# ui/province/military_ui.py
"""
UI military helpers (single source of truth).

Goals:
- Provide:
  - icons, colors, and *display names* per unit_key (keys come from config.unit_stats.UNIT_STATS)
  - dynamic grouping by category
  - helpers to count units per tile and per civilization

Notes:
- This module does NOT depend on the combat system; it only reflects UNIT_STATS.
- If UNIT_STATS changes, update the dictionaries below to cover new keys.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import DefaultDict

from config.unit_stats import UNIT_STATS

# ============================================================
# VISUAL CONSTANTS — by unit_key (as in UNIT_STATS)
# ============================================================

# Prefer explicit coverage for current UNIT_STATS keys.
# UI fallbacks (if missing): icon="•", color="#888", name from UNIT_STATS or Title Case.
UNIT_ICONS: dict[str, str] = {
    # LAND
    "light_infantry": "🚶",
    "mechanized_infantry": "🚶‍♂️",
    "mbt": "🚗",
    "atgm_team": "🎯",
    "sp_artillery": "💥",
    "shorad": "📡",
    "support_vehicle": "🚚",

    # AIR
    "fighter": "✈️",
    "strike_aircraft": "🛩️",
    "ucav": "🛰️",
    "transport_aircraft": "🪂",

    # NAVAL
    "frigate": "🚢",
    "destroyer": "🛥️",
    "submarine": "🐟",
    "amphibious_ship": "🚤",
    "aircraft_carrier": "🛳️",

    # CIVILIAN
    "worker": "👷",
}

UNIT_COLORS: dict[str, str] = {
    # LAND
    "light_infantry": "#4CAF50",
    "mechanized_infantry": "#66BB6A",
    "mbt": "#8BC34A",
    "atgm_team": "#7CB342",
    "sp_artillery": "#FF9800",
    "shorad": "#FFC107",
    "support_vehicle": "#BCAAA4",

    # AIR
    "fighter": "#9C27B0",
    "strike_aircraft": "#673AB7",
    "ucav": "#7E57C2",
    "transport_aircraft": "#B0BEC5",

    # NAVAL
    "frigate": "#2196F3",
    "destroyer": "#1976D2",
    "submarine": "#00BCD4",
    "amphibious_ship": "#03A9F4",
    "aircraft_carrier": "#1565C0",

    # CIVILIAN
    "worker": "#9E9E9E",
}

# Full names for wide buttons (English UI).
# If you prefer using UNIT_STATS.name everywhere, you can remove this mapping and rely on config.
UNIT_DISPLAY_NAMES: dict[str, str] = {
    # LAND
    "light_infantry": "Light Infantry",
    "mechanized_infantry": "Mechanized Infantry",
    "mbt": "Main Battle Tank",
    "atgm_team": "ATGM Team",
    "sp_artillery": "Self-Propelled Artillery",
    "shorad": "SHORAD (Short-Range Air Defense)",
    "support_vehicle": "Support Vehicle",

    # AIR
    "fighter": "Fighter",
    "strike_aircraft": "Strike Aircraft",
    "ucav": "Attack Drone (UCAV)",
    "transport_aircraft": "Transport Aircraft",

    # NAVAL
    "frigate": "Frigate/Corvette",
    "destroyer": "Destroyer",
    "submarine": "Submarine",
    "amphibious_ship": "Amphibious Ship",
    "aircraft_carrier": "Aircraft Carrier",

    # CIVILIAN
    "worker": "Worker",
}

CATEGORY_ICONS: dict[str, str] = {
    "LAND": "⚔️",
    "NAVAL": "⚓",
    "AIR": "✈️",
    "CIVILIAN": "🏗️",
}

CATEGORY_COLORS: dict[str, str] = {
    "LAND": "#4CAF50",
    "NAVAL": "#2196F3",
    "AIR": "#9C27B0",
    "CIVILIAN": "#9E9E9E",
}


# ============================================================
# CATEGORY GROUPING (dynamic)
# ============================================================

def build_units_by_category() -> dict[str, list[str]]:
    """
    Builds category -> [unit_keys] mapping from UNIT_STATS.

    Example:
      {"LAND": [...], "NAVAL": [...], "AIR": [...], "CIVILIAN": [...]}

    List ordering: alphabetical (stable/predictable for UI).
    """
    by_cat: dict[str, list[str]] = {"LAND": [], "NAVAL": [], "AIR": [], "CIVILIAN": []}

    for key, stats in UNIT_STATS.items():
        cat_name = stats.category.name if hasattr(stats.category, "name") else str(stats.category)
        if cat_name not in by_cat:
            by_cat[cat_name] = []
        by_cat[cat_name].append(key)

    for cat in by_cat:
        by_cat[cat].sort()

    return by_cat


# Cache computed once on import
UNITS_BY_CATEGORY: dict[str, list[str]] = build_units_by_category()


# ============================================================
# UI NAME HELPERS
# ============================================================

def get_unit_display_name(unit_key: str) -> str:
    """
    Returns a friendly unit name for the UI (English).

    Priority:
      1) UNIT_DISPLAY_NAMES (manual UI override)
      2) UNIT_STATS[unit_key].name (config canonical name)
      3) fallback: unit_key in Title Case
    """
    if unit_key in UNIT_DISPLAY_NAMES:
        return UNIT_DISPLAY_NAMES[unit_key]

    stats = UNIT_STATS.get(unit_key)
    if stats:
        return str(stats.name)

    return unit_key.replace("_", " ").title()


def get_unit_category(unit_key: str) -> str:
    """Returns the category name ("LAND", "NAVAL", "AIR", "CIVILIAN") for a unit_key."""
    stats = UNIT_STATS.get(unit_key)
    if stats:
        return stats.category.name if hasattr(stats.category, "name") else "LAND"
    return "LAND"


# ============================================================
# COUNTING HELPERS
# ============================================================

def count_units_in_tile(
    planet,
    tile: tuple[int, int],
    owner_id: int | None = None,
) -> dict[str, int]:
    """
    Counts units by unit_key in a tile.

    - If owner_id is provided, filters only stacks owned by that civ.
    - Expects:
        planet.stacks.stacks_in_tile(tile) -> iterable of stacks
        stack.owner_id
        stack.units -> iterable with unit.unit_key
    """
    counts: Counter[str] = Counter()
    if not planet:
        return dict(counts)

    for stack in planet.stacks.stacks_in_tile(tile):
        if owner_id is not None and getattr(stack, "owner_id", None) != owner_id:
            continue
        for unit in getattr(stack, "units", []):
            counts[getattr(unit, "unit_key", "")] += 1

    counts.pop("", None)  # drop invalid
    return dict(counts)


def count_units_for_civ(planet, civ_id: int) -> dict[str, int]:
    """
    Counts ALL units of a civ by unit_key.

    Depends on:
      - planet.stacks.stack_uids_by_owner[civ_id] -> set[uids]
      - planet.stacks.get_stack(uid) -> stack with stack.units
    """
    counts: Counter[str] = Counter()
    if not planet:
        return dict(counts)

    civ_stack_uids = planet.stacks.stack_uids_by_owner.get(civ_id, set())
    for uid in civ_stack_uids:
        stack = planet.stacks.get_stack(uid)
        if not stack:
            continue
        for unit in getattr(stack, "units", []):
            counts[getattr(unit, "unit_key", "")] += 1

    counts.pop("", None)
    return dict(counts)


def group_counts_by_category(unit_counts: dict[str, int]) -> dict[str, int]:
    """Groups unit_key counts into category counts."""
    by_cat: DefaultDict[str, int] = defaultdict(int)
    for unit_key, count in unit_counts.items():
        cat = get_unit_category(unit_key)
        by_cat[cat] += int(count)
    return dict(by_cat)


def format_units_by_category(unit_counts: dict[str, int]) -> str:
    """
    Formats {unit_key: count} into a category summary string.

    Example:
      "⚔️ LAND: 5 | ⚓ NAVAL: 2"

    Shows only categories with count > 0.
    """
    by_cat = group_counts_by_category(unit_counts)

    parts: list[str] = []
    for cat in ("LAND", "NAVAL", "AIR", "CIVILIAN"):
        c = by_cat.get(cat, 0)
        if c > 0:
            icon = CATEGORY_ICONS.get(cat, "")
            parts.append(f"{icon} {cat}: {c}")

    return " | ".join(parts) if parts else "No units present"
