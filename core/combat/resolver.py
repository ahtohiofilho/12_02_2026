# core/combat/resolver.py
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

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

    - effA/effD são derivados de CombatUnit.efficacy e podem ser modificados por modifiers.
    - Unidade non-combat => efficacy efetiva = 0 (por convenção do jogo).
    - Se ambas efficacies efetivas forem 0 => 50/50.
    """
    modifiers: list[CombatModifier] = field(default_factory=list)
    rng: random.Random = field(default_factory=random.Random)

    def _base_efficacy(self, unit: CombatUnit) -> float:
        """Eficácia base já aplicando a convenção de non-combat."""
        return 0.0 if unit.is_non_combat else float(unit.efficacy)

    def _effective_efficacy(
        self,
        attacker: CombatUnit,
        defender: CombatUnit,
        ctx: CombatContext,
    ) -> tuple[float, float, dict[str, Any]]:
        a = self._base_efficacy(attacker)
        d = self._base_efficacy(defender)

        if a < 0 or d < 0:
            raise ValueError("efficacy não pode ser negativa")

        debug: dict[str, Any] = {
            "base": {"attacker": a, "defender": d},
            "multipliers": [],
        }

        a_mul = 1.0
        d_mul = 1.0
        for mod in self.modifiers:
            ma, md = mod.multipliers(attacker, defender, ctx)

            ma = float(ma)
            md = float(md)
            if ma < 0 or md < 0:
                raise ValueError(
                    f"Multiplicador negativo em {mod.__class__.__name__}: attacker={ma} defender={md}"
                )

            a_mul *= ma
            d_mul *= md
            debug["multipliers"].append(
                {"modifier": mod.__class__.__name__, "attacker": ma, "defender": md}
            )

        a_eff = a * a_mul
        d_eff = d * d_mul

        # Segurança: evita probabilidades esquisitas se alguém botar multiplier gigante/NaN.
        if a_eff < 0 or d_eff < 0:
            raise ValueError(f"Eficácia efetiva negativa: attacker={a_eff}, defender={d_eff}")

        debug["effective"] = {"attacker": a_eff, "defender": d_eff}
        return a_eff, d_eff, debug

    # ─────────────────────────────────────────────────────────────
    # NOVO: win_probability (necessário pro utility do v2.6)
    # ─────────────────────────────────────────────────────────────
    def win_probability(
        self,
        attacker: CombatUnit,
        defender: CombatUnit,
        ctx: CombatContext | None = None,
    ) -> float:
        """
        Retorna P(attacker vencer) SEM rolar RNG.
        Usado pelo tile battle v2.6 (utility).
        """
        ctx = ctx or CombatContext()
        a_eff, d_eff, _ = self._effective_efficacy(attacker, defender, ctx)

        total = a_eff + d_eff
        p = 0.5 if total <= 0.0 else (a_eff / total)
        return _clamp01(float(p))

    def odds(
        self,
        attacker: CombatUnit,
        defender: CombatUnit,
        ctx: CombatContext | None = None,
    ) -> CombatOdds:
        ctx = ctx or CombatContext()
        a_eff, d_eff, _ = self._effective_efficacy(attacker, defender, ctx)

        total = a_eff + d_eff
        p = 0.5 if total <= 0.0 else (a_eff / total)
        p = _clamp01(float(p))

        return CombatOdds(p_attacker_win=p, p_defender_win=1.0 - p)

    def resolve(
        self,
        attacker: CombatUnit,
        defender: CombatUnit,
        ctx: CombatContext | None = None,
    ) -> CombatResult:
        ctx = ctx or CombatContext()

        a_eff, d_eff, debug = self._effective_efficacy(attacker, defender, ctx)
        total = a_eff + d_eff
        p = 0.5 if total <= 0.0 else (a_eff / total)
        p = _clamp01(float(p))

        roll = float(self.rng.random())
        attacker_wins = roll < p

        debug.update(
            {
                "odds": {"p_attacker_win": p, "p_defender_win": 1.0 - p},
                "roll": roll,
            }
        )

        winner = attacker if attacker_wins else defender
        loser = defender if attacker_wins else attacker

        return CombatResult(
            attacker=attacker,
            defender=defender,
            odds=CombatOdds(p_attacker_win=p, p_defender_win=1.0 - p),
            winner=winner,
            loser=loser,
            roll=roll,
            debug=debug,
        )
