# ga/core/military/types.py

from enum import Enum, auto
from dataclasses import dataclass
from config.gameplay import BASE_UNIT_COST


class UnitCategory(Enum):
    LAND = auto()
    NAVAL = auto()
    AIR = auto()


class UnitBlueprint(Enum):
    # Land
    INFANTRY = auto()
    TANK = auto()
    ARTILLERY = auto()
    SUPPORT_VEHICLE = auto()
    # Naval
    WARSHIP = auto()
    AIRCRAFT_CARRIER = auto()
    SUBMARINE = auto()
    AMPHIBIOUS_SHIP = auto()
    # Air
    FIGHTER = auto()
    BOMBER = auto()
    GUNSHIP = auto()
    TRANSPORT_AIRCRAFT = auto()


@dataclass(frozen=True)
class UnitStats:
    category: UnitCategory
    # Adicione outros stats base aqui (ataque, defesa, etc.) se necessário


# Mapeamento de Blueprints para seus stats base
# Isso substitui a necessidade de uma função get_unit_stats() com ifs
UNIT_STATS_MAP = {
    UnitBlueprint.INFANTRY: UnitStats(category=UnitCategory.LAND),
    UnitBlueprint.TANK: UnitStats(category=UnitCategory.LAND),
    UnitBlueprint.ARTILLERY: UnitStats(category=UnitCategory.LAND),
    UnitBlueprint.SUPPORT_VEHICLE: UnitStats(category=UnitCategory.LAND),
    UnitBlueprint.WARSHIP: UnitStats(category=UnitCategory.NAVAL),
    UnitBlueprint.AIRCRAFT_CARRIER: UnitStats(category=UnitCategory.NAVAL),
    UnitBlueprint.SUBMARINE: UnitStats(category=UnitCategory.NAVAL),
    UnitBlueprint.AMPHIBIOUS_SHIP: UnitStats(category=UnitCategory.NAVAL),
    UnitBlueprint.FIGHTER: UnitStats(category=UnitCategory.AIR),
    UnitBlueprint.BOMBER: UnitStats(category=UnitCategory.AIR),
    UnitBlueprint.GUNSHIP: UnitStats(category=UnitCategory.AIR),
    UnitBlueprint.TRANSPORT_AIRCRAFT: UnitStats(category=UnitCategory.AIR),
}


def get_unit_stats(unit_type: str | UnitBlueprint) -> UnitStats | None:
    """Retorna os stats base para um tipo de unidade."""
    if isinstance(unit_type, str):
        try:
            unit_type = UnitBlueprint[unit_type]
        except KeyError:
            return None
    return UNIT_STATS_MAP.get(unit_type)


def blueprint_to_unit_type(bp: UnitBlueprint) -> str:
    """Converte um UnitBlueprint para seu nome em string."""
    return bp.name


def get_unit_cost(unit_type: str, base_costs=None) -> float:
    """Retorna o custo de uma unidade a partir de seu nome."""
    costs = base_costs or BASE_UNIT_COST
    return costs.get(unit_type, 0.0)


def can_unit_be_produced_in_biome(unit_blueprint: UnitBlueprint, biome: str, has_water_access: bool) -> bool:
    """Verifica se uma unidade pode ser produzida em um determinado bioma."""
    from config.gameplay import ALLOWED_BIOMES_PER_CATEGORY

    stats = get_unit_stats(unit_blueprint)
    if not stats:
        return False

    category_name = stats.category.name.lower()  # 'land', 'naval', 'air'

    if stats.category == UnitCategory.NAVAL:
        # Unidades navais precisam de acesso à água (bioma costeiro ou adjacente a água)
        return has_water_access

    allowed_biomes = ALLOWED_BIOMES_PER_CATEGORY.get(category_name, [])
    return biome in allowed_biomes
