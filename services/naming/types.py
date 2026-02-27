# services/naming/types.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True, slots=True)
class NamingContext:
    seed: Optional[int] = None
    sanitizer: str = "western"   # "western" (default), "ascii", "unicode"
    capitalizar: bool = True
    kind: str = "province"
    biome: Optional[str] = None


class NameGenerator(Protocol):
    culture: str
    def province(self, ctx: NamingContext | None = None) -> str: ...
