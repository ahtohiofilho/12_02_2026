from __future__ import annotations

import random
from dataclasses import dataclass, field

from .models import CombatUnit, CombatContext, CombatOdds, CombatResult
from .modifiers import CombatModifier


def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


@dataclass(slots=True)
class CombatResolver:
    """
    Combate 1v1:
      P(attacker vencer) = effA / (effA + effD)
    onde effA/effD podem ser modificados por modifiers.

    Convenções:
    - Unidade non-combat => efficacy efetiva = 0
    - Se ambas efficacies efetivas forem 0 => 50/50
    """
    modifiers: list[CombatModifier] = field(default_factory=list)
    rng: random.Random = field(default_factory=random.Random)

    def _effective_efficacy(
        self,
        attacker: CombatUnit,
        defender: CombatUnit,
        ctx: CombatContext,
    ) -> tuple[float, float, dict]:
        a = 0.0 if attacker.is_non_combat else float(attacker.efficacy)
        d = 0.0 if defender.is_non_combat else float(defender.efficacy)

        if a < 0 or d < 0:
            raise ValueError("efficacy não pode ser negativa")

        debug = {"base": {"attacker": a, "defender": d}, "multipliers": []}

        a_mul = 1.0
        d_mul = 1.0
        for mod in self.modifiers:
            ma, md = mod.multipliers(attacker, defender, ctx)
            a_mul *= float(ma)
            d_mul *= float(md)
            debug["multipliers"].append(
                {"modifier": mod.__class__.__name__, "attacker": ma, "defender": md}
            )

        a_eff = a * a_mul
        d_eff = d * d_mul
        debug["effective"] = {"attacker": a_eff, "defender": d_eff}
        return a_eff, d_eff, debug

    def odds(self, attacker: CombatUnit, defender: CombatUnit, ctx: CombatContext | None = None) -> CombatOdds:
        ctx = ctx or CombatContext()
        a_eff, d_eff, _ = self._effective_efficacy(attacker, defender, ctx)

        total = a_eff + d_eff
        p = 0.5 if total <= 0 else (a_eff / total)
        p = _clamp01(p)

        return CombatOdds(p_attacker_win=p, p_defender_win=1.0 - p)

    def resolve(self, attacker: CombatUnit, defender: CombatUnit, ctx: CombatContext | None = None) -> CombatResult:
        ctx = ctx or CombatContext()

        odds = self.odds(attacker, defender, ctx)
        roll = self.rng.random()
        attacker_wins = roll < odds.p_attacker_win

        a_eff, d_eff, debug = self._effective_efficacy(attacker, defender, ctx)
        debug.update(
            {
                "odds": {"p_attacker_win": odds.p_attacker_win, "p_defender_win": odds.p_defender_win},
                "roll": roll,
                "effective_efficacy": {"attacker": a_eff, "defender": d_eff},
            }
        )

        winner = attacker if attacker_wins else defender
        loser = defender if attacker_wins else attacker

        return CombatResult(
            attacker=attacker,
            defender=defender,
            odds=odds,
            winner=winner,
            loser=loser,
            roll=roll,
            debug=debug,
        )
