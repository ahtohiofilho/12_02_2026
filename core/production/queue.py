# ga/core/production/queue.py

from enum import Enum, auto
from dataclasses import dataclass, field
from uuid import uuid4
from typing import Any

@dataclass
class QueueItemType(Enum):
    WORKER = auto()
    MILITARY = auto()
    # Adicione outros tipos aqui, como 'BUILDING'

@dataclass
class QueueItem:
    """Representa um item na fila de produção de uma província."""
    uid: str = field(default_factory=lambda: str(uuid4()))
    item_type: QueueItemType = QueueItemType.WORKER
    data: Any | None = None  # Ex: UnitBlueprint para unidades
    cost: float = 0.0
