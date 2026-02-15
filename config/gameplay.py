# config/gameplay.py

# --- Constantes de Geração de Mundo e Recursos ---

PRODUTIVIDADE_BASE = {
    'Meadow': 6, 'Forest': 5, 'Hills': 4, 'Savanna': 3, 'Coast': 3,
    'Desert': 2, 'Sea': 2, 'Mountains': 1, 'Ocean': 1, 'Ice': 0
}

MAPA_BIOMA_ALIMENTO = {
    'Meadow': 'Wheat', 'Forest': 'Rice', 'Hills': 'Corn', 'Savanna': 'Soybean',
    'Mountains': 'Barley', 'Desert': 'Sorghum', 'Coast': None, 'Sea': None,
    'Ocean': None, 'Ice': None
}

LETRAS_GREGAS = {
    "Alpha": "Α", "Beta": "Β", "Gamma": "Γ", "Delta": "Δ", "Epsilon": "Ε",
    "Zeta": "Ζ", "Eta": "Η", "Theta": "Θ", "Iota": "Ι", "Kappa": "Κ",
    "Lambda": "Λ", "Mu": "Μ", "Nu": "Ν", "Xi": "Ξ", "Omicron": "Ο", "Pi": "Π",
    "Rho": "Ρ", "Sigma": "Σ", "Tau": "Τ", "Upsilon": "Υ", "Phi": "Φ",
    "Chi": "Χ", "Psi": "Ψ", "Omega": "Ω"
}

# --- Constantes Militares e de Unidades ---

ALLOWED_BIOMES_PER_CATEGORY = {
    'land': ['Meadow', 'Forest', 'Savanna', 'Desert', 'Hills', 'Mountains', 'Ice'],
    'naval': ['Coast', 'Sea', 'Ocean'],
    'air': [
        'Meadow', 'Forest', 'Savanna', 'Hills', 'Mountains', 'Desert',
        'Coast', 'Sea', 'Ocean', 'Ice'
    ],
}

BASE_UNIT_COST = {
    'INFANTRY': 10.0,
    'TANK': 30.0,
    'ARTILLERY': 25.0,
    'SUPPORT_VEHICLE': 15.0,
    'WARSHIP': 50.0,
    'AIRCRAFT_CARRIER': 80.0,
    'SUBMARINE': 40.0,
    'AMPHIBIOUS_SHIP': 35.0,
    'FIGHTER': 40.0,
    'BOMBER': 60.0,
    'GUNSHIP': 50.0,
    'TRANSPORT_AIRCRAFT': 30.0,
}
