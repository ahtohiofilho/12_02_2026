# core/combat/unit_adapter.py
from __future__ import annotations

from config.unit_stats import get_unit_stats
from .models import CombatUnit


def combat_unit_from_key(unit_key: str) -> CombatUnit:
    """
    Converte um unit_key do config (UNIT_STATS) para um CombatUnit (core).
    Centraliza aqui a "tradução" de nomes: eficacia -> efficacy.
    """
    stats = get_unit_stats(unit_key)
    if stats is None:
        raise KeyError(f"Unidade desconhecida: {unit_key}")

    return CombatUnit(
        key=unit_key,
        name=stats.name,
        efficacy=float(stats.eficacia),
        cost=float(stats.cost),
        category=stats.category.name if hasattr(stats.category, "name") else str(stats.category),
        is_non_combat=bool(stats.is_non_combat),
        extra={
            "movement": stats.movement,
            "sprite_key": stats.sprite_key,
            "can_transport": stats.can_transport,
            "vision_range": stats.vision_range,
        },
    )
