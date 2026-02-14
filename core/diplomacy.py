from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class Relation(Enum):
    ALLY = auto()
    ENEMY = auto()
    NEUTRAL = auto()


@dataclass(slots=True)
class DiplomacyMatrix:
    relations: dict[tuple[int, int], Relation] = field(default_factory=dict)

    def set_relation(self, a: int, b: int, rel: Relation) -> None:
        if a == b:
            return
        self.relations[(a, b)] = rel
        self.relations[(b, a)] = rel

    def relation(self, a: int, b: int) -> Relation:
        if a == b:
            return Relation.ALLY
        return self.relations.get((a, b), Relation.NEUTRAL)
