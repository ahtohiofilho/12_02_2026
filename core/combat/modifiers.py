from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import CombatUnit, CombatContext
from config.unit_stats import ADVANTAGE_MAP, ADVANTAGE_MULTIPLIER


class CombatModifier(Protocol):
    def multipliers(
        self,
        attacker: CombatUnit,
        defender: CombatUnit,
        ctx: CombatContext,
    ) -> tuple[float, float]:
        ...


@dataclass(frozen=True, slots=True)
class AdvantageModifier:
    """
    Aplica bônus de vantagem baseado no seu ADVANTAGE_MAP.
    Regra:
      se defender.key está em ADVANTAGE_MAP[attacker.key] => attacker * ADVANTAGE_MULTIPLIER
    """
    multiplier: float = ADVANTAGE_MULTIPLIER

    def multipliers(self, attacker: CombatUnit, defender: CombatUnit, ctx: CombatContext) -> tuple[float, float]:
        advantages = ADVANTAGE_MAP.get(attacker.key, frozenset())
        if defender.key in advantages:
            return self.multiplier, 1.0
        return 1.0, 1.0
