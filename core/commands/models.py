# core/commands/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional
from uuid import uuid4

Tile = tuple[int, int]


class CommandType(Enum):
    MOVE = auto()
    ATTACK = auto()      # futuro: distinção explícita
    HOLD = auto()         # futuro: pular turno
    SPLIT = auto()        # futuro: dividir stack
    MERGE = auto()        # futuro: juntar stacks
    TRANSPORT = auto()    # futuro: embarcar/desembarcar
    FOUND_PROVINCE = auto()


class CommandStatus(Enum):
    PENDING = auto()
    SUBMITTED = auto()    # já submetido ao TurnEngine neste turno
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
