# core/economy/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol

Tile = tuple[int, int]


class ProvinceView(Protocol):
    tile: Tile
    workers: int
    food_type: str | None
    ore_type: str | None
    food_output: float
    ore_output: float


class EconomyWorldView(Protocol):
    def provinces(self) -> Iterable[ProvinceView]: ...
    def trade_graph(self) -> Any: ...


@dataclass(slots=True)
class ResultadoComercio:
    # Mantive sua estrutura para compatibilidade
    precos_alimento: dict[str, dict[Tile, float]] = field(default_factory=dict)
    precos_minerio: dict[str, dict[Tile, float]] = field(default_factory=dict)

    receitas_alimento: dict[Tile, float] = field(default_factory=dict)
    receitas_minerio: dict[Tile, float] = field(default_factory=dict)

    fluxos_alimento: dict[str, dict] = field(default_factory=dict)  # tipo -> origem -> destino -> qtd
    fluxos_minerio: dict[str, dict] = field(default_factory=dict)

    demandas_alimento: dict[str, dict[Tile, float]] = field(default_factory=dict)
    demandas_minerio: dict[str, dict[Tile, float]] = field(default_factory=dict)

    iteracoes: int = 0
    convergiu: bool = False

    def get_receita_total(self, tile: Tile) -> float:
        return float(self.receitas_alimento.get(tile, 0.0)) + float(self.receitas_minerio.get(tile, 0.0))
