# core/workforce/facade.py
from __future__ import annotations

from dataclasses import dataclass

from config.unit_stats import get_unit_stats
from core.production.queue import QueueItem, QueueItemType
from core.economy.production import calculate_production, worker_cost

Tile = tuple[int, int]


@dataclass(frozen=True, slots=True)
class WorkerInfo:
    current: int
    workers_food: int
    workers_ore: int
    next_cost: float


class ProvinceWorkforceFacade:
    """
    Facade que conecta a UI de workforce aos repositórios do core.

    Responsabilidades aqui (regras do jogo relacionadas à UI):
      - enfileirar itens
      - cancelar/remover itens aplicando refund (50% do que já foi pago)
      - expor métricas da fila (total, paid, remaining)

    Não processa turno; isso fica em Planet/process_production.
    """

    def __init__(self, *, planet, province):
        self.planet = planet
        self.province = province
        self.tile: Tile = province.tile_coords

    # ---- info ----

    def worker_info(self) -> WorkerInfo:
        econ = self.planet.econ_repo.get(self.tile)
        if not econ:
            return WorkerInfo(current=0, workers_food=0, workers_ore=0, next_cost=worker_cost(0))

        current = int(econ.workers)
        civ = self.province.owner

        # Pega o custo baseado no histórico de compras da Civilização
        cost = worker_cost(civ.workers_purchased) if civ else worker_cost(0)

        return WorkerInfo(
            current=current,
            workers_food=int(econ.workers_food_int),
            workers_ore=int(econ.workers_ore_int),
            next_cost=float(cost),
        )

    def resource_names(self) -> tuple[str, str]:
        econ = self.planet.econ_repo.get(self.tile)
        food_name = (econ.food_type if econ and econ.food_type else "Food")
        ore_name = (econ.ore_type if econ and econ.ore_type else "Ore")
        return str(food_name), str(ore_name)

    def outputs(self) -> tuple[float, float]:
        econ = self.planet.econ_repo.get(self.tile)
        if not econ:
            return 0.0, 0.0
        return float(econ.food_output or 0.0), float(econ.ore_output or 0.0)

    def productivities(self) -> tuple[float, float]:
        econ = self.planet.econ_repo.get(self.tile)
        if not econ:
            return 0.0, 0.0
        return float(econ.food_productivity or 0.0), float(econ.ore_productivity or 0.0)

    def treasury(self) -> float:
        econ = self.planet.econ_repo.get(self.tile)
        return float(econ.treasury) if econ else 0.0

    def biome(self) -> str:
        if self.planet.graph.has_node(self.tile):
            return self.planet.graph.nodes[self.tile].get("bioma", "Unknown")
        return "Unknown"

    def has_food_production(self) -> bool:
        econ = self.planet.econ_repo.get(self.tile)
        return econ is not None and float(econ.food_productivity or 0.0) > 0.0

    def has_ore_production(self) -> bool:
        econ = self.planet.econ_repo.get(self.tile)
        return econ is not None and float(econ.ore_productivity or 0.0) > 0.0

    # ---- revenue ----

    def revenue_total(self) -> float:
        r = self.planet.economy.calcular_equilibrio()
        return float(r.get_receita_total(self.tile))

    # ---- allocation ----

    def get_food_pref(self) -> float:
        return float(self.planet.workforce_repo.ensure(self.tile).food_pref)

    def set_food_pref(self, v: float) -> None:
        pref = max(0.0, min(1.0, float(v)))
        self.planet.workforce_repo.ensure(self.tile).food_pref = pref

        econ = self.planet.econ_repo.get(self.tile)
        if econ:
            calculate_production(econ, pref)
            self.planet.economy.invalidar_cache()

    # ---- queue: enqueue ----

    def enqueue_worker(self) -> bool:
        econ = self.planet.econ_repo.get(self.tile)
        if not econ:
            return False

        civ = self.province.owner
        if not civ:
            return False

        # Calcula o custo ANTES de incrementar
        cost = worker_cost(civ.workers_purchased)

        self.planet.production_queues.add(
            self.tile,
            QueueItem(item_type=QueueItemType.WORKER, data=None, cost=float(cost), paid=0.0),
        )

        # INCREMENTA O HISTÓRICO: O próximo já vai custar o dobro
        civ.workers_purchased += 1

        return True

    def enqueue_military_unit(self, unit_key: str) -> bool:
        stats = get_unit_stats(unit_key)
        if not stats:
            print(f"❌ Facade: Unidade desconhecida '{unit_key}'")
            return False

        item = QueueItem(
            item_type=QueueItemType.MILITARY,
            data=str(unit_key),
            cost=float(stats.cost),
            paid=0.0,
        )
        self.planet.production_queues.add(self.tile, item)
        return True

    # ---- queue: read ----

    def queue_items(self) -> list[QueueItem]:
        # retorna cópia (o repo já faz isso), ok para UI
        return self.planet.production_queues.items(self.tile)

    def queue_total_cost(self) -> float:
        """Soma do custo TOTAL (não restante). Mantido por compatibilidade."""
        return float(sum(float(it.cost or 0.0) for it in self.queue_items()))

    def queue_total_paid(self) -> float:
        return float(sum(float(getattr(it, "paid", 0.0) or 0.0) for it in self.queue_items()))

    def queue_total_remaining(self) -> float:
        return float(sum(float(getattr(it, "remaining", 0.0) or 0.0) for it in self.queue_items()))

    # ---- queue: cancel/remove (refund 50% do paid) ----

    def queue_remove(self, uid: str) -> bool:
        econ = self.planet.econ_repo.get(self.tile)
        if not econ:
            return False

        q = self.planet.production_queues.ensure(self.tile)

        for i, it in enumerate(q.items):
            if it.uid == uid:
                paid = float(getattr(it, "paid", 0.0) or 0.0)
                refund = 0.5 * paid
                if refund > 0.0:
                    econ.treasury += refund

                # Se o jogador cancelou a compra, nós "desfazemos" a compra no histórico
                if it.item_type == QueueItemType.WORKER:
                    civ = self.province.owner
                    if civ and civ.workers_purchased > 0:
                        civ.workers_purchased -= 1

                q.items.pop(i)
                return True

        return False

    def queue_clear(self) -> int:
        econ = self.planet.econ_repo.get(self.tile)
        if not econ:
            return 0

        q = self.planet.production_queues.ensure(self.tile)

        total_refund = 0.0
        workers_canceled = 0
        for it in q.items:
            total_refund += 0.5 * float(getattr(it, "paid", 0.0) or 0.0)
            if it.item_type == QueueItemType.WORKER:
                workers_canceled += 1

        if total_refund > 0.0:
            econ.treasury += total_refund

        # Desfaz as compras no histórico
        civ = self.province.owner
        if civ and workers_canceled > 0:
            civ.workers_purchased = max(0, civ.workers_purchased - workers_canceled)

        n = len(q.items)
        q.items.clear()
        return n