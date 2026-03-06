# core/combat_v2/api.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

Tile = tuple[int, int]


def normalize_evasion_mode(requested: str | None, *, can_evasive: bool) -> str:
    """
    Normaliza a postura pedida para o runtime, conforme contrato v2.1.1:

    - EVASIVE só é permitido se a unidade tiver capacidade intrínseca (can_evasive=True).
    - Caso contrário (ou se pedido inválido), força COMMITTED.

    Uso recomendado:
        effective = normalize_evasion_mode(cmd.extra.get("evasion_mode"), can_evasive=stats.can_evasive)
    """
    v = str(requested or "COMMITTED").upper()
    if v == "EVASIVE" and bool(can_evasive):
        return "EVASIVE"
    return "COMMITTED"


@dataclass(slots=True)
class UnitRuntime:
    """
    Runtime (execução) de uma unidade no combate v2.

    Consolidação p/ contrato 2.1.1:
    - EVASIVE é uma postura (evasion_mode), mas a elegibilidade é intrínseca (can_evasive).
    - Quem cria UnitRuntime (ex.: TurnEngine) deve chamar normalize_evasion_mode()
      e preencher evasion_mode já normalizado.
    """
    uid: str
    unit_key: str
    owner_id: int
    tile: Tile

    # Camada e alcance (para combate remoto/local)
    layer: str = "SURFACE"         # "SURFACE" | "AIR" | "NAVAL" | ...
    range: int = 0                 # alcance em tiles (0 = apenas mesmo tile)
    turns_per_tile: float = 999.0  # fonte da verdade de velocidade (entry cost)

    # Contrato 2.1.1: capacidade intrínseca para EVASIVE
    can_evasive: bool = False

    # Postura de engajamento (deve ser normalizada com base em can_evasive)
    evasion_mode: str = "COMMITTED"      # "EVASIVE" | "COMMITTED"
    primary_target_tile: Tile | None = None

    alive: bool = True
    attacked_this_round: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DuelOutcome:
    attacker_uid: str
    defender_uid: str
    attacker_killed: bool
    defender_killed: bool
    debug: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TileCombatReportV2:
    tile: Tile
    duels: list[DuelOutcome]
    killed_uids: list[str]
    stopped_by_max_duels: bool = False
