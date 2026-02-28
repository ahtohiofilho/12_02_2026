from __future__ import annotations
from dataclasses import dataclass, field

Tile = tuple[int, int]

@dataclass(slots=True)
class WorkforceState:
    tile: Tile
    # preferência do usuário (0..1) para alimento; minério = 1 - food_pref
    food_pref: float = 0.5

    # Governor local (default ON)
    auto_max_revenue: bool = True

    # workers “móveis” estacionados neste tile (uids)
    mobile_worker_uids: list[str] = field(default_factory=list)

class WorkforceRepository:
    def __init__(self):
        self._by_tile: dict[Tile, WorkforceState] = {}

    def ensure(self, tile: Tile) -> WorkforceState:
        s = self._by_tile.get(tile)
        if s is None:
            s = WorkforceState(tile=tile)
            self._by_tile[tile] = s
        return s

    def get(self, tile: Tile) -> WorkforceState | None:
        return self._by_tile.get(tile)
