# core/economy/province_repo.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

Tile = tuple[int, int]


@dataclass(slots=True)
class ProvinceEconomyState:
    tile: Tile
    workers: int = 1

    # Commodity "nome/tipo" produzido nesta província (pode ser None)
    food_type: str | None = None
    ore_type: str | None = None

    # Oferta (produção) desta província por turno (unidades abstratas)
    food_output: float = 0.0
    ore_output: float = 0.0


class ProvinceEconomyRepository:
    """
    Storage único da economia local por tile.
    Não conhece Planet, não conhece Civ, não conhece grafo.
    """
    def __init__(self):
        self._by_tile: dict[Tile, ProvinceEconomyState] = {}

    def upsert(self, state: ProvinceEconomyState) -> None:
        self._by_tile[state.tile] = state

    def get(self, tile: Tile) -> ProvinceEconomyState | None:
        return self._by_tile.get(tile)

    def ensure(self, tile: Tile) -> ProvinceEconomyState:
        s = self._by_tile.get(tile)
        if s is None:
            s = ProvinceEconomyState(tile=tile)
            self._by_tile[tile] = s
        return s

    def all(self) -> Iterable[ProvinceEconomyState]:
        return self._by_tile.values()

    def tiles(self) -> set[Tile]:
        return set(self._by_tile.keys())

    def delete(self, tile: Tile) -> None:
        self._by_tile.pop(tile, None)
