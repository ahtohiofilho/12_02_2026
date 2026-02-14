# config/unit_stats.py

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import FrozenSet


# ==============================================================================
# 1. ESTRUTURA (Refatorado com 'eficacia')
# ==============================================================================

class UnitCategory(Enum):
    LAND = auto()
    NAVAL = auto()
    AIR = auto()
    CIVILIAN = auto()


@dataclass(frozen=True)
class UnitStats:
    """Blueprint de uma unidade, usando 'eficacia' para combate."""
    name: str
    category: UnitCategory
    cost: float  # Custo de produção (inclui eficácia + utilidade)
    eficacia: float  # Eficácia de combate pura
    movement: int  # Pontos de movimento por turno
    sprite_key: str

    can_transport: bool = field(default=False, kw_only=True)
    is_non_combat: bool = field(default=False, kw_only=True)
    long_range: bool = field(default=False, kw_only=True)


# ==============================================================================
# 2. BANCO DE DADOS DE UNIDADES (Onde você vai calibrar o jogo)
# ==============================================================================

UNIT_STATS: dict[str, UnitStats] = {
    # --- Unidades Terrestres ---
    "infantry": UnitStats(name="Infantaria", category=UnitCategory.LAND, cost=1.0, eficacia=1.0, movement=2,
                          sprite_key="infantry"),
    "tank": UnitStats(name="Tanque", category=UnitCategory.LAND, cost=10.0, eficacia=8.0, movement=4,
                      sprite_key="tank"),
    "artillery": UnitStats(name="Artilharia", category=UnitCategory.LAND, cost=8.0, eficacia=6.0, movement=1,
                           sprite_key="artillery", long_range=True),
    "support_vehicle": UnitStats(name="Veículo de Suporte", category=UnitCategory.LAND, cost=4.0, eficacia=3.0,
                                 movement=4, sprite_key="support_vehicle", is_non_combat=True, can_transport=True),

    # --- Unidades Navais ---
    "warship": UnitStats(name="Navio de Guerra", category=UnitCategory.NAVAL, cost=20.0, eficacia=15.0, movement=3,
                         sprite_key="warship"),
    "aircraft_carrier": UnitStats(name="Porta-Aviões", category=UnitCategory.NAVAL, cost=50.0, eficacia=30.0,
                                  movement=2, sprite_key="aircraft_carrier", is_non_combat=True, can_transport=True),
    "submarine": UnitStats(name="Submarino", category=UnitCategory.NAVAL, cost=15.0, eficacia=10.0, movement=2,
                           sprite_key="submarine"),
    "amphibious_ship": UnitStats(name="Navio Anfíbio", category=UnitCategory.NAVAL, cost=12.0, eficacia=8.0, movement=3,
                                 sprite_key="amphibious_ship", is_non_combat=True, can_transport=True),

    # --- Unidades Aéreas ---
    "fighter": UnitStats(name="Caça", category=UnitCategory.AIR, cost=6.0, eficacia=4.0, movement=8,
                         sprite_key="fighter"),
    "bomber": UnitStats(name="Bombardeiro", category=UnitCategory.AIR, cost=18.0, eficacia=12.0, movement=5,
                        sprite_key="bomber", long_range=True),
    "gunship": UnitStats(name="Canhoneira", category=UnitCategory.AIR, cost=12.0, eficacia=8.0, movement=6,
                         sprite_key="gunship"),
    "transport_aircraft": UnitStats(name="Aeronave de Transporte", category=UnitCategory.AIR, cost=8.0, eficacia=5.0,
                                    movement=5, sprite_key="transport_aircraft", is_non_combat=True,
                                    can_transport=True),

    # --- Unidades Civis ---
    "worker": UnitStats(name="Trabalhador", category=UnitCategory.CIVILIAN, cost=1.0, eficacia=0.0, movement=3,
                        sprite_key="worker", is_non_combat=True),
}

# ==============================================================================
# 3. SISTEMA DE VANTAGENS (Modificador sobre a 'eficacia')
# ==============================================================================

ADVANTAGE_MULTIPLIER: float = 1.5
ADVANTAGE_MAP: dict[str, FrozenSet[str]] = {
    "infantry": frozenset({"artillery"}),
    "tank": frozenset({"infantry"}),
    "artillery": frozenset({"tank", "warship"}),
    "warship": frozenset({"submarine", "fighter"}),
    "submarine": frozenset({"aircraft_carrier", "amphibious_ship"}),
    "fighter": frozenset({"bomber", "gunship", "transport_aircraft"}),
    "bomber": frozenset({"warship", "artillery", "aircraft_carrier", "tank"}),
    "gunship": frozenset({"tank", "infantry", "submarine"}),
}


# ==============================================================================
# 4. FUNÇÕES AUXILIARES (Adaptadas para 'eficacia')
# ==============================================================================

def get_unit_stats(unit_key: str) -> UnitStats | None:
    """Retorna o blueprint de stats para uma unidade, dado sua chave."""
    return UNIT_STATS.get(unit_key)


def calcular_eficacia_em_combate(attacker_key: str, defender_key: str) -> float:
    """
    Calcula a eficácia real de uma unidade em combate, aplicando o bônus de vantagem.
    """
    stats = get_unit_stats(attacker_key)
    if not stats or stats.is_non_combat:
        return 0.0

    base_eficacia = stats.eficacia
    advantages = ADVANTAGE_MAP.get(attacker_key, frozenset())

    if defender_key in advantages:
        return base_eficacia * ADVANTAGE_MULTIPLIER

    return base_eficacia
