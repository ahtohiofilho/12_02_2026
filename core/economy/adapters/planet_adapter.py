# core/economy/adapters/planet_adapter.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, TYPE_CHECKING

from core.economy.models import EconomyWorldView, ProvinceView, Tile
from core.economy.province_repo import ProvinceEconomyRepository

if TYPE_CHECKING:
    from core.planet import Planet


@dataclass(frozen=True, slots=True)
class _ProvinceViewFromRepo:
    """
    Implementação concreta de ProvinceView para o TradeCalculator.
    Mapeia ProvinceEconomyState -> campos que o comércio precisa.
    """
    tile: Tile
    workers: int
    food_type: str | None
    ore_type: str | None
    food_output: float
    ore_output: float


class PlanetEconomyAdapter(EconomyWorldView):
    """
    Liga Planet + ProvinceEconomyRepository ao sistema de comércio.
    A economia não sabe o que é Planet; só recebe esse adapter.
    """

    def __init__(self, planet: Planet, repo: ProvinceEconomyRepository):
        self.planet = planet
        self.repo = repo

    def provinces(self) -> Iterable[ProvinceView]:
        for s in self.repo.all():
            yield _ProvinceViewFromRepo(
                tile=s.tile,
                workers=int(max(0, s.workers)),
                food_type=s.food_type,
                ore_type=s.ore_type,
                food_output=float(s.food_output or 0.0),
                ore_output=float(s.ore_output or 0.0),
            )

    def trade_graph(self):
        return self.planet.graph
