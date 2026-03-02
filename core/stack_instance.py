# core/stack_instance.py

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from .unit_instance import UnitInstance


@dataclass(slots=True)
class StackInstance:
    uid: str = field(default_factory=lambda: str(uuid4()))
    owner_id: int = 0
    tile: tuple[int, int] = (0, 0)
    units: list[UnitInstance] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.units
