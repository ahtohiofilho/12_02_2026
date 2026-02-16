# core/economy/province_repo.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

Tile = tuple[int, int]


@dataclass(slots=True)
class ProvinceEconomyState:
    """
    Estado econômico completo de uma província (tile).

    Campos de configuração (definidos na criação, mudam raramente):
      - food_type, ore_type: nome do recurso produzido
      - food_productivity, ore_productivity: produtividade BASE do tile

    Campos mutáveis (mudam com alocação, turnos, comércio):
      - workers: total de trabalhadores
      - workers_food_int, workers_ore_int: split inteiro da alocação
      - food_output, ore_output, total_output: produção efetiva calculada
      - treasury: caixa local (Globi)
      - last_revenue: receita do último turno (para exibição)
    """
    tile: Tile

    # --- Workers ---
    workers: int = 2
    workers_food_int: int = 1
    workers_ore_int: int = 1

    # --- Tipos de recurso ---
    food_type: str | None = None
    ore_type: str | None = None

    # --- Produtividade BASE (não muda com alocação) ---
    food_productivity: float = 0.0
    ore_productivity: float = 0.0

    # --- Produção EFETIVA (workers_int * produtividade * multiplicador) ---
    food_output: float = 0.0
    ore_output: float = 0.0
    total_output: float = 0.0

    # --- Tesouro local ---
    treasury: float = 0.0
    last_revenue: float = 0.0


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
