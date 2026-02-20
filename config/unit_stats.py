# config/unit_stats.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class UnitCategory(Enum):
    LAND = auto()
    NAVAL = auto()
    AIR = auto()
    CIVILIAN = auto()


@dataclass(frozen=True)
class UnitStats:
    """Blueprint de uma unidade, usando 'eficacia' como valor BASE de combate."""
    name: str
    category: UnitCategory
    cost: float
    eficacia: float
    movement: int
    sprite_key: str

    can_transport: bool = field(default=False, kw_only=True)
    is_non_combat: bool = field(default=False, kw_only=True)
    long_range: bool = field(default=False, kw_only=True)


UNIT_STATS: dict[str, UnitStats] = {
    # --- LAND ---
    "light_infantry": UnitStats("Infantaria Leve", UnitCategory.LAND, 1.0, 1.0, 2, "infantry"),
    "mechanized_infantry": UnitStats("Infantaria Mecanizada", UnitCategory.LAND, 4.0, 2.5, 3, "mech_infantry"),
    "mbt": UnitStats("Carro de Combate Principal", UnitCategory.LAND, 10.0, 7.5, 3, "mbt"),
    "atgm_team": UnitStats("Equipe ATGM", UnitCategory.LAND, 5.0, 3.0, 2, "atgm", long_range=True),
    "sp_artillery": UnitStats("Artilharia Autopropulsada", UnitCategory.LAND, 8.0, 5.5, 1, "sp_artillery", long_range=True),
    "shorad": UnitStats("Defesa AA Curto Alcance (SHORAD)", UnitCategory.LAND, 6.0, 3.5, 2, "shorad", long_range=True),
    "support_vehicle": UnitStats("Veículo de Suporte", UnitCategory.LAND, 4.0, 2.0, 3, "support_vehicle", can_transport=True),

    # --- AIR ---
    "fighter": UnitStats("Caça", UnitCategory.AIR, 8.0, 4.5, 8, "fighter", long_range=True),
    "strike_aircraft": UnitStats("Aeronave de Ataque", UnitCategory.AIR, 14.0, 7.0, 6, "strike", long_range=True),
    "ucav": UnitStats("Drone de Ataque (UCAV)", UnitCategory.AIR, 7.0, 3.5, 7, "ucav", long_range=True),
    "transport_aircraft": UnitStats("Aeronave de Transporte", UnitCategory.AIR, 8.0, 2.5, 6, "transport_aircraft", can_transport=True, long_range=True),

    # --- NAVAL ---
    "frigate": UnitStats("Fragata/Corveta", UnitCategory.NAVAL, 18.0, 10.0, 3, "frigate", long_range=True),
    "destroyer": UnitStats("Destroyer", UnitCategory.NAVAL, 28.0, 16.0, 3, "destroyer", long_range=True),
    "submarine": UnitStats("Submarino", UnitCategory.NAVAL, 24.0, 14.0, 2, "submarine", long_range=True),
    "amphibious_ship": UnitStats("Navio Anfíbio", UnitCategory.NAVAL, 12.0, 5.0, 3, "amphibious_ship", can_transport=True, long_range=True),
    "aircraft_carrier": UnitStats("Porta-Aviões", UnitCategory.NAVAL, 50.0, 12.0, 2, "aircraft_carrier", can_transport=True, long_range=True),

    # --- CIVILIAN ---
    "worker": UnitStats("Trabalhador", UnitCategory.CIVILIAN, 1.0, 0.2, 3, "worker", is_non_combat=False),
}


# attacker_key -> {defender_key: multiplier}
ADVANTAGE_MAP: dict[str, dict[str, float]] = {
    # LAND
    "atgm_team": {"mbt": 1.35},
    "mbt": {"mechanized_infantry": 1.25, "light_infantry": 1.20, "support_vehicle": 1.15},
    "sp_artillery": {"light_infantry": 1.25, "mechanized_infantry": 1.20, "shorad": 1.10},
    "light_infantry": {"sp_artillery": 1.25, "shorad": 1.20, "atgm_team": 1.10},
    "shorad": {"ucav": 1.35, "strike_aircraft": 1.20, "transport_aircraft": 1.25},

    # AIR
    "fighter": {"strike_aircraft": 1.30, "ucav": 1.25, "transport_aircraft": 1.35},
    "strike_aircraft": {"mbt": 1.25, "sp_artillery": 1.25, "frigate": 1.15, "destroyer": 1.10, "aircraft_carrier": 1.20},
    "ucav": {"sp_artillery": 1.20, "mbt": 1.15, "support_vehicle": 1.15},

    # NAVAL
    "submarine": {"destroyer": 1.25, "frigate": 1.20, "aircraft_carrier": 1.30, "amphibious_ship": 1.25},
    "destroyer": {"frigate": 1.15, "submarine": 1.10, "aircraft_carrier": 1.10},
    "frigate": {"submarine": 1.15, "amphibious_ship": 1.10},
}


def get_unit_stats(unit_key: str) -> UnitStats | None:
    return UNIT_STATS.get(unit_key)
