# ui/province/military_ui.py
"""
Constantes visuais e helpers para exibição de unidades militares.
Fonte única de verdade para ícones, cores, abreviações e helpers de contagem.
Todos os widgets de UI devem importar daqui.
"""

from collections import Counter, defaultdict

from config.unit_stats import UNIT_STATS


# ============================================================
# CONSTANTES VISUAIS — por unit_key (lowercase, como em UNIT_STATS)
# ============================================================

UNIT_ICONS: dict[str, str] = {
    "infantry":           "🚶",
    "tank":               "🚗",
    "artillery":          "💥",
    "support_vehicle":    "🚚",
    "warship":            "🚢",
    "aircraft_carrier":   "🛳️",
    "submarine":          "🐟",
    "amphibious_ship":    "🚤",
    "fighter":            "✈️",
    "bomber":             "🛩️",
    "gunship":            "🚁",
    "transport_aircraft": "🪂",
}

UNIT_COLORS: dict[str, str] = {
    "infantry":           "#4CAF50",
    "tank":               "#8BC34A",
    "artillery":          "#FF9800",
    "support_vehicle":    "#BCAAA4",
    "warship":            "#2196F3",
    "aircraft_carrier":   "#1976D2",
    "submarine":          "#00BCD4",
    "amphibious_ship":    "#03A9F4",
    "fighter":            "#9C27B0",
    "bomber":             "#673AB7",
    "gunship":            "#E91E63",
    "transport_aircraft": "#B0BEC5",
}

UNIT_ABBREVIATIONS: dict[str, str] = {
    "infantry":           "INF",
    "tank":               "TNK",
    "artillery":          "ART",
    "support_vehicle":    "SUP",
    "warship":            "WRS",
    "aircraft_carrier":   "CV",
    "submarine":          "SUB",
    "amphibious_ship":    "AMP",
    "fighter":            "FGT",
    "bomber":             "BMB",
    "gunship":            "GUN",
    "transport_aircraft": "TRN",
}

CATEGORY_ICONS: dict[str, str] = {
    "LAND":  "⚔️",
    "NAVAL": "⚓",
    "AIR":   "✈️",
}

CATEGORY_COLORS: dict[str, str] = {
    "LAND":  "#4CAF50",
    "NAVAL": "#2196F3",
    "AIR":   "#9C27B0",
}


# ============================================================
# AGRUPAMENTO DINÂMICO
# ============================================================

def build_units_by_category() -> dict[str, list[str]]:
    """
    Constrói mapeamento categoria -> [unit_keys] a partir de UNIT_STATS.
    Ex: {"LAND": ["infantry", "tank", ...], "NAVAL": [...], "AIR": [...]}
    """
    by_cat: dict[str, list[str]] = {"LAND": [], "NAVAL": [], "AIR": []}
    for key, stats in UNIT_STATS.items():
        cat_name = stats.category.name if hasattr(stats.category, "name") else str(stats.category)
        if cat_name in by_cat:
            by_cat[cat_name].append(key)
    return by_cat


# Cache calculado uma vez no import
UNITS_BY_CATEGORY: dict[str, list[str]] = build_units_by_category()


# ============================================================
# HELPERS DE CONTAGEM
# ============================================================

def get_unit_category(unit_key: str) -> str:
    """Retorna o nome da categoria ("LAND", "NAVAL", "AIR") de um unit_key."""
    stats = UNIT_STATS.get(unit_key)
    if stats:
        return stats.category.name if hasattr(stats.category, "name") else "LAND"
    return "LAND"


def count_units_in_tile(planet, tile: tuple[int, int], owner_id: int | None = None) -> dict[str, int]:
    """
    Conta unidades por unit_key em um tile.
    Se owner_id for fornecido, filtra apenas stacks daquele owner.
    """
    counts: Counter[str] = Counter()
    if not planet:
        return dict(counts)

    for stack in planet.stacks.stacks_in_tile(tile):
        if owner_id is not None and stack.owner_id != owner_id:
            continue
        for unit in stack.units:
            counts[unit.unit_key] += 1

    return dict(counts)


def count_units_for_civ(planet, civ_id: int) -> dict[str, int]:
    """Conta TODAS as unidades de uma civilização por unit_key."""
    counts: Counter[str] = Counter()
    if not planet:
        return dict(counts)

    civ_stack_uids = planet.stacks.stack_uids_by_owner.get(civ_id, set())
    for uid in civ_stack_uids:
        stack = planet.stacks.get_stack(uid)
        if stack:
            for unit in stack.units:
                counts[unit.unit_key] += 1

    return dict(counts)


def group_counts_by_category(unit_counts: dict[str, int]) -> dict[str, int]:
    """Agrupa contagens de unit_key em contagens por categoria."""
    by_cat: dict[str, int] = defaultdict(int)
    for unit_key, count in unit_counts.items():
        cat = get_unit_category(unit_key)
        by_cat[cat] += count
    return dict(by_cat)


def format_units_by_category(unit_counts: dict[str, int]) -> str:
    """
    Formata um dict {unit_key: count} em string agrupada por categoria.
    Ex: "⚔️ LAND: 5 | ⚓ NAVAL: 2"
    """
    by_cat = group_counts_by_category(unit_counts)
    parts = []
    for cat in ("LAND", "NAVAL", "AIR"):
        c = by_cat.get(cat, 0)
        if c > 0:
            icon = CATEGORY_ICONS.get(cat, "")
            parts.append(f"{icon} {cat}: {c}")
    return " | ".join(parts) if parts else "No units present"
