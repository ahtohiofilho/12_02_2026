# core/economy/production.py
"""
Lógica de produção por província.

Responsabilidades:
  - Calcular split inteiro de workers (food vs ore)
  - Calcular produção efetiva (workers * produtividade * multiplicador)
  - Inicializar estado econômico de uma província a partir do grafo
  - Processar fila de produção (1 item por turno)

Não conhece UI. Não conhece Planet diretamente (recebe o que precisa).
"""
from __future__ import annotations

from config.economy import (
    MULTIPLICADOR_JORNADA,
    CUSTO_TRABALHADOR_BASE,
    ALIMENTO_POR_BIOMA,
    PRODUTIVIDADE_MINERIO_COMPLEMENTO,
)
from core.economy.province_repo import ProvinceEconomyState
from core.production.queue import QueueItem, QueueItemType

Tile = tuple[int, int]


# ============================================================
# SPLIT DE WORKERS
# ============================================================

def split_workers(total: int, food_pref: float) -> tuple[int, int]:
    """
    Converte preferência float (0..1) em inteiros de workers.

    Regra de empate (food-first):
      Se o decimal é exatamente 0.5, arredonda para cima em food.

    Args:
        total: número total de workers
        food_pref: preferência de alimento (0.0 = tudo minério, 1.0 = tudo alimento)

    Returns:
        (workers_food, workers_ore) onde workers_food + workers_ore == total
    """
    if total <= 0:
        return 0, 0

    food_pref = max(0.0, min(1.0, float(food_pref)))

    if total == 1:
        return (1, 0) if food_pref >= 0.5 else (0, 1)

    food_exact = total * food_pref
    food_decimal = food_exact - int(food_exact)

    TOLERANCIA = 0.001
    is_empate = abs(food_decimal - 0.5) < TOLERANCIA

    if is_empate:
        food_int = int(food_exact) + 1
    else:
        food_int = round(food_exact)

    food_int = max(0, min(food_int, total))
    ore_int = total - food_int

    return food_int, ore_int


# ============================================================
# CÁLCULO DE PRODUÇÃO
# ============================================================

def calculate_production(econ: ProvinceEconomyState, food_pref: float) -> None:
    """
    Calcula e atualiza a produção efetiva de uma província IN-PLACE.

    Fórmula:
        food_output = workers_food_int * food_productivity * MULTIPLICADOR_JORNADA
        ore_output  = workers_ore_int  * ore_productivity  * MULTIPLICADOR_JORNADA

    Args:
        econ: estado econômico da província (será mutado)
        food_pref: preferência de alimento (0.0 a 1.0)
    """
    food_int, ore_int = split_workers(econ.workers, food_pref)

    econ.workers_food_int = food_int
    econ.workers_ore_int = ore_int

    econ.food_output = float(food_int) * econ.food_productivity * MULTIPLICADOR_JORNADA
    econ.ore_output = float(ore_int) * econ.ore_productivity * MULTIPLICADOR_JORNADA
    econ.total_output = econ.food_output + econ.ore_output


# ============================================================
# INICIALIZAÇÃO DE ESTADO ECONÔMICO
# ============================================================

def init_province_economy(
    tile: Tile,
    biome: str,
    fertility: float,
    tectonic_plate: str,
    workers: int,
) -> ProvinceEconomyState:
    """
    Cria um ProvinceEconomyState completo a partir dos dados do grafo.

    Args:
        tile: coordenadas do tile
        biome: nome do bioma (ex: "Meadow")
        fertility: fertilidade ponderada do grafo (já calculada em _geography)
        tectonic_plate: nome da placa tectônica (ex: "Alpha")
        workers: quantidade inicial de trabalhadores (varia por contexto)

    Returns:
        Estado econômico inicializado com produção calculada.
    """
    food_type = ALIMENTO_POR_BIOMA.get(biome, "Food")
    ore_type = f"{tectonic_plate} Ore" if tectonic_plate else "Ore"

    food_productivity = float(fertility)
    ore_productivity = max(0.0, PRODUTIVIDADE_MINERIO_COMPLEMENTO - food_productivity)

    state = ProvinceEconomyState(
        tile=tile,
        workers=max(0, int(workers)),
        food_type=food_type,
        ore_type=ore_type,
        food_productivity=food_productivity,
        ore_productivity=ore_productivity,
    )

    calculate_production(state, food_pref=0.5)

    return state


# ============================================================
# CUSTO DE TRABALHADOR
# ============================================================

def worker_cost(current_workers: int, workers_in_queue: int = 0) -> float:
    """
    Calcula o custo do PRÓXIMO trabalhador a ser enfileirado.

    Regra: custo_base * (2 ^ workers_já_na_fila)
    Ex com base=5: fila=0 → 5, fila=1 → 10, fila=2 → 20

    Args:
        current_workers: workers atuais (reservado para uso futuro)
        workers_in_queue: quantos WORKER já estão na fila

    Returns:
        Custo em Globi.
    """
    return CUSTO_TRABALHADOR_BASE * (2 ** workers_in_queue)


# ============================================================
# PROCESSAR FILA DE PRODUÇÃO (POR TURNO)
# ============================================================

def process_production_queue(
    econ: ProvinceEconomyState,
    queue_items: list[QueueItem],
    remove_first_fn,
    food_pref: float,
    *,
    add_unit_fn=None,
) -> dict:
    """
    Processa a fila de produção de uma província: NO MÁXIMO 1 item por turno.

    Regras:
      - Se não tem dinheiro para o primeiro item, para.
      - WORKER: incrementa workers, recalcula produção.
      - MILITARY: chama add_unit_fn (se fornecido).

    Args:
        econ: estado econômico (será mutado: treasury, workers)
        queue_items: lista ordenada de itens na fila
        remove_first_fn: callable que remove o primeiro item da fila
        food_pref: preferência de alocação atual
        add_unit_fn: callable(unit_key, tile) para spawnar unidade militar

    Returns:
        dict com resultado do processamento
    """
    result = {
        "workers_added": 0,
        "units_produced": [],
        "items_pending": len(queue_items),
        "produced": None,
        "insufficient_funds": False,
    }

    if not queue_items:
        return result

    item = queue_items[0]
    cost = float(item.cost or 0.0)

    if econ.treasury < cost:
        result["insufficient_funds"] = True
        return result

    # Pagar
    econ.treasury -= cost

    if item.item_type == QueueItemType.WORKER:
        econ.workers += 1
        calculate_production(econ, food_pref)
        result["workers_added"] = 1
        result["produced"] = "worker"

    elif item.item_type == QueueItemType.MILITARY:
        unit_key = str(item.data) if item.data else None
        if unit_key and add_unit_fn:
            add_unit_fn(unit_key, econ.tile)
        result["units_produced"].append(unit_key or "unknown")
        result["produced"] = unit_key

    remove_first_fn()
    result["items_pending"] = len(queue_items) - 1

    return result
