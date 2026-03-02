# core/combat/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config.unit_stats import UnitStats, UnitCategory  # <-- add UnitCategory


@dataclass(frozen=True, slots=True)
class CombatUnit:
    key: str
    name: str
    efficacy: float
    cost: float
    category: UnitCategory | None = None  # <-- era str | None
    tags: frozenset[str] = field(default_factory=frozenset)
    is_non_combat: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


def combat_unit_from_stats(
    key: str,
    stats: UnitStats,
    *,
    extra: dict[str, Any] | None = None,
) -> CombatUnit:
    tags: set[str] = set()

    if stats.can_transport:
        tags.add("transport")

    return CombatUnit(
        key=key,
        name=stats.name,
        efficacy=float(stats.eficacia),
        cost=float(stats.cost),
        category=stats.category,  # <-- era stats.category.name
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
