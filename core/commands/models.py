# core/commands/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional
from uuid import uuid4

Tile = tuple[int, int]


class CommandType(Enum):
    MOVE = auto()
    ATTACK = auto()  # futuro: distinção explícita
    HOLD = auto()  # futuro: pular turno
    SPLIT = auto()  # futuro: dividir stack
    MERGE = auto()  # futuro: juntar stacks
    TRANSPORT = auto()  # futuro: embarcar/desembarcar


class CommandStatus(Enum):
    PENDING = auto()
    SUBMITTED = auto()  # já submetido ao TurnEngine
    RESOLVED = auto()
    CANCELLED = auto()
    INVALID = auto()


@dataclass(slots=True)
class UnitCommand:
    """
    Um comando pendente para uma stack.

    Princípio: o jogador pode dar UM comando por stack por turno.
    O CommandManager coleta todos e no fim do turno submete ao TurnEngine.
    """
    uid: str = field(default_factory=lambda: str(uuid4()))
    command_type: CommandType = CommandType.MOVE
    stack_uid: str = ""
    owner_civ_id: int = 0

    # Dados específicos do comando
    origin: Optional[Tile] = None
    destination: Optional[Tile] = None
    path: Optional[list[Tile]] = None

    # Estado
    status: CommandStatus = CommandStatus.PENDING

    # Extensível para comandos futuros
    extra: dict[str, Any] = field(default_factory=dict)
