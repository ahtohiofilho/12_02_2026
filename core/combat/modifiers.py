# core/combat/modifiers.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import CombatUnit, CombatContext
from config.unit_stats import ADVANTAGE_MAP


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
    Aplica bônus de vantagem ponderado por par (attacker_key -> {defender_key: multiplier}).

    Regra:
      - Se existir ADVANTAGE_MAP[attacker.key][defender.key], aplica esse multiplicador ao atacante.
      - Caso contrário, 1.0.
    """
    def multipliers(
        self,
        attacker: CombatUnit,
        defender: CombatUnit,
        ctx: CombatContext,
    ) -> tuple[float, float]:
        by_defender = ADVANTAGE_MAP.get(attacker.key)
        if not by_defender:
            return 1.0, 1.0

        mult = by_defender.get(defender.key, 1.0)
        return float(mult), 1.0
