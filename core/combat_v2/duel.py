# core/combat_v2/duel.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.combat.models import CombatContext
from core.combat.resolver import CombatResolver
from core.combat.tile_battle import combat_unit_from_key

from .api import UnitRuntime, DuelOutcome
from .tables import evasive_multiplier_against_target


def kill_prob(attacker: UnitRuntime, defender: UnitRuntime, resolver: CombatResolver, ctx: CombatContext) -> float:
    """
    Probabilidade base de "kill" (abate binário) do attacker contra o defender,
    usando o CombatResolver 1v1 existente.
    """
    a = combat_unit_from_key(attacker.unit_key)
    d = combat_unit_from_key(defender.unit_key)

    p = float(resolver.win_probability(a, d, ctx=ctx))
    if p < 0.0:
        return 0.0
    if p > 1.0:
        return 1.0
    return p


@dataclass(frozen=True, slots=True)
class DuelConfig:
    allow_mutual_kill: bool = False  # mantém “no máximo 1 kill por duelo”


def resolve_duel(
    *,
    attacker: UnitRuntime,
    defender: UnitRuntime,
    resolver: CombatResolver,
    ctx: CombatContext,
    rng,
    dist_tiles: int = 0,
    cfg: DuelConfig | None = None,
) -> DuelOutcome:
    """
    Resolve um duelo A->D com retaliação condicional.

    Ajuste pedido (extra-contrato):
      - EVASIVE pode ser atacado (normal), mas NÃO pode atacar.
      - Interpretação operacional:
          * Se attacker está EVASIVE => ele não pode causar kill (p_ad efetivo = 0)
            (ainda assim "consome" o ataque da rodada, se a engine escolheu ele como atacante).
          * Se defender está EVASIVE => ele não pode causar kill na retaliação (p_da efetivo = 0).
      - Retaliação: só existe se dist_tiles <= defender.range.

    Observação:
      - A redução de chance contra alvos EVASIVE (k_evasive) continua válida.
        Aqui ela multiplica a chance de matar o ALVO (isto é, A->D aplica no D; D->A aplica no A).
    """
    cfg = cfg or DuelConfig()

    # ── Probabilidades base ──
    p_ad = kill_prob(attacker, defender, resolver, ctx)

    can_retaliate = int(dist_tiles) <= int(getattr(defender, "range", 0) or 0)
    p_da = 0.0 if not can_retaliate else kill_prob(defender, attacker, resolver, ctx)

    # ── Multiplicador evasive: reduz chance CONTRA o alvo evasivo ──
    # (isto é: se o alvo está EVASIVE, fica mais difícil abatê-lo)
    if getattr(defender, "evasion_mode", "COMMITTED") == "EVASIVE":
        p_ad *= float(evasive_multiplier_against_target(defender.unit_key))
    if getattr(attacker, "evasion_mode", "COMMITTED") == "EVASIVE":
        p_da *= float(evasive_multiplier_against_target(attacker.unit_key))

    # ── Regra extra: EVASIVE não pode atacar (não pode causar kill) ──
    # Em vez de “anular depois”, zera a chance de kill do lado EVASIVE.
    if getattr(attacker, "evasion_mode", "COMMITTED") == "EVASIVE":
        p_ad = 0.0
    if getattr(defender, "evasion_mode", "COMMITTED") == "EVASIVE":
        p_da = 0.0

    # clamp defensivo
    if p_ad < 0.0:
        p_ad = 0.0
    elif p_ad > 1.0:
        p_ad = 1.0
    if p_da < 0.0:
        p_da = 0.0
    elif p_da > 1.0:
        p_da = 1.0

    # ── Sorteio ──
    ad_hits = (rng.random() < p_ad)
    da_hits = (rng.random() < p_da)

    debug: dict[str, Any] = {
        "dist_tiles": int(dist_tiles),
        "retaliation": {"can_retaliate": bool(can_retaliate), "defender_range": int(getattr(defender, "range", 0) or 0)},
        "evasion_mode": {"A": getattr(attacker, "evasion_mode", None), "D": getattr(defender, "evasion_mode", None)},
        "p_kill": {"A->D": float(p_ad), "D->A": float(p_da)},
        "raw_hits": {"A->D": bool(ad_hits), "D->A": bool(da_hits)},
        "mvp": {"evasive_enabled": True, "remote_enabled": True},
        "rules": {
            "evasive_cannot_attack": True,
            "evasive_reduces_incoming_kill_prob": True,
            "retaliation_by_distance": True,
        },
    }

    attacker_killed = False
    defender_killed = False

    # ── Resolução (no máximo 1 kill por duelo, salvo cfg.allow_mutual_kill) ──
    if cfg.allow_mutual_kill:
        attacker_killed = bool(da_hits)
        defender_killed = bool(ad_hits)
    else:
        if ad_hits and da_hits:
            total = p_ad + p_da
            a_wins = (rng.random() < 0.5) if total <= 0.0 else (rng.random() < (p_ad / total))
            defender_killed = bool(a_wins)
            attacker_killed = bool(not a_wins)
            debug["both_hit_resolution"] = {"a_wins": bool(a_wins), "total_p": float(total)}
        elif ad_hits:
            defender_killed = True
        elif da_hits:
            attacker_killed = True

    return DuelOutcome(
        attacker_uid=attacker.uid,
        defender_uid=defender.uid,
        attacker_killed=attacker_killed,
        defender_killed=defender_killed,
        debug=debug,
    )
