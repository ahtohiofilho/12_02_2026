# core/workforce/facade.py
from __future__ import annotations

from dataclasses import dataclass
from core.production.queue import QueueItem, QueueItemType

Tile = tuple[int, int]


@dataclass(frozen=True, slots=True)
class WorkerInfo:
    current: int
    next_cost: float


class ProvinceWorkforceFacade:
    def __init__(self, *, planet, province):
        self.planet = planet
        self.province = province
        self.tile: Tile = province.tile_coords

    def worker_info(self) -> WorkerInfo:
        econ = self.planet.econ_repo.get(self.tile)
        current = int(econ.workers) if econ else 0
        next_cost = 5.0 + 0.5 * float(current)
        return WorkerInfo(current=current, next_cost=float(next_cost))

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

    # ---- revenue TOTAL only ----
    def revenue_total(self) -> float:
        r = self.planet.economy.calcular_equilibrio()
        return float(r.get_receita_total(self.tile))

    # ---- allocation preference ----
    def get_food_pref(self) -> float:
        return float(self.planet.workforce_repo.ensure(self.tile).food_pref)

    def set_food_pref(self, v: float) -> None:
        s = self.planet.workforce_repo.ensure(self.tile)
        s.food_pref = max(0.0, min(1.0, float(v)))

    # ---- queue ----
    def enqueue_worker(self) -> bool:
        info = self.worker_info()
        self.planet.production_queues.add(
            self.tile,
            QueueItem(item_type=QueueItemType.WORKER, data=None, cost=info.next_cost),
        )
        return True

    def queue_items(self) -> list[QueueItem]:
        return self.planet.production_queues.list_items(self.tile)

    def queue_total_cost(self) -> float:
        return float(sum(float(it.cost or 0.0) for it in self.queue_items()))

    def queue_remove(self, uid: str) -> bool:
        return self.planet.production_queues.remove_by_uid(self.tile, uid)

    def queue_clear(self) -> int:
        return self.planet.production_queues.clear(self.tile)
