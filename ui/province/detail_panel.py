# ui/province/detail_panel.py
"""
Widget de gerenciamento de província com abas.
Adaptado da versão antiga (ProvinceManagerWidget) para a arquitetura atual:
  - Planet com graph, stacks (StackRepository), econ_repo, turn_engine
  - Province com tile_coords, owner, is_capital, name
  - Unidades via unit_key (config.unit_stats)
"""

from collections import Counter, defaultdict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTabWidget, QGroupBox, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QSizePolicy, QGridLayout, QScrollArea,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from core.civilization import Province
from core.planet import Planet
from config.unit_stats import UNIT_STATS
from ui.widgets import compact_button
from ui.province.military_ui import (
    UNIT_ICONS,
    UNIT_COLORS,
    UNIT_ABBREVIATIONS,
    CATEGORY_ICONS,
    UNITS_BY_CATEGORY,
    count_units_in_tile,
    group_counts_by_category,
    format_units_by_category,
    get_unit_category,
)
from core.workforce.facade import ProvinceWorkforceFacade

# ============================================================
# WIDGET PRINCIPAL
# ============================================================

class ProvinceDetailPanel(QWidget):
    """
    Widget de gerenciamento de uma província individual com abas:
      - Overview (info geral + economia + guarnição)
      - Workforce (placeholder)
      - Trade (placeholder)
      - Military (unidades presentes + recrutamento)
    """

    back_requested = Signal()
    go_to_province_requested = Signal(object)  # emite Province

    def __init__(self, parent=None):
        super().__init__(parent)
        self.province: Province | None = None
        self.planet: Planet | None = None

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._init_ui()

    def set_province(self, province: Province, planet: Planet):
        """Define a província e o planeta, e carrega os dados na interface."""
        self.province = province
        self.planet = planet
        self._load_province_data()

    # =====================================================================
    # LAYOUT PRINCIPAL
    # =====================================================================

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # === Header ===
        header_frame = QFrame()
        header_frame.setStyleSheet(
            "background-color: #2a2a2a; border-bottom: 2px solid #3a3a3a;"
        )
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(10, 10, 10, 10)

        self.btn_back = compact_button("◀ Back")
        self.btn_back.clicked.connect(self.back_requested.emit)
        header_layout.addWidget(self.btn_back)

        self.title_label = QLabel("Province Details")
        self.title_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.title_label.setStyleSheet("color: #4CAF50;")
        header_layout.addWidget(self.title_label, 1)

        self.btn_go_to = compact_button("📍 Go to")
        self.btn_go_to.clicked.connect(self._emit_go_to)
        header_layout.addWidget(self.btn_go_to)

        layout.addWidget(header_frame)

        # === Tabs ===
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #3a3a3a; background-color: #2a2a2a; }
            QTabBar::tab { background-color: #333; color: #ccc; padding: 8px 16px; margin-right: 2px; }
            QTabBar::tab:selected { background-color: #2a2a2a; color: #fff; border-bottom: 2px solid #4CAF50; }
            QTabBar::tab:hover { background-color: #3a3a3a; }
        """)

        # Tab 1: Overview
        self.tab_overview = self._create_overview_tab()
        self.tab_widget.addTab(self.tab_overview, "📊 Overview")

        # Tab 2: Workforce (placeholder)
        self.tab_workforce = self._create_workforce_tab()
        self.tab_widget.addTab(self.tab_workforce, "👷 Workforce")

        # Tab 3: Trade (placeholder)
        self.tab_trade = self._create_trade_tab()
        self.tab_widget.addTab(self.tab_trade, "🔄 Trade")

        # Tab 4: Military
        self.tab_military = self._create_military_tab()
        self.tab_widget.addTab(self.tab_military, "⚔️ Military")

        layout.addWidget(self.tab_widget, 1)

        # === Footer ===
        footer_frame = QFrame()
        footer_frame.setStyleSheet(
            "background-color: #2a2a2a; border-top: 1px solid #3a3a3a;"
        )
        footer_layout = QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(10, 5, 10, 5)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #888; font-size: 11px;")
        footer_layout.addWidget(self.status_label)

        layout.addWidget(footer_frame)

    # =====================================================================
    # TAB: OVERVIEW
    # =====================================================================

    def _create_overview_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # --- Informações básicas ---
        group_basic = QGroupBox("📍 Basic Information")
        group_basic.setStyleSheet(self._group_style("#9E9E9E"))
        layout_basic = QVBoxLayout(group_basic)
        layout_basic.setContentsMargins(10, 15, 10, 10)
        layout_basic.setSpacing(4)

        self.label_coordinates = QLabel("Coordinates: —")
        self.label_biome = QLabel("Biome: —")
        self.label_temperature = QLabel("Temperature: —")
        self.label_humidity = QLabel("Humidity: —")
        self.label_altitude = QLabel("Altitude: —")
        self.label_fertility = QLabel("Fertility: —")
        self.label_plate = QLabel("Tectonic Plate: —")
        self.label_civilization = QLabel("Civilization: —")
        self.label_is_capital = QLabel("Capital: No")

        for lbl in (
            self.label_coordinates, self.label_biome, self.label_temperature,
            self.label_humidity, self.label_altitude, self.label_fertility,
            self.label_plate,
        ):
            lbl.setStyleSheet("color: #aaa;")

        self.label_civilization.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self.label_is_capital.setStyleSheet("color: #aaa;")

        for lbl in (
            self.label_coordinates, self.label_biome, self.label_temperature,
            self.label_humidity, self.label_altitude, self.label_fertility,
            self.label_plate, self.label_civilization, self.label_is_capital,
        ):
            layout_basic.addWidget(lbl)

        layout.addWidget(group_basic)

        # --- Economia resumida ---
        group_economy = QGroupBox("💰 Economy Summary")
        group_economy.setStyleSheet(self._group_style("#81C784"))
        layout_economy = QGridLayout(group_economy)
        layout_economy.setContentsMargins(10, 15, 10, 10)
        layout_economy.setSpacing(8)

        layout_economy.addWidget(QLabel("👥 Workers:"), 0, 0)
        self.label_workers = QLabel("0")
        self.label_workers.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self.label_workers.setAlignment(Qt.AlignRight)
        layout_economy.addWidget(self.label_workers, 0, 1)

        layout_economy.addWidget(QLabel("🌾 Food Output:"), 1, 0)
        self.label_food = QLabel("0.0")
        self.label_food.setStyleSheet("color: #4CAF50;")
        self.label_food.setAlignment(Qt.AlignRight)
        layout_economy.addWidget(self.label_food, 1, 1)

        layout_economy.addWidget(QLabel("🍞 Food Type:"), 2, 0)
        self.label_food_type = QLabel("—")
        self.label_food_type.setStyleSheet("color: #aaa;")
        self.label_food_type.setAlignment(Qt.AlignRight)
        layout_economy.addWidget(self.label_food_type, 2, 1)

        layout_economy.addWidget(QLabel("⛏️ Ore Output:"), 3, 0)
        self.label_ore = QLabel("0.0")
        self.label_ore.setStyleSheet("color: #FF9800;")
        self.label_ore.setAlignment(Qt.AlignRight)
        layout_economy.addWidget(self.label_ore, 3, 1)

        layout_economy.addWidget(QLabel("🪨 Ore Type:"), 4, 0)
        self.label_ore_type = QLabel("—")
        self.label_ore_type.setStyleSheet("color: #aaa;")
        self.label_ore_type.setAlignment(Qt.AlignRight)
        layout_economy.addWidget(self.label_ore_type, 4, 1)

        layout.addWidget(group_economy)

        # --- Guarnição resumida ---
        group_garrison = QGroupBox("⚔️ Garrison Summary")
        group_garrison.setStyleSheet(self._group_style("#FF9800"))
        garrison_layout = QVBoxLayout(group_garrison)
        garrison_layout.setContentsMargins(10, 15, 10, 10)

        self.label_garrison_summary = QLabel("No units")
        self.label_garrison_summary.setStyleSheet("color: #888; font-style: italic;")
        self.label_garrison_summary.setWordWrap(True)
        garrison_layout.addWidget(self.label_garrison_summary)

        layout.addWidget(group_garrison)

        layout.addStretch()
        return widget

    # =====================================================================
    # TAB: WORKFORCE (placeholder)
    # =====================================================================

    def _create_workforce_tab(self) -> QWidget:
        from ui.province.workforce_tab import WorkforceTabWidget
        widget = WorkforceTabWidget()
        return widget

    # =====================================================================
    # TAB: TRADE (placeholder)
    # =====================================================================

    def _create_trade_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)

        placeholder = QLabel("🔄 Trade overview coming soon...")
        placeholder.setStyleSheet("color: #666; font-style: italic;")
        placeholder.setAlignment(Qt.AlignCenter)
        layout.addWidget(placeholder)
        layout.addStretch()
        return widget

    # =====================================================================
    # TAB: MILITARY
    # =====================================================================

    def _create_military_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(5, 5, 5, 5)
        scroll_layout.setSpacing(10)

        # --- Info bar (cash + queue) ---
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        info_layout = QHBoxLayout(info_frame)
        info_layout.setContentsMargins(10, 5, 10, 5)

        self.label_mil_cash = QLabel("💰 Cash: —")
        self.label_mil_cash.setStyleSheet("color: #FFD700; font-weight: bold;")
        info_layout.addWidget(self.label_mil_cash)

        info_layout.addStretch()

        self.label_mil_queue = QLabel("📋 Queue: —")
        self.label_mil_queue.setStyleSheet("color: #aaa;")
        info_layout.addWidget(self.label_mil_queue)

        scroll_layout.addWidget(info_frame)

        # --- Recrutamento por categoria ---
        category_meta = {
            "LAND":  ("⚔️ Land Units",  "#4CAF50"),
            "NAVAL": ("⚓ Naval Units",  "#2196F3"),
            "AIR":   ("✈️ Air Units",   "#9C27B0"),
        }

        self.recruit_buttons: dict[str, QPushButton] = {}

        for cat_name, (group_title, group_color) in category_meta.items():
            unit_keys = UNITS_BY_CATEGORY.get(cat_name, [])
            if not unit_keys:
                continue

            group = QGroupBox(group_title)
            group.setStyleSheet(self._group_style(group_color))
            grid = QGridLayout(group)
            grid.setContentsMargins(10, 15, 10, 10)
            grid.setSpacing(5)

            row, col = 0, 0
            max_cols = 2

            for unit_key in unit_keys:
                stats = UNIT_STATS.get(unit_key)
                if not stats:
                    continue

                icon = UNIT_ICONS.get(unit_key, "?")
                abbrev = UNIT_ABBREVIATIONS.get(unit_key, unit_key[:3].upper())
                color = UNIT_COLORS.get(unit_key, "#888")
                cost = stats.cost

                btn = QPushButton(f"{icon} {abbrev}\n{cost:.0f}G")
                btn.setMinimumHeight(50)
                btn.setToolTip(
                    f"{unit_key.replace('_', ' ').title()}\n"
                    f"Cost: {cost:.0f} Globi\n"
                    f"Efficacy: {stats.eficacia}\n"
                    f"Click to add to production queue"
                )
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #2a2a2a;
                        border: 2px solid {color};
                        border-radius: 4px;
                        color: #ddd;
                        font-size: 11px;
                        padding: 5px;
                    }}
                    QPushButton:hover {{
                        background-color: #3a3a3a;
                        border-color: {color};
                    }}
                    QPushButton:pressed {{
                        background-color: {color};
                    }}
                    QPushButton:disabled {{
                        background-color: #1a1a1a;
                        border-color: #333;
                        color: #555;
                    }}
                """)

                btn.clicked.connect(
                    lambda checked, k=unit_key: self._enqueue_unit(k)
                )

                grid.addWidget(btn, row, col)
                self.recruit_buttons[unit_key] = btn

                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1

            scroll_layout.addWidget(group)

        # --- Unidades presentes ---
        group_units = QGroupBox("🗺️ Units in Province")
        group_units.setStyleSheet(self._group_style("#64B5F6"))
        layout_units = QVBoxLayout(group_units)

        self.table_units = QTableWidget(0, 3)
        self.table_units.setHorizontalHeaderLabels(["Unit Type", "Count", "Category"])
        self.table_units.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_units.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_units.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_units.setMaximumHeight(180)
        self.table_units.setStyleSheet("""
            QTableWidget {
                background-color: #2a2a2a; border: 1px solid #3a3a3a; gridline-color: #3a3a3a;
            }
            QTableWidget::item { padding: 5px; }
            QHeaderView::section {
                background-color: #333; color: #ddd; padding: 5px; border: 1px solid #3a3a3a;
            }
        """)
        layout_units.addWidget(self.table_units)

        self.label_units_summary = QLabel("No units")
        self.label_units_summary.setWordWrap(True)
        self.label_units_summary.setStyleSheet("""
            color: #aaa; font-size: 11px; padding: 5px;
            background-color: #252525; border-radius: 3px;
        """)
        layout_units.addWidget(self.label_units_summary)

        scroll_layout.addWidget(group_units)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        return widget

    # =====================================================================
    # CARREGAMENTO DE DADOS
    # =====================================================================

    def _load_province_data(self):
        """Carrega todos os dados da província na interface."""
        prov = self.province
        planet = self.planet
        if not prov or not planet:
            return

        tile = prov.tile_coords

        # --- Header ---
        prefix = "⭐ " if prov.is_capital else "🏘️ "
        self.title_label.setText(f"{prefix}{prov.name}")

        # --- Overview: Info básica ---
        node_data = {}
        if planet.graph.has_node(tile):
            node_data = planet.graph.nodes[tile]

        self.label_coordinates.setText(f"Coordinates: {tile}")

        biome = node_data.get("bioma", "—")
        allowed_cats = self._get_allowed_categories_for_biome(biome, tile, planet)
        self.label_biome.setText(f"Biome: {biome} ({allowed_cats})")

        if "temperatura" in node_data:
            self.label_temperature.setText(f"Temperature: {node_data['temperatura']:.1f} °C")
        else:
            self.label_temperature.setText("Temperature: —")

        self.label_humidity.setText(
            f"Humidity: {node_data.get('umidade', '—').capitalize()}"
        )
        self.label_altitude.setText(
            f"Altitude: {node_data.get('altitude', '—').capitalize()}"
        )

        if "fertilidade" in node_data:
            self.label_fertility.setText(f"Fertility: {node_data['fertilidade']:.2f}")
        else:
            self.label_fertility.setText("Fertility: —")

        plate = node_data.get("placa", "—")
        greek = node_data.get("letra_grega", "")
        self.label_plate.setText(
            f"Tectonic Plate: {plate} ({greek})" if greek else f"Tectonic Plate: {plate}"
        )

        if prov.owner:
            self.label_civilization.setText(f"Civilization: {prov.owner.name}")
        else:
            self.label_civilization.setText("Civilization: —")

        self.label_is_capital.setText(f"Capital: {'⭐ Yes' if prov.is_capital else 'No'}")

        # --- Overview: Economia ---
        econ = planet.econ_repo.get(tile)
        if econ:
            self.label_workers.setText(str(econ.workers))
            self.label_food.setText(f"{econ.food_output:.1f}")
            self.label_food_type.setText(econ.food_type or "—")
            self.label_ore.setText(f"{econ.ore_output:.1f}")
            self.label_ore_type.setText(econ.ore_type or "—")
        else:
            self.label_workers.setText("0")
            self.label_food.setText("0.0")
            self.label_food_type.setText("—")
            self.label_ore.setText("0.0")
            self.label_ore_type.setText("—")

        # --- Overview: Guarnição resumida ---
        self._update_garrison_summary()

        # --- Military tab ---
        self._update_military_tab()
        self._refresh_military_panel()

        # --- Workforce tab ---
        if hasattr(self, "tab_workforce") and self.tab_workforce:
            try:
                wf = ProvinceWorkforceFacade(planet=planet, province=prov)
                self.tab_workforce.set_facade(wf)
            except Exception as e:
                print(f"⚠️ Workforce facade error: {e}")

        # Status
        self.status_label.setText("Ready")
        self.status_label.setStyleSheet("color: #888; font-size: 11px;")

    # =====================================================================
    # GARRISON SUMMARY (overview tab)
    # =====================================================================

    def _update_garrison_summary(self):
        prov = self.province
        planet = self.planet
        if not prov or not planet:
            self.label_garrison_summary.setText("No units")
            return

        counts = self._count_units_in_tile(prov.tile_coords)
        if not counts:
            self.label_garrison_summary.setText("No units stationed")
            self.label_garrison_summary.setStyleSheet("color: #888; font-style: italic;")
            return

        total = sum(counts.values())
        summary = format_units_by_category(counts)
        self.label_garrison_summary.setText(f"🎖️ {total} unit(s): {summary}")
        self.label_garrison_summary.setStyleSheet("color: #E6E6E6;")

    # =====================================================================
    # MILITARY TAB
    # =====================================================================

    def _update_military_tab(self):
        self.table_units.setRowCount(0)

        prov = self.province
        planet = self.planet
        if not prov or not planet:
            self.label_units_summary.setText("No province selected")
            return

        counts = self._count_units_in_tile(prov.tile_coords)
        if not counts:
            self.label_units_summary.setText("No units in this province")
            return

        for unit_key, count in sorted(counts.items()):
            row = self.table_units.rowCount()
            self.table_units.insertRow(row)

            icon = UNIT_ICONS.get(unit_key, "•")
            display_name = unit_key.replace("_", " ").title()
            cat_name = get_unit_category(unit_key)
            cat_icon = CATEGORY_ICONS.get(cat_name, "")

            self.table_units.setItem(row, 0, QTableWidgetItem(f"{icon} {display_name}"))
            self.table_units.setItem(row, 1, QTableWidgetItem(str(count)))
            self.table_units.setItem(row, 2, QTableWidgetItem(f"{cat_icon} {cat_name}"))

        self.label_units_summary.setText(format_units_by_category(counts))

    def _refresh_military_panel(self):
        """Atualiza os labels de cash e fila de produção."""
        # Cash: não temos tesouro por província na arquitetura atual
        self.label_mil_cash.setText("💰 Cash: N/A")

        # Queue: não temos fila de produção ainda
        self.label_mil_queue.setText("📋 Queue: Empty")

    def _enqueue_unit(self, unit_key: str):
        """
        Tenta enfileirar a produção de uma unidade.
        Por agora, cria a unidade diretamente no tile (spawn imediato)
        já que o sistema de produção/fila ainda não existe na arquitetura atual.
        """
        prov = self.province
        planet = self.planet
        if not prov or not planet:
            return

        tile = prov.tile_coords
        owner = prov.owner
        if not owner:
            self.status_label.setText("❌ No civilization owns this province")
            self.status_label.setStyleSheet("color: #F44336; font-size: 11px;")
            return

        # Validação de bioma
        stats = UNIT_STATS.get(unit_key)
        if not stats:
            self.status_label.setText(f"❌ Unknown unit: {unit_key}")
            self.status_label.setStyleSheet("color: #F44336; font-size: 11px;")
            return

        biome = ""
        if planet.graph.has_node(tile):
            biome = planet.graph.nodes[tile].get("bioma", "")

        cat_name = stats.category.name if hasattr(stats.category, "name") else "LAND"

        if cat_name == "NAVAL":
            # Navais: precisa de tile costeiro ou adjacente a água
            has_water = self._tile_has_water_access(tile, planet)
            if not has_water:
                self.status_label.setText(
                    f"❌ Cannot produce {unit_key}: no water access"
                )
                self.status_label.setStyleSheet("color: #F44336; font-size: 11px;")
                return

        elif cat_name == "LAND":
            # Terrestres: não podem ser produzidos em tiles aquáticos
            water_biomes = {"Ocean", "Sea"}
            if biome in water_biomes:
                self.status_label.setText(
                    f"❌ Cannot produce {unit_key} in {biome}"
                )
                self.status_label.setStyleSheet("color: #F44336; font-size: 11px;")
                return

        # AIR: pode ser produzido em qualquer lugar (sem restrição)

        # Spawn imediato (substituto temporário para fila de produção)
        # Busca ou cria uma stack da civilização no tile
        existing_stacks = planet.stacks.stacks_in_tile(tile)
        target_stack = None
        for s in existing_stacks:
            if s.owner_id == owner.id:
                target_stack = s
                break

        if target_stack is None:
            target_stack = planet.stacks.create_stack(owner_id=owner.id, tile=tile)

        planet.stacks.add_unit_to_stack(target_stack.uid, unit_key)

        # Feedback
        icon = UNIT_ICONS.get(unit_key, "")
        cost = stats.cost
        self.status_label.setText(
            f"✅ Spawned: {icon} {unit_key.replace('_', ' ').title()} ({cost:.0f}G)"
        )
        self.status_label.setStyleSheet("color: #4CAF50; font-size: 11px;")

        # Atualizar tabelas
        self._update_military_tab()
        self._update_garrison_summary()

    # =====================================================================
    # HELPERS
    # =====================================================================

    def _count_units_in_tile(self, tile: tuple[int, int]) -> dict[str, int]:
        """Conta unidades da civilização dona da província no tile."""
        prov = self.province
        planet = self.planet
        if not prov or not planet:
            return {}
        owner_id = prov.owner.id if prov.owner else None
        return count_units_in_tile(planet, tile, owner_id)

    def _tile_has_water_access(self, tile: tuple[int, int], planet: Planet) -> bool:
        """Verifica se o tile é costeiro ou adjacente a um tile aquático."""
        if not planet.graph.has_node(tile):
            return False

        biome = planet.graph.nodes[tile].get("bioma", "")
        water_biomes = {"Coast", "Sea", "Ocean"}

        if biome in water_biomes:
            return True

        # Verifica vizinhos
        for neighbor in planet.graph.neighbors(tile):
            nb_biome = planet.graph.nodes[neighbor].get("bioma", "")
            if nb_biome in water_biomes:
                return True

        return False

    @staticmethod
    def _get_allowed_categories_for_biome(
        biome: str, tile: tuple[int, int], planet: Planet
    ) -> str:
        """Retorna string indicando categorias permitidas (L/N/A)."""
        water_biomes = {"Coast", "Sea", "Ocean"}

        allowed = []

        # Land: permitido em tudo exceto Ocean/Sea
        if biome not in {"Ocean", "Sea"}:
            allowed.append("L")

        # Naval: permitido se o tile é aquático ou adjacente a água
        is_water = biome in water_biomes
        has_water_neighbor = False
        if planet.graph.has_node(tile):
            for nb in planet.graph.neighbors(tile):
                if planet.graph.nodes[nb].get("bioma", "") in water_biomes:
                    has_water_neighbor = True
                    break
        if is_water or has_water_neighbor:
            allowed.append("N")

        # Air: permitido em qualquer lugar
        allowed.append("A")

        return "/".join(allowed) if allowed else "None"

    def _emit_go_to(self):
        if self.province:
            self.go_to_province_requested.emit(self.province)

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
