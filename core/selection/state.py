# core/selection/state.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

Tile = tuple[int, int]


@dataclass(slots=True)
class SelectionState:
    """
    Estado de seleção do jogador.

    Regra: apenas UMA stack selecionada por vez.
    Futuro: pode expandir para multi-select (shift+click).
    """
    selected_stack_uid: Optional[str] = None
    selected_tile: Optional[Tile] = None

    # Preview de caminho (para overlay visual)
    preview_path: Optional[list[Tile]] = None

    def select_stack(self, stack_uid: str, tile: Tile) -> None:
        self.selected_stack_uid = stack_uid
        self.selected_tile = tile
        self.preview_path = None

    def clear(self) -> None:
        self.selected_stack_uid = None
        self.selected_tile = None
        self.preview_path = None

    @property
    def has_selection(self) -> bool:
        return self.selected_stack_uid is not None
