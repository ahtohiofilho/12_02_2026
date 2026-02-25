# ui/selection_panel.py
"""
Painel lateral exibido quando o jogador seleciona uma stack no mapa.
Mostra as unidades da stack, stats de movimento e comando pendente.
Permite cancelar comando ou dar novo comando (via clique direito no mapa).
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QFrame, QSizePolicy, QListWidget,
    QListWidgetItem, QPushButton, QScrollArea,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

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


class SelectionPanel(QWidget):
    """
    Painel de seleção/comando de stack militar.

    Sinais:
        back_requested: jogador clicou em ◀ Back
        cancel_command_requested: jogador cancelou o comando pendente
        go_to_tile_requested(tuple): jogador quer centralizar câmera no tile
    """

    back_requested = Signal()
    cancel_command_requested = Signal()
    go_to_tile_requested = Signal(object)

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
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
        self.unit_list.setMaximumHeight(200)
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
        self.label_slowest.setStyleSheet("color: #888; font-size: 11px; font-style: italic;")
        self.label_slowest.setWordWrap(True)
        stats_layout.addWidget(self.label_slowest)

        scroll_layout.addWidget(group_stats)

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

        # Placeholder (sem comando)
        self.label_no_command = QLabel(
            "ℹ️ Right-click a tile on the map\nto issue a move command."
        )
        self.label_no_command.setAlignment(Qt.AlignCenter)
        self.label_no_command.setStyleSheet(
            "color: #888; font-style: italic; padding: 10px;"
        )
        self.label_no_command.setWordWrap(True)
        cmd_layout.addWidget(self.label_no_command)

        # Cancel button
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
            lbl_key.setStyleSheet("color: #FFD700; font-weight: bold; font-size: 11px;")
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
    # PUBLIC: update from controller state
    # ================================================================

    def update_from_selection(self, controller):
        """
        Atualiza todo o painel com base no estado de seleção atual.
        Chamado pelo Controller/Sidebar quando:
          - Stack é selecionada (clique esquerdo)
          - Comando é emitido (clique direito)
          - Comando é cancelado (Escape ou botão)
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

            text = f"{icon} {display_name}  [{cat_icon}{cat}]  ⚔{efficacy}  🏃{movement}"
            item = QListWidgetItem(text)
            item.setForeground(QColor(color))
            self.unit_list.addItem(item)

        # --- Stats ---
        mov = max_movement_for_stack(stack)
        budget = movement_budget_for_stack(stack)
        self.label_movement.setText(f"Movement: {mov} points")
        self.label_budget.setText(f"Budget: {budget:.0f} cost units")

        # Identificar a unidade mais lenta
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
                self.label_slowest.setText(f"⚠️ Limited by {name} (mov={slowest_mov})")
        else:
            self.label_slowest.setText("")

        # --- Pending Command ---
        cmd = game.command_manager.get_command(stack.uid)
        if cmd and cmd.path and cmd.destination:
            dest_biome = "—"
            if game.graph.has_node(cmd.destination):
                dest_biome = game.graph.nodes[cmd.destination].get("bioma", "—")

            self.command_frame.setVisible(True)
            self.label_no_command.setVisible(False)
            self.btn_cancel_command.setVisible(True)

            self.label_command_type.setText(f"🟢 {cmd.command_type.name} → {cmd.destination}")
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

    def _show_empty(self):
        self.label_tile_coords.setText("Tile: —")
        self.label_tile_biome.setText("Biome: —")
        self.label_tile_owner.setText("Owner: —")
        self.label_unit_count.setText("0 units")
        self.unit_list.clear()
        self.label_movement.setText("Movement: —")
        self.label_budget.setText("Budget: —")
        self.label_slowest.setText("")
        self.command_frame.setVisible(False)
        self.label_no_command.setVisible(True)
        self.btn_cancel_command.setVisible(False)

    def _emit_go_to(self):
        sel = self.controller.selection
        if sel and sel.selected_tile:
            self.go_to_tile_requested.emit(sel.selected_tile)

    # ================================================================
    # STYLE HELPER
    # ================================================================

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
