# config/movement_costs.py
"""
Custo de entrada em tile (em turnos) por unidade e bioma.
Quanto MAIOR o valor, mais LENTO o terreno para aquela unidade.
"""

LAND_MOVEMENT_COSTS: dict[str, dict[str, int]] = {
    "light_infantry": {
        "Meadow": 4, "Savanna": 5, "Forest": 6, "Hills": 7,
        "Desert": 6, "Mountains": 9, "Ice": 11,
    },
    "mechanized_infantry": {
        "Meadow": 2, "Savanna": 3, "Forest": 3, "Hills": 4,
        "Desert": 3, "Mountains": 5, "Ice": 7,
    },
    "mbt": {
        "Meadow": 2, "Savanna": 3, "Forest": 3, "Hills": 4,
        "Desert": 3, "Mountains": 5, "Ice": 6,
    },
    "atgm_team": {
        "Meadow": 5, "Savanna": 6, "Forest": 7, "Hills": 8,
        "Desert": 8, "Mountains": 11, "Ice": 13,
    },
    "sp_artillery": {
        "Meadow": 6, "Savanna": 8, "Forest": 9, "Hills": 10,
        "Desert": 9, "Mountains": 14, "Ice": 16,
    },
    "shorad": {
        "Meadow": 4, "Savanna": 5, "Forest": 6, "Hills": 7,
        "Desert": 6, "Mountains": 9, "Ice": 11,
    },
    "support_vehicle": {
        "Meadow": 2, "Savanna": 3, "Forest": 3, "Hills": 4,
        "Desert": 3, "Mountains": 5, "Ice": 8,
    },
    "worker": {
        "Meadow": 3, "Savanna": 4, "Forest": 5, "Hills": 6,
        "Desert": 5, "Mountains": 8, "Ice": 10,
    },
}

NAVAL_MOVEMENT_COSTS: dict[str, dict[str, int]] = {
    "frigate":          {"Ocean": 2, "Sea": 3, "Coast": 5},
    "destroyer":        {"Ocean": 2, "Sea": 3, "Coast": 5},
    "submarine":        {"Ocean": 2, "Sea": 3, "Coast": 5},
    "amphibious_ship":  {"Ocean": 4, "Sea": 6, "Coast": 10},
    "aircraft_carrier":  {"Ocean": 4, "Sea": 6, "Coast": 10},
}

AIR_MOVEMENT_COSTS: dict[str, int] = {
    "fighter": 1,
    "strike_aircraft": 1,
    "ucav": 1,
    "transport_aircraft": 2,
}


def get_unit_domain(unit_key: str) -> str:
    """Retorna 'land', 'naval' ou 'air'."""
    if unit_key in LAND_MOVEMENT_COSTS:
        return "land"
    if unit_key in NAVAL_MOVEMENT_COSTS:
        return "naval"
    if unit_key in AIR_MOVEMENT_COSTS:
        return "air"
    return "land"


def get_entry_cost(unit_key: str, biome: str) -> int | None:
    """
    Custo (em turnos) para a unidade entrar num tile daquele bioma.
    Retorna None se o bioma for inacessível.
    """
    # Aéreo — custo fixo, ignora bioma
    if unit_key in AIR_MOVEMENT_COSTS:
        return AIR_MOVEMENT_COSTS[unit_key]

    # Terrestre
    if unit_key in LAND_MOVEMENT_COSTS:
        return LAND_MOVEMENT_COSTS[unit_key].get(biome)

    # Naval
    if unit_key in NAVAL_MOVEMENT_COSTS:
        return NAVAL_MOVEMENT_COSTS[unit_key].get(biome)

    return None


def get_stack_entry_cost(unit_keys: list[str], biome: str) -> int | None:
    """
    Custo de entrada para uma stack = unidade MAIS LENTA (max).
    Retorna None se qualquer unidade não puder entrar.
    """
    worst = 0
    for key in unit_keys:
        cost = get_entry_cost(key, biome)
        if cost is None:
            return None
        worst = max(worst, cost)
    return worst
