from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class CombatUnit:
    """
    Unidade no contexto de combate.
    - efficacy/cost: nomes padronizados em inglês (core)
    - key: referencia sua UNIT_STATS (ex.: "infantry")
    """
    key: str
    name: str
    efficacy: float
    cost: float
    category: str | None = None
    tags: frozenset[str] = field(default_factory=frozenset)
    is_non_combat: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


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
