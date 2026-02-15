# ui/civ_manager.py
"""
Widget de gerenciamento da civilização do jogador.
Exibe informações da civ, províncias, economia e forças militares.
Adaptado para a arquitetura atual (Planet, StackRepository, ProvinceEconomyRepository).
"""

from collections import defaultdict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTabWidget, QGroupBox, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QSizePolicy, QGridLayout, QScrollArea,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap

from core.planet import Planet
from core.civilization import Civilization
from config.unit_stats import UNIT_STATS, UnitCategory
from ui.widgets import compact_button
from ui.province.military_ui import (
    UNIT_ICONS,
    UNIT_COLORS,
    CATEGORY_ICONS,
    CATEGORY_COLORS,
    UNITS_BY_CATEGORY,
    count_units_for_civ,
    format_units_by_category,
)

# ============================================================
# WIDGET PRINCIPAL
# ============================================================

class CivilizationManagerWidget(QWidget):
    """
    Painel de gerenciamento da civilização do jogador.
    Adaptado para a nova arquitetura:
      - Planet (self.current_planet) contém graph, stacks, econ_repo, turn_engine
      - Civilization (self.current_civ) contém provinces, capital_coords, name, color
    """

    # Sinais
    turn_advanced = Signal()
    save_requested = Signal()
    back_to_menu_requested = Signal()
    exit_requested = Signal()
    province_selected = Signal(object)
    go_to_capital_requested = Signal()

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.current_civ: Civilization | None = None
        self.current_planet: Planet | None = None

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._init_ui()

    def set_data(self, civ: Civilization, planet: Planet):
        """Define a civilização e o planeta a serem gerenciados."""
        self.current_civ = civ
        self.current_planet = planet
        self.update_display()

    # =====================================================================
    # LAYOUT PRINCIPAL
    # =====================================================================

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        self.header_frame = self._create_header()
        layout.addWidget(self.header_frame)

        # Tabs
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #3a3a3a; background-color: #2a2a2a; }
            QTabBar::tab { background-color: #333; color: #ccc; padding: 8px 16px; margin-right: 2px; }
            QTabBar::tab:selected { background-color: #2a2a2a; color: #fff; border-bottom: 2px solid #4CAF50; }
            QTabBar::tab:hover { background-color: #3a3a3a; }
        """)

        self.tab_overview = self._create_overview_tab()
        self.tab_widget.addTab(self.tab_overview, "📊 Overview")

        self.tab_provinces = self._create_provinces_tab()
        self.tab_widget.addTab(self.tab_provinces, "🏛️ Provinces")

        self.tab_military = self._create_military_tab()
        self.tab_widget.addTab(self.tab_military, "⚔️ Military")

        self.tab_diplomacy = self._create_diplomacy_tab()
        self.tab_widget.addTab(self.tab_diplomacy, "🤝 Diplomacy")

        layout.addWidget(self.tab_widget, 1)

        # Footer
        self.footer_frame = self._create_footer()
        layout.addWidget(self.footer_frame)

    # =====================================================================
    # HEADER
    # =====================================================================

    def _create_header(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("background-color: #2a2a2a; border-bottom: 2px solid #4CAF50;")

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Bandeira
        self.flag_label = QLabel()
        self.flag_label.setFixedSize(48, 30)
        self.flag_label.setStyleSheet("border: 2px solid #555; border-radius: 3px; background-color: #333;")
        layout.addWidget(self.flag_label)

        # Nome
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        self.name_label = QLabel("Civilization")
        self.name_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.name_label.setStyleSheet("color: #4CAF50; border: none;")
        info_layout.addWidget(self.name_label)

        layout.addLayout(info_layout, 1)

        # Turno + botão Advance
        turn_layout = QVBoxLayout()
        turn_layout.setAlignment(Qt.AlignRight)

        self.turn_label = QLabel("Turn 0")
        self.turn_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.turn_label.setStyleSheet("color: #FFD700; border: none;")
        self.turn_label.setAlignment(Qt.AlignRight)
        turn_layout.addWidget(self.turn_label)

        layout.addLayout(turn_layout)
        return frame

    # =====================================================================
    # TAB: OVERVIEW
    # =====================================================================

    def _create_overview_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # --- Statistics ---
        group_stats = QGroupBox("📈 Statistics")
        group_stats.setStyleSheet(self._group_style("#64B5F6"))
        stats_layout = QGridLayout(group_stats)
        stats_layout.setContentsMargins(10, 15, 10, 10)
        stats_layout.setSpacing(8)

        stats_layout.addWidget(QLabel("🏛️ Provinces:"), 0, 0)
        self.label_provinces_count = QLabel("0")
        self.label_provinces_count.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self.label_provinces_count.setAlignment(Qt.AlignRight)
        stats_layout.addWidget(self.label_provinces_count, 0, 1)

        stats_layout.addWidget(QLabel("👥 Total Workers:"), 1, 0)
        self.label_total_workers = QLabel("0")
        self.label_total_workers.setStyleSheet("color: #64B5F6; font-weight: bold;")
        self.label_total_workers.setAlignment(Qt.AlignRight)
        stats_layout.addWidget(self.label_total_workers, 1, 1)

        stats_layout.addWidget(QLabel("⚔️ Military Units:"), 2, 0)
        self.label_military_units = QLabel("0")
        self.label_military_units.setStyleSheet("color: #FF9800; font-weight: bold;")
        self.label_military_units.setAlignment(Qt.AlignRight)
        stats_layout.addWidget(self.label_military_units, 2, 1)

        layout.addWidget(group_stats)

        # --- Economy ---
        group_economy = QGroupBox("💰 Economy")
        group_economy.setStyleSheet(self._group_style("#81C784"))
        economy_layout = QGridLayout(group_economy)
        economy_layout.setContentsMargins(10, 15, 10, 10)
        economy_layout.setSpacing(8)

        economy_layout.addWidget(QLabel("💵 Total Treasury:"), 0, 0)
        self.label_total_treasury = QLabel("N/A")
        self.label_total_treasury.setStyleSheet("color: #FFD700; font-weight: bold;")
        self.label_total_treasury.setAlignment(Qt.AlignRight)
        economy_layout.addWidget(self.label_total_treasury, 0, 1)

        economy_layout.addWidget(QLabel("📈 Last Income:"), 1, 0)
        self.label_last_income = QLabel("N/A")
        self.label_last_income.setStyleSheet("color: #8BC34A;")
        self.label_last_income.setAlignment(Qt.AlignRight)
        economy_layout.addWidget(self.label_last_income, 1, 1)

        economy_layout.addWidget(QLabel("🌾 Food Production:"), 2, 0)
        self.label_food_production = QLabel("0.0")
        self.label_food_production.setStyleSheet("color: #4CAF50;")
        self.label_food_production.setAlignment(Qt.AlignRight)
        economy_layout.addWidget(self.label_food_production, 2, 1)

        economy_layout.addWidget(QLabel("⛏️ Ore Production:"), 3, 0)
        self.label_ore_production = QLabel("0.0")
        self.label_ore_production.setStyleSheet("color: #FF9800;")
        self.label_ore_production.setAlignment(Qt.AlignRight)
        economy_layout.addWidget(self.label_ore_production, 3, 1)

        layout.addWidget(group_economy)

        # --- Capital ---
        group_capital = QGroupBox("⭐ Capital")
        group_capital.setStyleSheet(self._group_style("#FFD700"))
        capital_layout = QVBoxLayout(group_capital)
        capital_layout.setContentsMargins(10, 15, 10, 10)

        self.label_capital_info = QLabel("No capital")
        self.label_capital_info.setStyleSheet("color: #ddd;")
        self.label_capital_info.setWordWrap(True)
        capital_layout.addWidget(self.label_capital_info)

        self.btn_go_to_capital = compact_button("📍 Go to Capital")
        self.btn_go_to_capital.clicked.connect(self.go_to_capital_requested.emit)
        capital_layout.addWidget(self.btn_go_to_capital, 0, Qt.AlignLeft)

        layout.addWidget(group_capital)
        layout.addStretch()
        return widget

    # =====================================================================
    # TAB: PROVINCES
    # =====================================================================

    def _create_provinces_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Tabela
        self.provinces_table = QTableWidget(0, 5)
        self.provinces_table.setHorizontalHeaderLabels([
            "Name", "Coords", "Biome", "Workers", "Food / Ore",
        ])
        self.provinces_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 5):
            self.provinces_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.provinces_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.provinces_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.provinces_table.clicked.connect(self._on_province_clicked)
        self.provinces_table.setStyleSheet("""
            QTableWidget {
                background-color: #2a2a2a; border: 1px solid #3a3a3a; gridline-color: #3a3a3a;
            }
            QTableWidget::item { padding: 5px; }
            QTableWidget::item:selected { background-color: #3a4a5a; }
            QHeaderView::section {
                background-color: #333; color: #ddd; padding: 5px; border: 1px solid #3a3a3a;
            }
        """)
        layout.addWidget(self.provinces_table, 1)

        return widget

    # =====================================================================
    # TAB: MILITARY
    # =====================================================================

    def _create_military_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(5, 5, 5, 5)
        scroll_layout.setSpacing(10)

        # --- Total Forces ---
        group_total = QGroupBox("🎖️ Total Forces")
        group_total.setStyleSheet(self._group_style("#FF9800"))
        total_layout = QHBoxLayout(group_total)
        total_layout.setContentsMargins(10, 15, 10, 10)

        self.label_total_units = QLabel("0 units")
        self.label_total_units.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.label_total_units.setStyleSheet("color: #FFD700;")
        total_layout.addWidget(self.label_total_units)

        total_layout.addStretch()

        self.label_land_summary = QLabel("⚔️ 0")
        self.label_land_summary.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self.label_land_summary.setToolTip("Land Forces")
        total_layout.addWidget(self.label_land_summary)

        self.label_naval_summary = QLabel("⚓ 0")
        self.label_naval_summary.setStyleSheet("color: #2196F3; font-weight: bold;")
        self.label_naval_summary.setToolTip("Naval Forces")
        total_layout.addWidget(self.label_naval_summary)

        self.label_air_summary = QLabel("✈️ 0")
        self.label_air_summary.setStyleSheet("color: #9C27B0; font-weight: bold;")
        self.label_air_summary.setToolTip("Air Forces")
        total_layout.addWidget(self.label_air_summary)

        scroll_layout.addWidget(group_total)

        # --- Grupos por categoria (gerados dinamicamente) ---
        self.unit_labels_by_key: dict[str, QLabel] = {}

        category_meta = {
            "LAND":  ("⚔️ Land Forces",  "#4CAF50"),
            "NAVAL": ("⚓ Naval Forces",  "#2196F3"),
            "AIR":   ("✈️ Air Forces",   "#9C27B0"),
        }

        for cat_name, (group_title, group_color) in category_meta.items():
            unit_keys = UNITS_BY_CATEGORY.get(cat_name, [])
            if not unit_keys:
                continue

            group = QGroupBox(group_title)
            group.setStyleSheet(self._group_style(group_color))
            grid = QGridLayout(group)
            grid.setContentsMargins(10, 15, 10, 10)
            grid.setSpacing(8)

            for row, unit_key in enumerate(unit_keys):
                icon = UNIT_ICONS.get(unit_key, "?")
                color = UNIT_COLORS.get(unit_key, "#888")
                display_name = unit_key.replace("_", " ").title()

                lbl_name = QLabel(f"{icon} {display_name}:")
                lbl_name.setStyleSheet(f"color: {color};")
                grid.addWidget(lbl_name, row, 0)

                lbl_count = QLabel("0")
                lbl_count.setStyleSheet(f"color: {color}; font-weight: bold;")
                lbl_count.setAlignment(Qt.AlignRight)
                grid.addWidget(lbl_count, row, 1)

                self.unit_labels_by_key[unit_key] = lbl_count

            scroll_layout.addWidget(group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        return widget

    # =====================================================================
    # TAB: DIPLOMACY
    # =====================================================================

    def _create_diplomacy_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)

        # Wars
        group_wars = QGroupBox("⚔️ Active Wars")
        group_wars.setStyleSheet(self._group_style("#F44336"))
        wars_layout = QVBoxLayout(group_wars)
        wars_layout.setContentsMargins(10, 15, 10, 10)

        self.label_wars = QLabel("No active wars")
        self.label_wars.setStyleSheet("color: #888; font-style: italic;")
        self.label_wars.setWordWrap(True)
        wars_layout.addWidget(self.label_wars)
        layout.addWidget(group_wars)

        # Relations
        group_relations = QGroupBox("🤝 Relations")
        group_relations.setStyleSheet(self._group_style("#9E9E9E"))
        relations_layout = QVBoxLayout(group_relations)
        relations_layout.setContentsMargins(10, 15, 10, 10)

        self.relations_container = QVBoxLayout()
        relations_layout.addLayout(self.relations_container)

        placeholder = QLabel("Diplomacy features coming soon...")
        placeholder.setStyleSheet("color: #666; font-style: italic;")
        placeholder.setAlignment(Qt.AlignCenter)
        self.relations_container.addWidget(placeholder)

        layout.addWidget(group_relations)
        layout.addStretch()
        return widget

    # =====================================================================
    # FOOTER
    # =====================================================================

    def _create_footer(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("background-color: #252525; border-top: 1px solid #3a3a3a;")

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        btn_save = compact_button("💾 Save")
        btn_save.clicked.connect(self.save_requested.emit)
        layout.addWidget(btn_save, 0, Qt.AlignLeft)

        layout.addStretch()

        btn_back = compact_button("🔙 Menu")
        btn_back.clicked.connect(self.back_to_menu_requested.emit)
        layout.addWidget(btn_back, 0, Qt.AlignRight)

        btn_exit = compact_button("🚪 Exit")
        btn_exit.setObjectName("dangerButton")
        btn_exit.clicked.connect(self.exit_requested.emit)
        layout.addWidget(btn_exit, 0, Qt.AlignRight)

        return frame

    # =====================================================================
    # ESTILO AUXILIAR
    # =====================================================================

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

    # =====================================================================
    # ATUALIZAÇÃO DE DADOS
    # =====================================================================

    def update_display(self):
        if not self.current_civ or not self.current_planet:
            return
        self._update_header()
        self._update_overview()
        self._update_provinces()
        self._update_military()
        self._update_diplomacy()

    def _update_header(self):
        civ = self.current_civ
        planet = self.current_planet

        self.name_label.setText(civ.name)
        self.turn_label.setText(f"Turn {planet.turn_engine.turn_number}")

        # Bandeira: tenta carregar a imagem gerada pelo flag_service
        self._update_flag_icon()

    def _update_flag_icon(self):
        """Tenta carregar o pixmap da bandeira da civilização."""
        civ = self.current_civ
        planet = self.current_planet
        if not civ or not planet:
            return

        # Caminho padrão esperado pelo flag_service
        import os
        flag_path = os.path.join(
            "assets", "flags", str(planet.id), f"{civ.name}.png"
        )

        if os.path.isfile(flag_path):
            pixmap = QPixmap(flag_path)
            if not pixmap.isNull():
                self.flag_label.setPixmap(
                    pixmap.scaled(48, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
                return

        # Fallback: cor sólida da civilização
        r, g, b = civ.color
        self.flag_label.setStyleSheet(
            f"border: 2px solid #555; border-radius: 3px; background-color: rgb({r},{g},{b});"
        )
        self.flag_label.setText("")

    def _update_overview(self):
        civ = self.current_civ
        planet = self.current_planet
        if not civ or not planet:
            return

        # Províncias e workers
        civ_tiles = {p.tile_coords for p in civ.provinces}
        self.label_provinces_count.setText(str(len(civ.provinces)))

        total_workers = sum(
            econ.workers
            for econ in planet.econ_repo.all()
            if econ.tile in civ_tiles
        )
        self.label_total_workers.setText(str(total_workers))

        # Unidades militares (total)
        counts = self._count_all_units()
        self.label_military_units.setText(str(sum(counts.values())))

        # Economia
        self.label_total_treasury.setText("N/A")
        self.label_last_income.setText("N/A")

        total_food = sum(s.food_output for s in planet.econ_repo.all() if s.tile in civ_tiles)
        total_ore = sum(s.ore_output for s in planet.econ_repo.all() if s.tile in civ_tiles)
        self.label_food_production.setText(f"{total_food:.1f}")
        self.label_ore_production.setText(f"{total_ore:.1f}")

        # Capital
        capital_prov = next(
            (p for p in civ.provinces if p.tile_coords == civ.capital_coords), None
        )
        if capital_prov:
            econ = planet.econ_repo.get(civ.capital_coords)
            workers = econ.workers if econ else 0
            self.label_capital_info.setText(
                f"📍 {capital_prov.name}\n"
                f"Coords: {capital_prov.tile_coords}\n"
                f"Workers: {workers}"
            )
            self.btn_go_to_capital.setEnabled(True)
        else:
            self.label_capital_info.setText("Capital not found")
            self.btn_go_to_capital.setEnabled(False)

    def _update_provinces(self):
        """Atualiza a tabela de províncias."""
        civ = self.current_civ
        planet = self.current_planet
        if not civ or not planet:
            return

        self.provinces_table.setRowCount(0)

        # Ordenar: capital primeiro, depois por coordenada
        sorted_provinces = sorted(
            civ.provinces,
            key=lambda p: (not p.is_capital, p.tile_coords),
        )

        for prov in sorted_provinces:
            row = self.provinces_table.rowCount()
            self.provinces_table.insertRow(row)

            # Nome (⭐ se capital)
            display_name = f"⭐ {prov.name}" if prov.is_capital else prov.name
            item_name = QTableWidgetItem(display_name)
            item_name.setData(Qt.UserRole, prov)
            self.provinces_table.setItem(row, 0, item_name)

            # Coordenadas
            self.provinces_table.setItem(row, 1, QTableWidgetItem(str(prov.tile_coords)))

            # Bioma
            biome = "—"
            if planet.graph.has_node(prov.tile_coords):
                biome = planet.graph.nodes[prov.tile_coords].get("bioma", "—")
            self.provinces_table.setItem(row, 2, QTableWidgetItem(biome))

            # Workers
            econ = planet.econ_repo.get(prov.tile_coords)
            workers = econ.workers if econ else 0
            self.provinces_table.setItem(row, 3, QTableWidgetItem(str(workers)))

            # Food / Ore
            food = econ.food_output if econ else 0.0
            ore = econ.ore_output if econ else 0.0
            self.provinces_table.setItem(row, 4, QTableWidgetItem(f"{food:.0f} / {ore:.0f}"))

    def _count_all_units(self) -> dict[str, int]:
        """Conta todas as unidades da civilização por unit_key."""
        if not self.current_civ or not self.current_planet:
            return {}
        return count_units_for_civ(self.current_planet, self.current_civ.id)

    def _update_military(self):
        """Atualiza a aba militar com contagens reais."""
        counts = self._count_all_units()
        total = sum(counts.values())

        self.label_total_units.setText(f"{total} units")

        # Por categoria
        land_total = sum(counts.get(k, 0) for k in UNITS_BY_CATEGORY.get("LAND", []))
        naval_total = sum(counts.get(k, 0) for k in UNITS_BY_CATEGORY.get("NAVAL", []))
        air_total = sum(counts.get(k, 0) for k in UNITS_BY_CATEGORY.get("AIR", []))

        self.label_land_summary.setText(f"⚔️ {land_total}")
        self.label_naval_summary.setText(f"⚓ {naval_total}")
        self.label_air_summary.setText(f"✈️ {air_total}")

        # Labels individuais
        for unit_key, label in self.unit_labels_by_key.items():
            label.setText(str(counts.get(unit_key, 0)))

    def _update_diplomacy(self):
        """Atualiza a aba de diplomacia usando a DiplomacyMatrix."""
        civ = self.current_civ
        planet = self.current_planet
        if not civ or not planet:
            return

        from core.diplomacy import Relation

        # Encontrar guerras (relações ENEMY)
        active_enemies = []
        for other_civ in planet.civilizations:
            if other_civ.id == civ.id:
                continue
            rel = planet.diplomacy.relation(civ.id, other_civ.id)
            if rel == Relation.ENEMY:
                active_enemies.append(other_civ.name)

        if active_enemies:
            self.label_wars.setText("⚔️ At war with:\n• " + "\n• ".join(active_enemies))
            self.label_wars.setStyleSheet("color: #F44336;")
        else:
            self.label_wars.setText("✌️ At peace with all civilizations")
            self.label_wars.setStyleSheet("color: #8BC34A;")

    # =====================================================================
    # CALLBACKS
    # =====================================================================

    def _on_province_clicked(self, index):
        """Emite o sinal province_selected ao clicar em qualquer linha da tabela."""
        row = index.row()
        item = self.provinces_table.item(row, 0)
        if item:
            prov = item.data(Qt.UserRole)
            if prov:
                print(f"Província selecionada: {prov.name} em {prov.tile_coords}")
                self.province_selected.emit(prov)

