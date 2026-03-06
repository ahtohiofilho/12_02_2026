# config/unit_stats.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class UnitCategory(Enum):
    LAND = auto()
    NAVAL = auto()
    AIR = auto()
    CIVILIAN = auto()
    # (opcional/futuro) SUB = auto()  # se você quiser distinguir submarinos de NAVAL


@dataclass(frozen=True)
class UnitStats:
    """
    Blueprint de uma unidade.

    Campos relevantes para o combate v2.1:
    - eficacia: valor BASE de combate (usado no resolver 1v1 existente).
    - range: alcance em tiles para participar como atacante remoto (ATTACK_TILE).
      * 0 = só o próprio tile (melee/local).
      * 1 = pode atacar tiles adjacentes.
    - layer: camada usada pelo combate v2.1 (ex.: "SURFACE", "AIR", "NAVAL").
    - can_evasive: capacidade intrínseca (contrato v2.1.1) para operar em postura EVASIVE.
      Se False, qualquer ordem pedindo EVASIVE deve ser normalizada para COMMITTED no runtime.
    """
    name: str
    category: UnitCategory
    cost: float
    eficacia: float
    movement: int
    sprite_key: str

    can_transport: bool = field(default=False, kw_only=True)
    is_non_combat: bool = field(default=False, kw_only=True)

    # Visão/UI
    vision_range: int = field(default=0, kw_only=True)

    # Combate v2.1 (remoto)
    range: int = field(default=0, kw_only=True)

    # Camada (para evolução futura; hoje pode ficar padrão)
    layer: str = field(default="SURFACE", kw_only=True)

    # ✅ Contrato 2.1.1: capacidade intrínseca para EVASIVE
    can_evasive: bool = field(default=False, kw_only=True)


UNIT_STATS: dict[str, UnitStats] = {
    # ------------------------------------------------------------------ #
    # LAND                                                                #
    # ------------------------------------------------------------------ #
    "light_infantry":       UnitStats(
        "Infantaria Leve", UnitCategory.LAND, 1.0, 1.0, 2, "infantry",
        range=0, layer="SURFACE",
    ),
    "mechanized_infantry":  UnitStats(
        "Infantaria Mecanizada", UnitCategory.LAND, 4.0, 2.5, 3, "mech_infantry",
        range=0, layer="SURFACE",
    ),
    "mbt":                  UnitStats(
        "Carro de Combate Principal", UnitCategory.LAND, 10.0, 7.5, 3, "mbt",
        range=0, layer="SURFACE",
    ),
    "support_vehicle":      UnitStats(
        "Veículo de Suporte", UnitCategory.LAND, 4.0, 2.0, 3, "support_vehicle",
        can_transport=True, range=0, layer="SURFACE",
    ),
    "atgm_team":            UnitStats(
        "Equipe ATGM", UnitCategory.LAND, 5.0, 3.0, 2, "atgm",
        range=0, layer="SURFACE",
    ),

    # ✅ Artilharia: exemplo de unidade remota (alcance 2)
    "sp_artillery":         UnitStats(
        "Artilharia Autopropulsada", UnitCategory.LAND, 8.0, 5.5, 1, "sp_artillery",
        range=2, layer="SURFACE",
    ),

    "shorad":               UnitStats(
        "Defesa AA Curto Alcance", UnitCategory.LAND, 6.0, 3.5, 2, "shorad",
        range=1, layer="SURFACE",
    ),

    # ------------------------------------------------------------------ #
    # AIR                                                                 #
    #   Regra pedida: todas AIR exceto transport_aircraft com can_evasive #
    # ------------------------------------------------------------------ #
    "fighter":              UnitStats(
        "Caça", UnitCategory.AIR, 8.0, 4.5, 8, "fighter",
        vision_range=1, range=1, layer="AIR",
        can_evasive=True,
    ),
    "strike_aircraft":      UnitStats(
        "Aeronave de Ataque", UnitCategory.AIR, 14.0, 7.0, 6, "strike",
        vision_range=1, range=1, layer="AIR",
        can_evasive=True,
    ),
    "ucav":                 UnitStats(
        "Drone de Ataque (UCAV)", UnitCategory.AIR, 7.0, 3.5, 7, "ucav",
        vision_range=1, range=1, layer="AIR",
        can_evasive=True,
    ),
    "transport_aircraft":   UnitStats(
        "Aeronave de Transporte", UnitCategory.AIR, 8.0, 2.5, 6, "transport_aircraft",
        can_transport=True, range=0, layer="AIR",
        can_evasive=False,  # ✅ exceção pedida
    ),

    # ------------------------------------------------------------------ #
    # NAVAL                                                               #
    # ------------------------------------------------------------------ #
    "frigate":              UnitStats(
        "Fragata/Corveta", UnitCategory.NAVAL, 18.0, 10.0, 3, "frigate",
        vision_range=1, range=1, layer="NAVAL",
    ),
    "destroyer":            UnitStats(
        "Destroyer", UnitCategory.NAVAL, 28.0, 16.0, 3, "destroyer",
        vision_range=1, range=1, layer="NAVAL",
    ),
    "aircraft_carrier":     UnitStats(
        "Porta-Aviões", UnitCategory.NAVAL, 50.0, 12.0, 2, "aircraft_carrier",
        can_transport=True, vision_range=1, range=1, layer="NAVAL",
    ),
    "submarine":            UnitStats(
        "Submarino", UnitCategory.NAVAL, 24.0, 14.0, 2, "submarine",
        range=1, layer="NAVAL",
    ),
    "amphibious_ship":      UnitStats(
        "Navio Anfíbio", UnitCategory.NAVAL, 12.0, 5.0, 3, "amphibious_ship",
        can_transport=True, range=1, layer="NAVAL",
    ),

    # ------------------------------------------------------------------ #
    # CIVILIAN                                                            #
    # ------------------------------------------------------------------ #
    "worker":               UnitStats(
        "Trabalhador", UnitCategory.CIVILIAN, 1.0, 0.2, 3, "worker",
        is_non_combat=True, range=0, layer="SURFACE",
    ),
}


# attacker_key -> {defender_key: multiplier}
ADVANTAGE_MAP: dict[str, dict[str, float]] = {
    # LAND
    "atgm_team":        {"mbt": 1.35},
    "mbt":              {"mechanized_infantry": 1.25, "light_infantry": 1.20, "support_vehicle": 1.15},
    "sp_artillery":     {"light_infantry": 1.25, "mechanized_infantry": 1.20, "shorad": 1.10},
    "light_infantry":   {"sp_artillery": 1.25, "shorad": 1.20, "atgm_team": 1.10},
    "shorad":           {"ucav": 1.35, "strike_aircraft": 1.20, "transport_aircraft": 1.25},

    # AIR
    "fighter":          {"strike_aircraft": 1.30, "ucav": 1.25, "transport_aircraft": 1.35},
    "strike_aircraft":  {"mbt": 1.25, "sp_artillery": 1.25, "frigate": 1.15, "destroyer": 1.10, "aircraft_carrier": 1.20},
    "ucav":             {"sp_artillery": 1.20, "mbt": 1.15, "support_vehicle": 1.15},

    # NAVAL
    "submarine":        {"destroyer": 1.25, "frigate": 1.20, "aircraft_carrier": 1.30, "amphibious_ship": 1.25},
    "destroyer":        {"frigate": 1.15, "submarine": 1.10, "aircraft_carrier": 1.10},
    "frigate":          {"submarine": 1.15, "amphibious_ship": 1.10},
}


def get_unit_stats(unit_key: str) -> UnitStats | None:
    return UNIT_STATS.get(unit_key)
