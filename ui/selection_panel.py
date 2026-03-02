# ui/selection_panel.py
"""
Painel lateral exibido quando o jogador seleciona uma stack no mapa.
Mostra as unidades da stack, stats de movimento e comando pendente.
Permite cancelar comando ou dar novo comando (via clique direito no mapa).

✅ Melhorias:
- Seletor "Stacks Here" agora mostra a BANDEIRA da civilização ao lado de cada stack.
- Mantém reuso de widgets (não recria tudo sempre).
- set_active_stack_uid funciona com a nova estrutura (row -> botão + label da bandeira).
"""
from __future__ import annotations

import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QFrame, QSizePolicy, QListWidget,
    QListWidgetItem, QPushButton, QScrollArea,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QPixmap

from config.unit_stats import get_unit_stats
from core.commands.pathfinding import max_movement_for_stack, movement_budget_for_stack
from ui.widgets import compact_button
from ui.province.military_ui import (
    UNIT_ICONS,
    UNIT_COLORS,
    UNIT_DISPLAY_NAMES,
    CATEGORY_ICONS,
    get_unit_category,
)
from core.diplomacy import Relation


class SelectionPanel(QWidget):
    """
    Painel de seleção/comando de stack.

    Cobre dois modos:
      - Stack militar/mista: mostra stats, comando pendente, hints de teclado.
      - Stack de workers:    mostra adicionalmente o grupo "Worker Actions"
                             com botões Fundar Província e Reintegrar Worker.

    Sinais:
        back_requested:           jogador clicou em ◀ Back
        cancel_command_requested: jogador cancelou o comando pendente
        go_to_tile_requested:     jogador quer centralizar câmera no tile
    """

    back_requested = Signal()
    cancel_command_requested = Signal()
    go_to_tile_requested = Signal(object)
    stack_selected = Signal(str)

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # uid -> (row_widget, btn, flag_label)
        self._stack_rows_by_uid: dict[str, tuple[QWidget, QPushButton, QLabel]] = {}
        self._active_stack_uid: str | None = None
        self._tile_coords_for_stack_list = None

        self._init_ui()

    # ================================================================
    # UI CONSTRUCTION
    # ================================================================

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # === Header ===
        header = QFrame()
        header.setStyleSheet(
            "background-color: #2a2a2a; border-bottom: 2px solid #FF9800;"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 10, 10, 10)

        self.btn_back = compact_button("◀ Back")
        self.btn_back.clicked.connect(self.back_requested.emit)
        header_layout.addWidget(self.btn_back)

        self.title_label = QLabel("⚔️ Unit Command")
        self.title_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.title_label.setStyleSheet("color: #FF9800;")
        header_layout.addWidget(self.title_label, 1)

        self.btn_go_to = compact_button("📍 Go to")
        self.btn_go_to.clicked.connect(self._emit_go_to)
        header_layout.addWidget(self.btn_go_to)

        layout.addWidget(header)

        # === Scroll area ===
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(8, 8, 8, 8)
        scroll_layout.setSpacing(10)

        # --- Location ---
        group_location = QGroupBox("📍 Location")
        group_location.setStyleSheet(self._group_style("#9E9E9E"))
        loc_layout = QVBoxLayout(group_location)
        loc_layout.setContentsMargins(10, 15, 10, 10)
        loc_layout.setSpacing(4)

        self.label_tile_coords = QLabel("Tile: —")
        self.label_tile_coords.setStyleSheet("color: #ddd;")
        loc_layout.addWidget(self.label_tile_coords)

        self.label_tile_biome = QLabel("Biome: —")
        self.label_tile_biome.setStyleSheet("color: #aaa;")
        loc_layout.addWidget(self.label_tile_biome)

        self.label_tile_owner = QLabel("Owner: —")
        self.label_tile_owner.setStyleSheet("color: #4CAF50;")
        loc_layout.addWidget(self.label_tile_owner)

        scroll_layout.addWidget(group_location)

        # ----------------------------------------------------------------
        # Stacks no tile (selector)
        # ----------------------------------------------------------------
        self.group_tile_stacks = QGroupBox("🧩 Stacks Here")
        self.group_tile_stacks.setStyleSheet(self._group_style("#FFC107"))
        tile_stacks_layout = QVBoxLayout(self.group_tile_stacks)
        tile_stacks_layout.setContentsMargins(10, 15, 10, 10)
        tile_stacks_layout.setSpacing(6)

        self.label_tile_stacks_hint = QLabel("—")
        self.label_tile_stacks_hint.setStyleSheet("color: #aaa; font-size: 11px;")
        self.label_tile_stacks_hint.setWordWrap(True)
        tile_stacks_layout.addWidget(self.label_tile_stacks_hint)

        self.stacks_layout = QVBoxLayout()
        self.stacks_layout.setSpacing(6)
        tile_stacks_layout.addLayout(self.stacks_layout)

        self.group_tile_stacks.setVisible(False)
        scroll_layout.addWidget(self.group_tile_stacks)

        # --- Units in Stack ---
        group_units = QGroupBox("🎖️ Stack Units")
        group_units.setStyleSheet(self._group_style("#FF9800"))
        units_layout = QVBoxLayout(group_units)
        units_layout.setContentsMargins(10, 15, 10, 10)
        units_layout.setSpacing(6)

        self.label_unit_count = QLabel("0 units")
        self.label_unit_count.setStyleSheet("color: #FFD700; font-weight: bold;")
        units_layout.addWidget(self.label_unit_count)

        self.unit_list = QListWidget()
        self.unit_list.setSelectionMode(QListWidget.NoSelection)
        self.unit_list.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 2px;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #2a2a2a;
                color: #ddd;
            }
        """)
        units_layout.addWidget(self.unit_list)

        scroll_layout.addWidget(group_units)

        # --- Stack Stats ---
        group_stats = QGroupBox("📊 Stack Stats")
        group_stats.setStyleSheet(self._group_style("#64B5F6"))
        stats_layout = QVBoxLayout(group_stats)
        stats_layout.setContentsMargins(10, 15, 10, 10)
        stats_layout.setSpacing(4)

        self.label_movement = QLabel("Movement: —")
        self.label_movement.setStyleSheet("color: #64B5F6;")
        stats_layout.addWidget(self.label_movement)

        self.label_budget = QLabel("Budget: —")
        self.label_budget.setStyleSheet("color: #aaa;")
        stats_layout.addWidget(self.label_budget)

        self.label_slowest = QLabel("")
        self.label_slowest.setStyleSheet(
            "color: #888; font-size: 11px; font-style: italic;"
        )
        self.label_slowest.setWordWrap(True)
        stats_layout.addWidget(self.label_slowest)

        scroll_layout.addWidget(group_stats)

        # --- Worker Actions ---
        self.group_worker = QGroupBox("⚒️ Worker Actions")
        self.group_worker.setStyleSheet(self._group_style("#9E9E9E"))
        worker_layout = QVBoxLayout(self.group_worker)
        worker_layout.setContentsMargins(10, 15, 10, 10)
        worker_layout.setSpacing(8)

        self.label_worker_info = QLabel("")
        self.label_worker_info.setStyleSheet("color: #aaa; font-size: 11px;")
        self.label_worker_info.setWordWrap(True)
        worker_layout.addWidget(self.label_worker_info)

        self.btn_found_province = QPushButton("🏛️ Found Province")
        self.btn_found_province.setToolTip(
            "Found a new province at this tile.\n"
            "Requires: colonizable biome, no existing province."
        )
        self.btn_found_province.setStyleSheet("""
            QPushButton { background-color: #1B5E20; border: none; border-radius: 4px;
                         padding: 8px 12px; color: white; font-weight: bold; }
            QPushButton:hover { background-color: #2E7D32; }
            QPushButton:pressed { background-color: #145214; }
            QPushButton:disabled { background-color: #333; color: #666; }
        """)
        self.btn_found_province.clicked.connect(self._on_found_province)
        worker_layout.addWidget(self.btn_found_province)

        self.btn_reattach_worker = QPushButton("🏠 Reintegrate Worker")
        self.btn_reattach_worker.setToolTip(
            "Return this worker to the province at this tile.\n"
            "Requires: a province at this tile."
        )
        self.btn_reattach_worker.setStyleSheet("""
            QPushButton { background-color: #0D47A1; border: none; border-radius: 4px;
                         padding: 8px 12px; color: white; font-weight: bold; }
            QPushButton:hover { background-color: #1565C0; }
            QPushButton:pressed { background-color: #0A3272; }
            QPushButton:disabled { background-color: #333; color: #666; }
        """)
        self.btn_reattach_worker.clicked.connect(self._on_reattach_worker)
        worker_layout.addWidget(self.btn_reattach_worker)

        self.label_worker_action_status = QLabel("")
        self.label_worker_action_status.setStyleSheet("color: #888; font-size: 11px;")
        worker_layout.addWidget(self.label_worker_action_status)

        self.group_worker.setVisible(False)
        scroll_layout.addWidget(self.group_worker)

        # --- Pending Command ---
        group_command = QGroupBox("📋 Pending Command")
        group_command.setStyleSheet(self._group_style("#4CAF50"))
        cmd_layout = QVBoxLayout(group_command)
        cmd_layout.setContentsMargins(10, 15, 10, 10)
        cmd_layout.setSpacing(8)

        self.command_frame = QFrame()
        self.command_frame.setStyleSheet("""
            QFrame {
                background-color: #2d3a2d;
                border: 1px solid #3a4a3a;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        cmd_inner = QVBoxLayout(self.command_frame)
        cmd_inner.setContentsMargins(8, 8, 8, 8)
        cmd_inner.setSpacing(4)

        self.label_command_type = QLabel("No command")
        self.label_command_type.setStyleSheet("color: #4CAF50; font-weight: bold;")
        cmd_inner.addWidget(self.label_command_type)

        self.label_command_dest = QLabel("")
        self.label_command_dest.setStyleSheet("color: #ddd;")
        cmd_inner.addWidget(self.label_command_dest)

        self.label_command_path = QLabel("")
        self.label_command_path.setStyleSheet("color: #aaa; font-size: 11px;")
        cmd_inner.addWidget(self.label_command_path)

        cmd_layout.addWidget(self.command_frame)

        self.label_no_command = QLabel(
            "ℹ️ Right-click a tile on the map\nto issue a move command."
        )
        self.label_no_command.setAlignment(Qt.AlignCenter)
        self.label_no_command.setStyleSheet(
            "color: #888; font-style: italic; padding: 10px;"
        )
        self.label_no_command.setWordWrap(True)
        cmd_layout.addWidget(self.label_no_command)

        self.btn_cancel_command = QPushButton("🚫 Cancel Command")
        self.btn_cancel_command.setStyleSheet("""
            QPushButton {
                background-color: #5D4037; border: none; border-radius: 4px;
                padding: 8px 12px; color: #ddd; font-weight: bold;
            }
            QPushButton:hover { background-color: #6D4C41; }
            QPushButton:pressed { background-color: #4E342E; }
        """)
        self.btn_cancel_command.clicked.connect(self.cancel_command_requested.emit)
        cmd_layout.addWidget(self.btn_cancel_command)

        scroll_layout.addWidget(group_command)

        # --- Hints ---
        hints_frame = QFrame()
        hints_frame.setStyleSheet(
            "background-color: #252525; border: 1px solid #3a3a3a; border-radius: 4px;"
        )
        hints_layout = QVBoxLayout(hints_frame)
        hints_layout.setContentsMargins(10, 8, 10, 8)
        hints_layout.setSpacing(2)

        hints = [
            ("🖱️ Right-click", "Move/Attack"),
            ("Esc", "Deselect"),
            ("Enter", "End Turn"),
        ]
        for key, action in hints:
            row = QHBoxLayout()
            lbl_key = QLabel(key)
            lbl_key.setStyleSheet(
                "color: #FFD700; font-weight: bold; font-size: 11px;"
            )
            lbl_key.setFixedWidth(100)
            row.addWidget(lbl_key)
            lbl_action = QLabel(action)
            lbl_action.setStyleSheet("color: #aaa; font-size: 11px;")
            row.addWidget(lbl_action)
            hints_layout.addLayout(row)

        scroll_layout.addWidget(hints_frame)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

    # ================================================================
    # PUBLIC: tile stacks selector (with flags)
    # ================================================================

    def set_tile_stacks(
        self,
        tile_coords,
        stacks,
        active_stack_uid: str | None,
        controlled_civ_id: int,
    ):
        """
        Atualiza a lista de stacks no tile SEM recriar widgets desnecessariamente.
        Cada stack é exibida como:
          [bandeira civ] [botão checkável com texto]
        """
        self._tile_coords_for_stack_list = tile_coords

        # 0 stacks: esconde e limpa
        if not stacks:
            self.group_tile_stacks.setVisible(False)
            self.label_tile_stacks_hint.setText("—")
            self._clear_stack_buttons()
            self._active_stack_uid = None
            self._tile_coords_for_stack_list = None
            return

        # 1+ stacks: mostra grupo
        self.group_tile_stacks.setVisible(True)

        if len(stacks) == 1:
            self.label_tile_stacks_hint.setText(f"Stack ativa em {tile_coords}:")
        else:
            self.label_tile_stacks_hint.setText(
                f"{len(stacks)} stack(s) em {tile_coords}. Selecione qual comandar:"
            )

        new_uids = [s.uid for s in stacks]
        new_uid_set = set(new_uids)

        game = getattr(self.controller, "game", None)
        planet_id = str(getattr(game, "id", "") or "") if game else ""

        # remove rows que não existem mais
        for uid in list(self._stack_rows_by_uid.keys()):
            if uid not in new_uid_set:
                row_widget, btn, flag_label = self._stack_rows_by_uid.pop(uid)
                row_widget.setParent(None)
                row_widget.deleteLater()

        # cria/atualiza rows (reusando quando possível)
        for s in stacks:
            row = self._stack_rows_by_uid.get(s.uid)

            # civ dona (para bandeira)
            owner_civ = None
            if game:
                owner_civ = next(
                    (c for c in getattr(game, "civilizations", []) if c.id == s.owner_id),
                    None,
                )

            text = self._format_stack_label(s, controlled_civ_id)

            if row is None:
                # row widget
                row_widget = QFrame()
                row_widget.setStyleSheet("QFrame { background-color: transparent; border: none; }")

                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(8)

                # bandeira
                flag_label = QLabel()
                flag_label.setFixedSize(24, 15)
                flag_label.setStyleSheet("border: 1px solid #555; border-radius: 2px;")
                row_layout.addWidget(flag_label, 0, Qt.AlignVCenter)

                # botão
                btn = QPushButton(text)
                btn.setCheckable(True)
                btn.setStyleSheet(self._stack_button_style())
                btn.clicked.connect(lambda _=False, uid=s.uid: self.stack_selected.emit(uid))
                row_layout.addWidget(btn, 1)

                self._stack_rows_by_uid[s.uid] = (row_widget, btn, flag_label)
                self.stacks_layout.addWidget(row_widget)
            else:
                row_widget, btn, flag_label = row
                btn.setText(text)

            # atualiza pixmap da bandeira (sempre)
            flag_label.setPixmap(self._get_flag_pixmap_for_civ(owner_civ, planet_id, size=(24, 15)))

        # garante highlight consistente (sem disparar signals)
        self.set_active_stack_uid(active_stack_uid)

    def set_active_stack_uid(self, active_stack_uid: str | None):
        """Só muda checked/highlight nos botões existentes."""
        self._active_stack_uid = active_stack_uid
        for uid, (row_widget, btn, flag_label) in self._stack_rows_by_uid.items():
            btn.blockSignals(True)
            btn.setChecked(uid == active_stack_uid)
            btn.blockSignals(False)

    # ================================================================
    # PUBLIC: update from controller state
    # ================================================================

    def update_from_selection(self, controller):
        """
        Atualiza todo o painel com base no estado de seleção atual.

        Detecta se a stack é exclusivamente de workers e exibe/esconde
        o grupo Worker Actions de acordo.
        """
        game = controller.game
        selection = controller.selection

        if not game or not selection.has_selection:
            self._show_empty()
            return

        stack = game.stacks.get_stack(selection.selected_stack_uid)
        if not stack or stack.is_empty():
            self._show_empty()
            return

        tile = stack.tile

        # --- Location ---
        biome = "—"
        if game.graph.has_node(tile):
            biome = game.graph.nodes[tile].get("bioma", "—")
        self.label_tile_coords.setText(f"Tile: {tile}")
        self.label_tile_biome.setText(f"Biome: {biome}")

        province = game.get_province(tile)
        if province and province.owner:
            r, g, b = province.owner.color
            self.label_tile_owner.setText(f"Owner: {province.owner.name}")
            self.label_tile_owner.setStyleSheet(
                f"color: rgb({r},{g},{b}); font-weight: bold;"
            )
        else:
            self.label_tile_owner.setText("Owner: None")
            self.label_tile_owner.setStyleSheet("color: #888;")

        # --- Units ---
        self.unit_list.clear()
        units = stack.units
        self.label_unit_count.setText(f"{len(units)} unit(s)")

        for unit in units:
            key = unit.unit_key
            stats = get_unit_stats(key)
            icon = UNIT_ICONS.get(key, "•")
            color = UNIT_COLORS.get(key, "#aaa")
            cat = get_unit_category(key)
            cat_icon = CATEGORY_ICONS.get(cat, "")
            display_name = UNIT_DISPLAY_NAMES.get(key, key.replace("_", " ").title())
            efficacy = f"{stats.eficacia:.1f}" if stats else "?"
            movement = str(stats.movement) if stats else "?"
            text = (
                f"{icon} {display_name}  [{cat_icon}{cat}]"
                f"  ⚔{efficacy}  🏃{movement}"
            )
            item = QListWidgetItem(text)
            item.setForeground(QColor(color))
            self.unit_list.addItem(item)

        self._fit_unit_list_height(max_height=220)

        # --- Stats ---
        mov = max_movement_for_stack(stack)
        budget = movement_budget_for_stack(stack)
        self.label_movement.setText(f"Movement: {mov} points")
        self.label_budget.setText(f"Budget: {budget:.0f} cost units")

        if len(units) > 1:
            slowest_key = None
            slowest_mov = 999
            for u in units:
                s = get_unit_stats(u.unit_key)
                if s and s.movement < slowest_mov:
                    slowest_mov = s.movement
                    slowest_key = u.unit_key
            if slowest_key:
                name = UNIT_DISPLAY_NAMES.get(
                    slowest_key, slowest_key.replace("_", " ").title()
                )
                self.label_slowest.setText(
                    f"⚠️ Limited by {name} (mov={slowest_mov})"
                )
        else:
            self.label_slowest.setText("")

        # --- Worker Actions ---
        is_worker_stack = all(u.unit_key == "worker" for u in units)
        self.group_worker.setVisible(is_worker_stack)
        self.label_worker_action_status.setText("")

        if is_worker_stack:
            self._update_worker_actions(stack, province, game)

        # --- Pending Command ---
        cmd = game.command_manager.get_command(stack.uid)
        if cmd and cmd.path and cmd.destination:
            dest_biome = "—"
            if game.graph.has_node(cmd.destination):
                dest_biome = game.graph.nodes[cmd.destination].get("bioma", "—")

            self.command_frame.setVisible(True)
            self.label_no_command.setVisible(False)
            self.btn_cancel_command.setVisible(True)

            self.label_command_type.setText(
                f"🟢 {cmd.command_type.name} → {cmd.destination}"
            )
            self.label_command_dest.setText(f"Destination biome: {dest_biome}")

            path_len = len(cmd.path)
            cost = 0.0
            for i in range(path_len - 1):
                edge = game.graph.get_edge_data(cmd.path[i], cmd.path[i + 1])
                if edge:
                    cost += float(edge.get("cust_mob", 0))
            self.label_command_path.setText(
                f"Path: {path_len} tiles, cost {cost:.1f}"
            )
            self.command_frame.setStyleSheet("""
                QFrame {
                    background-color: #2d3a2d;
                    border: 1px solid #4CAF50;
                    border-radius: 4px;
                    padding: 8px;
                }
            """)
        else:
            self.command_frame.setVisible(False)
            self.label_no_command.setVisible(True)
            self.btn_cancel_command.setVisible(False)

        # mantém highlight consistente quando o painel atualiza
        if self.group_tile_stacks.isVisible():
            self.set_active_stack_uid(stack.uid)

    # ================================================================
    # WORKER ACTIONS HELPERS
    # ================================================================

    def _update_worker_actions(self, stack, province, game) -> None:
        from core.workforce.facade import ProvinceWorkforceFacade

        tile = stack.tile
        first_worker_uid = stack.units[0].uid
        n_workers = len(stack.units)

        prov_name = province.name if province else "wilderness"
        self.label_worker_info.setText(
            f"{n_workers} worker(s) at {tile} — {prov_name}"
        )

        can_found, found_reason = ProvinceWorkforceFacade.can_found_province(
            first_worker_uid, game
        )
        self.btn_found_province.setEnabled(can_found)
        self.btn_found_province.setToolTip(
            f"Found a new province at {tile}.\n"
            f"{'✅ Available' if can_found else f'❌ {found_reason}'}"
        )

        if province is not None:
            can_reattach, reattach_reason = ProvinceWorkforceFacade.can_reattach_worker(
                first_worker_uid, province, game
            )
            self.btn_reattach_worker.setEnabled(can_reattach)
            self.btn_reattach_worker.setToolTip(
                f"Reintegrate worker into '{province.name}'.\n"
                f"{'✅ Available' if can_reattach else f'❌ {reattach_reason}'}"
            )
        else:
            self.btn_reattach_worker.setEnabled(False)
            self.btn_reattach_worker.setToolTip(
                "No province at this tile.\n"
                "Move the worker to a province tile first."
            )

    # ================================================================
    # WORKER CALLBACKS
    # ================================================================

    def _on_found_province(self) -> None:
        ctrl = self.controller
        game = ctrl.game
        selection = ctrl.selection

        if not game or not selection.has_selection:
            return

        stack = game.stacks.get_stack(selection.selected_stack_uid)
        if not stack or stack.is_empty():
            return

        first_worker_uid = stack.units[0].uid
        ok = ctrl.action_found_province(first_worker_uid)

        if ok:
            self.label_worker_action_status.setText("🏛️ Province founded!")
            self.label_worker_action_status.setStyleSheet(
                "color: #4CAF50; font-size: 11px;"
            )
        else:
            self.label_worker_action_status.setText("❌ Cannot found province here.")
            self.label_worker_action_status.setStyleSheet(
                "color: #F44336; font-size: 11px;"
            )
            self.update_from_selection(ctrl)

    def _on_reattach_worker(self) -> None:
        ctrl = self.controller
        game = ctrl.game
        selection = ctrl.selection

        if not game or not selection.has_selection:
            return

        stack = game.stacks.get_stack(selection.selected_stack_uid)
        if not stack or stack.is_empty():
            return

        province = game.get_province(stack.tile)
        if not province:
            self.label_worker_action_status.setText("❌ No province at this tile.")
            self.label_worker_action_status.setStyleSheet(
                "color: #F44336; font-size: 11px;"
            )
            return

        first_worker_uid = stack.units[0].uid
        ok = ctrl.action_reattach_worker(first_worker_uid, province)

        if ok:
            self.label_worker_action_status.setText("🏠 Worker reintegrated!")
            self.label_worker_action_status.setStyleSheet(
                "color: #4CAF50; font-size: 11px;"
            )
        else:
            self.label_worker_action_status.setText("❌ Cannot reintegrate here.")
            self.label_worker_action_status.setStyleSheet(
                "color: #F44336; font-size: 11px;"
            )
            self.update_from_selection(ctrl)

    # ================================================================
    # EMPTY STATE
    # ================================================================

    def _show_empty(self):
        self.label_tile_coords.setText("Tile: —")
        self.label_tile_biome.setText("Biome: —")
        self.label_tile_owner.setText("Owner: —")
        self.label_tile_owner.setStyleSheet("color: #4CAF50;")

        self.group_tile_stacks.setVisible(False)
        self.label_tile_stacks_hint.setText("—")
        self._clear_stack_buttons()
        self._active_stack_uid = None
        self._tile_coords_for_stack_list = None

        self.label_unit_count.setText("0 units")
        self.unit_list.clear()
        self._fit_unit_list_height(max_height=220)
        self.label_movement.setText("Movement: —")
        self.label_budget.setText("Budget: —")
        self.label_slowest.setText("")

        self.group_worker.setVisible(False)
        self.label_worker_action_status.setText("")

        self.command_frame.setVisible(False)
        self.label_no_command.setVisible(True)
        self.btn_cancel_command.setVisible(False)

    # ================================================================
    # MISC
    # ================================================================

    def _emit_go_to(self):
        sel = self.controller.selection
        if sel and sel.selected_tile:
            self.go_to_tile_requested.emit(sel.selected_tile)

    @staticmethod
    def _group_style(color: str) -> str:
        return f"""
            QGroupBox {{
                font-weight: bold;
                border: 1px solid #3a3a3a;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #252525;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: {color};
            }}
        """

    def _clear_stack_buttons(self):
        for uid, (row_widget, btn, flag_label) in list(self._stack_rows_by_uid.items()):
            self._stack_rows_by_uid.pop(uid, None)
            row_widget.setParent(None)
            row_widget.deleteLater()

    def _stack_button_style(self) -> str:
        return """
            QPushButton {
                text-align: left;
                background-color: #1e1e1e;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 8px 10px;
                color: #ddd;
            }
            QPushButton:hover {
                border: 1px solid #5a5a5a;
                background-color: #242424;
            }
            QPushButton:checked {
                border: 1px solid #FF9800;
                background-color: #2a2418;
                color: #FFD700;
                font-weight: bold;
            }
        """

    def _format_stack_label(self, stack, controlled_civ_id: int) -> str:
        owner_name = f"Civ {getattr(stack, 'owner_id', '?')}"

        game = getattr(self.controller, "game", None)
        if game:
            civ = next(
                (c for c in getattr(game, "civilizations", []) if c.id == stack.owner_id),
                None,
            )
            if civ:
                owner_name = civ.name

        rel_tag = ""
        if game and getattr(stack, "owner_id", None) is not None:
            if stack.owner_id == controlled_civ_id:
                rel_tag = "YOU"
            else:
                rel = game.diplomacy.relation(controlled_civ_id, stack.owner_id)
                if rel == Relation.ALLY:
                    rel_tag = "ALLY"
                elif rel == Relation.ENEMY:
                    rel_tag = "ENEMY"
                else:
                    rel_tag = "NEUTRAL"

        units = getattr(stack, "units", []) or []
        unit_keys = [u.unit_key for u in units]
        summary = ", ".join(unit_keys) if unit_keys else "—"

        owner_part = owner_name if not rel_tag else f"{owner_name} [{rel_tag}]"
        return f"{stack.uid[:8]} • {owner_part} • {len(units)}: {summary}"

    # ------------------------------------------------
    # Flags helper
    # ------------------------------------------------
    def _get_flag_pixmap_for_civ(self, civ, planet_id: str, size=(24, 15)) -> QPixmap:
        """
        Carrega assets/worlds/<planet_id>/flags/<civ.name>.png.
        Se não existir, cria um retângulo com a cor da civ.
        """
        def solid(rgb):
            px = QPixmap(size[0], size[1])
            if rgb and isinstance(rgb, (tuple, list)) and len(rgb) == 3:
                r, g, b = rgb
                px.fill(QColor(r, g, b))
            else:
                px.fill(QColor(120, 120, 120))
            return px

        if not civ:
            return solid(None)

        flag_path = os.path.join(
            "assets", "worlds", str(planet_id), "flags", f"{civ.name}.png"
        )
        if os.path.isfile(flag_path):
            px = QPixmap(flag_path)
            if not px.isNull():
                return px.scaled(
                    size[0], size[1], Qt.KeepAspectRatio, Qt.SmoothTransformation
                )

        return solid(getattr(civ, "color", None))

    # Helper de ajuste do tamanho do widget da lista de unidades da stack

    def _unit_list_content_height(self) -> int:
        """
        Altura ideal do QListWidget para mostrar todos os itens sem scroll,
        somando header interno + bordas. Funciona bem com poucos itens.
        """
        # altura de cada item
        total = 0
        for i in range(self.unit_list.count()):
            total += self.unit_list.sizeHintForRow(i)

        # alguns estilos retornam -1 quando ainda não calculou
        if total <= 0:
            # fallback: 1 linha
            total = max(1, self.unit_list.count()) * max(22, self.unit_list.fontMetrics().height() + 10)

        # bordas + margens internas
        total += 2 * self.unit_list.frameWidth()
        total += self.unit_list.contentsMargins().top() + self.unit_list.contentsMargins().bottom()

        # pequena folga pra evitar “corte” no último item com alguns estilos
        total += 4
        return total

    def _fit_unit_list_height(self, *, max_height: int = 220) -> None:
        """
        Ajusta a altura do QListWidget ao conteúdo (até max_height).
        Se passar do teto, permite scroll.
        """
        h = self._unit_list_content_height()

        # altura mínima quando vazio (evita ficar gigante)
        if self.unit_list.count() == 0:
            self.unit_list.setFixedHeight(40)
            return

        self.unit_list.setFixedHeight(min(h, max_height))