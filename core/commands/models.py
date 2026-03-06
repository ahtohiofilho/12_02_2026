# core/commands/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional
from uuid import uuid4

Tile = tuple[int, int]


class CommandType(Enum):
    """
    Tipos de comando para stacks.

    Notas:
    - MOVE: deslocamento físico (multi-turno via path/remaining_path).
    - ATTACK_TILE: ordem explícita de atacar um tile (sem mover necessariamente).
      Usado pelo combate v2 para construir pools remotos sem "pull".
    - ATTACK: reservado/legado (se você já usa para algo diferente, mantenha).
    """
    MOVE = auto()
    ATTACK = auto()          # legado/futuro (p.ex. "ataque contextual")
    ATTACK_TILE = auto()     # ✅ NOVO: ordem explícita (contrato combate v2.1)
    HOLD = auto()            # futuro: pular turno
    SPLIT = auto()           # futuro: dividir stack
    MERGE = auto()           # futuro: juntar stacks
    TRANSPORT = auto()       # futuro: embarcar/desembarcar
    FOUND_PROVINCE = auto()


class CommandStatus(Enum):
    PENDING = auto()
    SUBMITTED = auto()       # já submetido ao TurnEngine neste turno
    RESOLVED = auto()
    CANCELLED = auto()
    INVALID = auto()


@dataclass(slots=True)
class UnitCommand:
    """
    Um comando pendente para uma stack.

    Suporta comandos multi-turno: o path completo é armazenado,
    e remaining_path é atualizado a cada turno conforme a stack avança.
    accumulated_budget guarda o "tempo acumulado" entre turnos para
    unidades lentas que precisam de mais de 1 turno para cruzar 1 tile.

    Campos para ATTACK_TILE:
      - destination pode ser usado como target_tile (por compatibilidade),
        mas prefira extra["target_tile"].
      - extra["target_tile"]: Tile (obrigatório para ATTACK_TILE)
      - extra["target_layer"]: str | None (opcional; p.ex. "SURFACE"/"AIR")
      - extra["explicit_attack"]: bool (recomendado True; facilita debug)
      - extra["evasion_mode"]: "EVASIVE"|"COMMITTED" (opcional)
    """
    uid: str = field(default_factory=lambda: str(uuid4()))
    command_type: CommandType = CommandType.MOVE
    stack_uid: str = ""
    owner_civ_id: int = 0

    # Dados específicos do comando
    origin: Optional[Tile] = None
    destination: Optional[Tile] = None
    path: Optional[list[Tile]] = None

    # ── Movimento multi-turno ──
    remaining_path: Optional[list[Tile]] = None
    accumulated_budget: int = 0  # turnos acumulados aguardando cruzar tile caro

    # Estado
    status: CommandStatus = CommandStatus.PENDING

    # Extensível para comandos futuros
    extra: dict[str, Any] = field(default_factory=dict)

    # ─────────────────────────────────────────────────────────────
    # Helpers seguros (não obrigatórios, mas reduzem bugs)
    # ─────────────────────────────────────────────────────────────
    def target_tile(self) -> Optional[Tile]:
        """
        Para ATTACK_TILE, retorna o tile alvo.
        Para outros comandos, pode retornar destination.
        """
        tt = self.extra.get("target_tile")
        if isinstance(tt, (list, tuple)) and len(tt) >= 2:
            return (int(tt[0]), int(tt[1]))
        if self.destination is None:
            return None
        return (int(self.destination[0]), int(self.destination[1]))

    def evasion_mode(self) -> str:
        """
        Postura de engajamento do comando.
        Default: COMMITTED.
        """
        v = self.extra.get("evasion_mode", "COMMITTED")
        v = str(v or "COMMITTED").upper()
        return "EVASIVE" if v == "EVASIVE" else "COMMITTED"
