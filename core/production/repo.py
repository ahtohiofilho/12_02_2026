from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterable
from core.production.queue import QueueItem, QueueItemType

Tile = tuple[int, int]

@dataclass(slots=True)
class ProvinceQueue:
    tile: Tile
    items: list[QueueItem] = field(default_factory=list)

class ProductionQueueRepository:
    def __init__(self):
        self._by_tile: dict[Tile, ProvinceQueue] = {}

    def ensure(self, tile: Tile) -> ProvinceQueue:
        q = self._by_tile.get(tile)
        if q is None:
            q = ProvinceQueue(tile=tile)
            self._by_tile[tile] = q
        return q

    def items(self, tile: Tile) -> list[QueueItem]:
        return list(self.ensure(tile).items)

    def add(self, tile: Tile, item: QueueItem) -> None:
        self.ensure(tile).items.append(item)

    def remove_by_uid(self, tile: Tile, uid: str) -> bool:
        q = self.ensure(tile)
        for i, it in enumerate(q.items):
            if it.uid == uid:
                q.items.pop(i)
                return True
        return False

    def clear(self, tile: Tile) -> int:
        q = self.ensure(tile)
        n = len(q.items)
        q.items.clear()
        return n
