# core/production/queue.py
from __future__ import annotations

from enum import Enum, auto
from dataclasses import dataclass, field
from uuid import uuid4
from typing import Any


class QueueItemType(Enum):
    WORKER = auto()
    MILITARY = auto()
    DETACH_WORKER = auto()   # ← novo: destacar worker fixo → unidade móvel


@dataclass(slots=True)
class QueueItem:
    """Represents an item in a province production queue."""
    uid: str = field(default_factory=lambda: str(uuid4()))
    item_type: QueueItemType = QueueItemType.WORKER
    data: Any | None = None  # unit_key (str) para MILITARY; None para WORKER/DETACH_WORKER
    cost: float = 0.0
    paid: float = 0.0

    @property
    def remaining(self) -> float:
        return max(0.0, float(self.cost) - float(self.paid))

    @property
    def progress(self) -> float:
        total = float(self.cost)
        if total <= 0:
            return 1.0
        return min(1.0, max(0.0, float(self.paid) / total))
