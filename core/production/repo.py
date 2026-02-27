# core/production/repo.py
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
        """Retorna (ou cria) a fila do tile. Use apenas quando for escrever."""
        q = self._by_tile.get(tile)
        if q is None:
            q = ProvinceQueue(tile=tile)
            self._by_tile[tile] = q
        return q

    def get(self, tile: Tile) -> ProvinceQueue | None:
        """Retorna a fila do tile sem criá-la. Use para leitura."""
        return self._by_tile.get(tile)

    def items(self, tile: Tile) -> list[QueueItem]:
        """Leitura segura: não cria entrada se o tile não tiver fila."""
        q = self._by_tile.get(tile)   # ← era ensure(); corrigido para get()
        return list(q.items) if q else []

    def add(self, tile: Tile, item: QueueItem) -> None:
        self.ensure(tile).items.append(item)

    def remove_by_uid(self, tile: Tile, uid: str) -> bool:
        q = self._by_tile.get(tile)   # ← não cria fila só para remover
        if q is None:
            return False
        for i, it in enumerate(q.items):
            if it.uid == uid:
                q.items.pop(i)
                return True
        return False

    def clear(self, tile: Tile) -> int:
        q = self._by_tile.get(tile)   # ← não cria fila só para limpar
        if q is None:
            return 0
        n = len(q.items)
        q.items.clear()
        return n
