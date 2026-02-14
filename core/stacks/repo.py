from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from uuid import uuid4

from core.stack_instance import StackInstance
from core.unit_instance import UnitInstance


@dataclass(slots=True)
class StackRepository:
    """
    Storage/índices de stacks e unidades.
    Não conhece diplomacia, não conhece combate, não conhece grafo.
    Apenas mantém consistência de estado.
    """
    stacks_by_uid: dict[str, StackInstance]
    stack_uids_by_tile: dict[tuple[int, int], set[str]]
    stack_uids_by_owner: dict[int, set[str]]
    unit_uid_to_stack_uid: dict[str, str]

    def __init__(self):
        self.stacks_by_uid = {}
        self.stack_uids_by_tile = {}
        self.stack_uids_by_owner = {}
        self.unit_uid_to_stack_uid = {}

    # ---------- Query ----------
    def get_stack(self, stack_uid: str) -> StackInstance | None:
        return self.stacks_by_uid.get(stack_uid)

    def stacks_in_tile(self, tile: tuple[int, int]) -> list[StackInstance]:
        uids = self.stack_uids_by_tile.get(tile, set())
        return [self.stacks_by_uid[uid] for uid in uids if uid in self.stacks_by_uid]

    def civs_present_in_tile(self, tile: tuple[int, int]) -> set[int]:
        civs: set[int] = set()
        for s in self.stacks_in_tile(tile):
            if not s.is_empty():
                civs.add(s.owner_id)
        return civs

    # ---------- CRUD ----------
    def create_stack(self, owner_id: int, tile: tuple[int, int], *, stack_uid: str | None = None) -> StackInstance:
        uid = stack_uid or str(uuid4())
        if uid in self.stacks_by_uid:
            raise KeyError(f"stack_uid já existe: {uid}")

        s = StackInstance(uid=uid, owner_id=owner_id, tile=tile)
        self._index_stack(s)
        return s

    def delete_stack(self, stack_uid: str) -> None:
        s = self.get_stack(stack_uid)
        if not s:
            return
        self._deindex_stack(s)

    def add_unit_to_stack(self, stack_uid: str, unit_key: str, *, unit_uid: str | None = None) -> UnitInstance:
        s = self.get_stack(stack_uid)
        if s is None:
            raise KeyError(f"stack inexistente: {stack_uid}")

        u = UnitInstance(uid=unit_uid or str(uuid4()), unit_key=unit_key)
        if u.uid in self.unit_uid_to_stack_uid:
            raise KeyError(f"unit_uid já existe: {u.uid}")

        s.units.append(u)
        self.unit_uid_to_stack_uid[u.uid] = s.uid
        return u

    def remove_unit(self, unit_uid: str) -> bool:
        stack_uid = self.unit_uid_to_stack_uid.get(unit_uid)
        if not stack_uid:
            return False

        s = self.get_stack(stack_uid)
        if not s:
            self.unit_uid_to_stack_uid.pop(unit_uid, None)
            return False

        for i, u in enumerate(s.units):
            if u.uid == unit_uid:
                s.units.pop(i)
                self.unit_uid_to_stack_uid.pop(unit_uid, None)
                return True

        self.unit_uid_to_stack_uid.pop(unit_uid, None)
        return False

    # ---------- Split / Merge ----------
    def split_stack(self, source_stack_uid: str, unit_uids: list[str]) -> StackInstance:
        src = self.get_stack(source_stack_uid)
        if src is None:
            raise KeyError(f"stack inexistente: {source_stack_uid}")

        new_stack = self.create_stack(src.owner_id, src.tile)

        uid_set = set(unit_uids)
        moved: list[UnitInstance] = []
        remaining: list[UnitInstance] = []

        for u in src.units:
            (moved if u.uid in uid_set else remaining).append(u)

        src.units = remaining
        new_stack.units = moved

        for u in moved:
            self.unit_uid_to_stack_uid[u.uid] = new_stack.uid

        return new_stack

    def merge_stacks(self, stack_uids: list[str]) -> StackInstance:
        if not stack_uids:
            raise ValueError("stack_uids vazio")

        stacks = [self.get_stack(uid) for uid in stack_uids]
        if any(s is None for s in stacks):
            missing = [uid for uid, s in zip(stack_uids, stacks) if s is None]
            raise KeyError(f"stacks inexistentes: {missing}")

        dst = stacks[0]
        assert dst is not None

        owner = dst.owner_id
        tile = dst.tile
        for s in stacks[1:]:
            assert s is not None
            if s.owner_id != owner or s.tile != tile:
                raise ValueError("merge exige mesmo owner e mesmo tile")

        for s in stacks[1:]:
            assert s is not None
            dst.units.extend(s.units)
            for u in s.units:
                self.unit_uid_to_stack_uid[u.uid] = dst.uid
            self.delete_stack(s.uid)

        return dst

    # ---------- Move ----------
    def move_stack_position_only(self, stack_uid: str, dst_tile: tuple[int, int]) -> None:
        s = self.get_stack(stack_uid)
        if s is None:
            raise KeyError(f"stack inexistente: {stack_uid}")

        old_tile = s.tile
        if old_tile == dst_tile:
            return

        old_set = self.stack_uids_by_tile.get(old_tile)
        if old_set:
            old_set.discard(s.uid)
            if not old_set:
                self.stack_uids_by_tile.pop(old_tile, None)

        s.tile = dst_tile
        self.stack_uids_by_tile.setdefault(dst_tile, set()).add(s.uid)

    # ---------- Internal indexing ----------
    def _index_stack(self, s: StackInstance) -> None:
        self.stacks_by_uid[s.uid] = s
        self.stack_uids_by_tile.setdefault(s.tile, set()).add(s.uid)
        self.stack_uids_by_owner.setdefault(s.owner_id, set()).add(s.uid)
        for u in s.units:
            self.unit_uid_to_stack_uid[u.uid] = s.uid

    def _deindex_stack(self, s: StackInstance) -> None:
        self.stacks_by_uid.pop(s.uid, None)

        tile_set = self.stack_uids_by_tile.get(s.tile)
        if tile_set:
            tile_set.discard(s.uid)
            if not tile_set:
                self.stack_uids_by_tile.pop(s.tile, None)

        owner_set = self.stack_uids_by_owner.get(s.owner_id)
        if owner_set:
            owner_set.discard(s.uid)
            if not owner_set:
                self.stack_uids_by_owner.pop(s.owner_id, None)

        for u in s.units:
            self.unit_uid_to_stack_uid.pop(u.uid, None)
