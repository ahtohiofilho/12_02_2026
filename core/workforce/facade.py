# core/workforce/facade.py
from __future__ import annotations

from dataclasses import dataclass

# IMPORTAÇÕES ADICIONADAS PARA SUPORTAR UNIDADES MILITARES
from config.unit_stats import get_unit_stats
from core.production.queue import QueueItem, QueueItemType
# FIM DAS IMPORTAÇÕES ADICIONADAS

from core.economy.production import (
    calculate_production,
    worker_cost,
)

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
    Não conhece UI. Conhece Planet apenas para acessar repos.
    """

    def __init__(self, *, planet, province):
        self.planet = planet
        self.province = province
        self.tile: Tile = province.tile_coords

    # ---- info ----

    def worker_info(self) -> WorkerInfo:
        econ = self.planet.econ_repo.get(self.tile)
        if not econ:
            return WorkerInfo(current=0, workers_food=0, workers_ore=0, next_cost=worker_cost(0, 0))

        current = int(econ.workers)
        workers_in_queue = self._count_workers_in_queue()
        cost = worker_cost(current, workers_in_queue)

        return WorkerInfo(
            current=current,
            workers_food=econ.workers_food_int,
            workers_ore=econ.workers_ore_int,
            next_cost=cost,
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
        """Retorna produtividades BASE (food, ore)."""
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
        return econ is not None and (econ.food_productivity or 0.0) > 0

    def has_ore_production(self) -> bool:
        econ = self.planet.econ_repo.get(self.tile)
        return econ is not None and (econ.ore_productivity or 0.0) > 0

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

        # Recalcular produção imediatamente
        econ = self.planet.econ_repo.get(self.tile)
        if econ:
            calculate_production(econ, pref)
            self.planet.economy.invalidar_cache()

    # ---- queue ----

    def enqueue_worker(self) -> bool:
        econ = self.planet.econ_repo.get(self.tile)
        if not econ:
            return False

        workers_in_queue = self._count_workers_in_queue()
        cost = worker_cost(econ.workers, workers_in_queue)

        self.planet.production_queues.add(
            self.tile,
            QueueItem(item_type=QueueItemType.WORKER, data=None, cost=cost),
        )
        return True

    def enqueue_military_unit(self, unit_key: str) -> bool:
        """
        Adiciona uma unidade militar à fila de produção da província.

        Retorna True se a unidade for enfileirada com sucesso, False caso contrário.
        """
        stats = get_unit_stats(unit_key)
        if not stats:
            print(f"❌ Facade: Unidade desconhecida '{unit_key}'")
            return False

        item = QueueItem(
            item_type=QueueItemType.MILITARY,
            data=unit_key,  # Armazena a chave da unidade (ex: "infantry")
            cost=float(stats.cost)
        )

        self.planet.production_queues.add(self.tile, item)
        return True

    def queue_items(self) -> list[QueueItem]:
        return self.planet.production_queues.items(self.tile)

    def queue_total_cost(self) -> float:
        return float(sum(float(it.cost or 0.0) for it in self.queue_items()))

    def queue_remove(self, uid: str) -> bool:
        return self.planet.production_queues.remove_by_uid(self.tile, uid)

    def queue_clear(self) -> int:
        return self.planet.production_queues.clear(self.tile)

    # ---- helpers ----

    def _count_workers_in_queue(self) -> int:
        return sum(
            1 for it in self.planet.production_queues.items(self.tile)
            if it.item_type == QueueItemType.WORKER
        )

