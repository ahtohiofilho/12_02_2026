# core/combat_v2/tables.py
from __future__ import annotations

"""
Tabelas (design) para o combate v2.

Contrato (v2.1):
- T4: exposição local (range(A)==0) → multiplicador linear no peso de seleção do defensor
- T5: preferência estratégica remota (range(A)>0) → multiplicador linear no peso de seleção do defensor
- T3 (aqui como helper): multiplicador de evasive contra o ALVO (reduz chance de abate contra alvos EVASIVE)

Observações:
- Chaves são unit_key (as mesmas de config.unit_stats.UNIT_STATS).
- Fallback: 1.0 para multiplicadores; valores fora da tabela não quebram o jogo.
"""

# ─────────────────────────────────────────────────────────────
# T4 — m_local_exposure[defender_unit_key] (range(A)==0)
# ─────────────────────────────────────────────────────────────
M_LOCAL_EXPOSURE: dict[str, float] = {
    # LAND
    "light_infantry": 1.20,
    "mechanized_infantry": 1.10,
    "mbt": 1.05,
    "support_vehicle": 1.00,
    "atgm_team": 0.90,
    "sp_artillery": 0.85,
    "shorad": 0.90,

    # AIR
    "fighter": 0.95,
    "strike_aircraft": 0.95,
    "ucav": 0.95,
    "transport_aircraft": 0.90,

    # NAVAL
    "frigate": 1.00,
    "destroyer": 1.00,
    "aircraft_carrier": 0.90,
    "submarine": 0.85,
    "amphibious_ship": 0.95,

    # CIVILIAN
    "worker": 1.05,
}


def local_exposure(unit_key: str) -> float:
    """T4: multiplicador linear aplicado quando range(A)==0."""
    return float(M_LOCAL_EXPOSURE.get(str(unit_key), 1.0))


# ─────────────────────────────────────────────────────────────
# T5 — m_remote_preference[defender_unit_key] (range(A)>0)
# ─────────────────────────────────────────────────────────────
M_REMOTE_PREFERENCE: dict[str, float] = {
    # LAND
    "light_infantry": 0.90,
    "mechanized_infantry": 1.00,
    "mbt": 1.05,
    "support_vehicle": 1.10,
    "atgm_team": 1.05,
    "sp_artillery": 1.20,
    "shorad": 1.20,

    # AIR
    "fighter": 1.05,
    "strike_aircraft": 1.15,
    "ucav": 1.10,
    "transport_aircraft": 1.25,

    # NAVAL
    "frigate": 1.10,
    "destroyer": 1.15,
    "aircraft_carrier": 1.30,
    "submarine": 1.20,
    "amphibious_ship": 1.20,

    # CIVILIAN
    "worker": 1.10,
}


def remote_preference(unit_key: str) -> float:
    """T5: multiplicador linear aplicado quando range(A)>0."""
    return float(M_REMOTE_PREFERENCE.get(str(unit_key), 1.0))


# ─────────────────────────────────────────────────────────────
# T3 — Multiplicador de evasive (chance de abate CONTRA o alvo EVASIVE)
# ─────────────────────────────────────────────────────────────
# Nesta versão: global e simples.
# Se você quiser, pode trocar por tabela por unit_key (ex.: aeronaves mais evasivas).
K_EVASIVE_GLOBAL: float = 0.75


def evasive_multiplier_against_target(unit_key: str | None = None) -> float:
    """
    Retorna k_evasive ∈ (0, 1], multiplicador na probabilidade de abate
    quando o ALVO está em EVASIVE.

    `unit_key` está aqui para futura especialização por tipo; por ora é global.
    """
    _ = unit_key  # reservado
    k = float(K_EVASIVE_GLOBAL)
    if k <= 0.0:
        return 0.01
    if k > 1.0:
        return 1.0
    return k


# ─────────────────────────────────────────────────────────────
# (Opcional) Distância remota leve (contrato 9.7)
# ─────────────────────────────────────────────────────────────
# Habilite se desejar: em vez de depender do unit_key, dá um viés leve p/ alvos mais distantes.
ENABLE_REMOTE_DISTANCE_BONUS: bool = False

M_REMOTE_DISTANCE: dict[int, float] = {
    0: 1.00,
    1: 1.00,
    2: 1.05,  # usado como "2 ou mais"
}


def remote_distance_multiplier(dist_tiles: int) -> float:
    if not ENABLE_REMOTE_DISTANCE_BONUS:
        return 1.0
    d = int(dist_tiles)
    if d <= 0:
        return float(M_REMOTE_DISTANCE[0])
    if d == 1:
        return float(M_REMOTE_DISTANCE[1])
    return float(M_REMOTE_DISTANCE[2])
