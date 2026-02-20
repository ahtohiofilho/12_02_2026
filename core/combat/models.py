from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config.unit_stats import UnitStats


@dataclass(frozen=True, slots=True)
class CombatUnit:
    """
    Unidade no contexto de combate.
    - efficacy/cost: nomes padronizados em inglês (core)
    - key: referencia sua UNIT_STATS (ex.: "light_infantry", "mbt")
    """
    key: str
    name: str
    efficacy: float
    cost: float
    category: str | None = None
    tags: frozenset[str] = field(default_factory=frozenset)
    is_non_combat: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


def combat_unit_from_stats(
    key: str,
    stats: UnitStats,
    *,
    extra: dict[str, Any] | None = None,
) -> CombatUnit:
    """
    Converte UnitStats (config) -> CombatUnit (runtime de combate).

    IMPORTANTES:
    - efficacy aqui é BASE (sem vantagem). A vantagem entra via modifiers.
    - is_non_combat é respeitado pelo CombatResolver (zera eficácia efetiva).
    """
    tags: set[str] = set()

    if stats.long_range:
        tags.add("long_range")
    if stats.can_transport:
        tags.add("transport")

    return CombatUnit(
        key=key,
        name=stats.name,
        efficacy=float(stats.eficacia),
        cost=float(stats.cost),
        category=stats.category.name,  # "LAND" / "AIR" / "NAVAL" / "CIVILIAN"
        tags=frozenset(tags),
        is_non_combat=bool(stats.is_non_combat),
        extra=extra or {},
    )


@dataclass(frozen=True, slots=True)
class CombatContext:
    attacker_tile: Any | None = None
    defender_tile: Any | None = None
    biome: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CombatOdds:
    p_attacker_win: float
    p_defender_win: float


@dataclass(frozen=True, slots=True)
class CombatResult:
    attacker: CombatUnit
    defender: CombatUnit
    odds: CombatOdds
    winner: CombatUnit
    loser: CombatUnit
    roll: float  # 0..1
    debug: dict[str, Any] = field(default_factory=dict)
