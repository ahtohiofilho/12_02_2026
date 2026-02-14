from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass(slots=True)
class UnitInstance:
    uid: str = field(default_factory=lambda: str(uuid4()))
    unit_key: str = "infantry"
