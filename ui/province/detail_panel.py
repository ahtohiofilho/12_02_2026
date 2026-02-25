# ui/province/detail_panel.py
"""
Widget de gerenciamento de província com abas.
Serve como um orquestrador, delegando a lógica específica de cada
aba para seus próprios widgets e facades, garantindo modularidade e
separação de concerns.
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
    CATEGORY_ICONS,
    count_units_in_tile,
    format_units_by_category,
    get_unit_category,
)# === NOVAS IMPORTAÇÕES PARA ARQUITETURA MODULAR ===
from ui.province.workforce_tab import WorkforceTabWidget
from ui.province.trade_tab import TradeTabWidget
from core.workforce.facade import ProvinceWorkforceFacade
from core.trade.facade import ProvinceTradeFacade
from ui.province.combat_preview import CombatPreviewWidget


# ===================================================


class ProvinceDetailPanel(QWidget):
    """
    Widget de gerenciamento de uma província individual com abas.
    """

    back_requested = Signal()
    go_to_province_requested = Signal(object)  # emite Province

    def __init__(self, controller, parent=None):  # 1. Adicione 'controller' e mantenha 'parent=None'
        super().__init__(parent)  # 2. Passe 'parent' para o super()

        self.province: Province | None = None
        self.planet: Planet | None = None
        self.controller = controller  # 3. Armazene o controller

        # Facades...
        self.workforce_facade: ProvinceWorkforceFacade | None = None
        self.trade_facade: ProvinceTradeFacade | None = None

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._init_ui()

    def update_display(self) -> None:
        """
        Atualiza o painel com base no estado atual do planet/econ_repo.
        Seguro chamar a qualquer momento (ex: após avanço de turno).
        """
        self._load_province_data()

    def set_province(self, province: Province, planet: Planet):
        """Define a província e o planeta, cria as facades e atualiza as abas."""
        self.province = province
        self.planet = planet

        try:
            # 1. Cria a facade para Workforce e a passa para a aba correspondente
            self.workforce_facade = ProvinceWorkforceFacade(planet=planet, province=province)
            if hasattr(self.workforce_tab, 'set_facade'):
                self.workforce_tab.set_facade(self.workforce_facade)

            # 2. Cria a facade para Trade e a passa para a aba correspondente
            self.trade_facade = ProvinceTradeFacade(planet=planet, province=province)
            if hasattr(self.trade_tab, 'set_facade'):
                self.trade_tab.set_facade(self.trade_facade)

        except Exception as e:
            print(f"⚠️ Erro ao criar facades: {e}")

        self._load_province_data()

    # =====================================================================
    # LAYOUT PRINCIPAL E CRIAÇÃO DAS ABAS
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

        # Tab 0: Overview (continua aqui por ser simples)
        self.tab_overview = self._create_overview_tab()
        self.tab_widget.addTab(self.tab_overview, "📊 Overview")

        # Tab 1: Workforce (instância da classe dedicada)
        self.workforce_tab = WorkforceTabWidget(self.controller)
        self.tab_widget.addTab(self.workforce_tab, "👷 Workforce")

        # Tab 2: Trade (instância da classe dedicada)
        self.trade_tab = TradeTabWidget(self.controller)
        self.tab_widget.addTab(self.trade_tab, "🔄 Trade")

        # Tab 3: Military (continua aqui, mas poderia ser modularizado)
        self.tab_military = self._create_military_tab()
        self.tab_widget.addTab(self.tab_military, "⚔️ Military")

        # Tab 4: Aba de análise de chance de vitória
        self.tab_combat = CombatPreviewWidget()
        self.tab_widget.addTab(self.tab_combat, "🎲 Combat")

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

        # Caixa e receita do último turno (acumulado)
        layout_economy.addWidget(QLabel("💰 Cash:"), 5, 0)
        self.label_cash = QLabel("0.0")
        self.label_cash.setStyleSheet("color: #FFD700; font-weight: bold;")
        self.label_cash.setAlignment(Qt.AlignRight)
        layout_economy.addWidget(self.label_cash, 5, 1)

        layout_economy.addWidget(QLabel("📈 Last Revenue:"), 6, 0)
        self.label_last_revenue = QLabel("0.0")
        self.label_last_revenue.setStyleSheet("color: #aaa;")
        self.label_last_revenue.setAlignment(Qt.AlignRight)
        layout_economy.addWidget(self.label_last_revenue, 6, 1)

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
    # TAB: MILITARY
    # =====================================================================

    def _create_military_tab(self) -> QWidget:
        """
        Military tab:
          - Recruitment buttons grouped by category (LAND/NAVAL/AIR)
          - Units present in the province (table + summary)
          - Uses ui.province.military_ui as the single source of truth for icons/colors/display names.
        """
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

        # --- Recruitment by category ---
        # NOTE: icons/colors/names come from ui.province.military_ui
        from ui.province.military_ui import (
            UNIT_ICONS,
            UNIT_COLORS,
            UNITS_BY_CATEGORY,
            get_unit_display_name,
        )

        category_meta = {
            "LAND": ("⚔️ Land Units", "#4CAF50"),
            "NAVAL": ("⚓ Naval Units", "#2196F3"),
            "AIR": ("✈️ Air Units", "#9C27B0"),
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

                icon = UNIT_ICONS.get(unit_key, "•")
                color = UNIT_COLORS.get(unit_key, "#888")
                cost = float(stats.cost)

                display_name = get_unit_display_name(unit_key)

                btn = QPushButton(f"{icon} {display_name}\n{cost:.0f}G")
                btn.setMinimumHeight(54)
                btn.setToolTip(
                    f"{display_name}\n"
                    f"Key: {unit_key}\n"
                    f"Cost: {cost:.0f} Globi\n"
                    f"Efficacy: {float(stats.eficacia):.2f}\n"
                    f"Movement: {int(stats.movement)}\n"
                    f"Click to add to production queue"
                )
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #2a2a2a;
                        border: 2px solid {color};
                        border-radius: 4px;
                        color: #ddd;
                        font-size: 11px;
                        padding: 6px;
                        text-align: center;
                    }}
                    QPushButton:hover {{
                        background-color: #3a3a3a;
                        border-color: {color};
                    }}
                    QPushButton:pressed {{
                        background-color: {color};
                        color: #111;
                    }}
                    QPushButton:disabled {{
                        background-color: #1a1a1a;
                        border-color: #333;
                        color: #555;
                    }}
                """)

                # IMPORTANT: capture unit_key in default arg (avoid late-binding lambda bug)
                btn.clicked.connect(lambda checked=False, k=unit_key: self._enqueue_unit(k))

                grid.addWidget(btn, row, col)
                self.recruit_buttons[unit_key] = btn

                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1

            scroll_layout.addWidget(group)

        # --- Units present ---
        from ui.province.military_ui import CATEGORY_ICONS  # for the table display

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
        """Carrega dados gerais e pede para as abas se atualizarem."""
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
        self.label_humidity.setText(f"Humidity: {node_data.get('umidade', '—').capitalize()}")
        self.label_altitude.setText(f"Altitude: {node_data.get('altitude', '—').capitalize()}")
        if "fertilidade" in node_data:
            self.label_fertility.setText(f"Fertility: {node_data['fertilidade']:.2f}")
        plate = node_data.get("placa", "—")
        greek = node_data.get("letra_grega", "")
        self.label_plate.setText(f"Tectonic Plate: {plate} ({greek})" if greek else f"Tectonic Plate: {plate}")
        self.label_civilization.setText(f"Civilization: {prov.owner.name}" if prov.owner else "Civilization: —")
        self.label_is_capital.setText(f"Capital: {'⭐ Yes' if prov.is_capital else 'No'}")

        # --- Overview: Economia ---
        econ = planet.econ_repo.get(tile)
        if econ:
            self.label_workers.setText(str(econ.workers))
            self.label_food.setText(f"{econ.food_output:.1f}")
            self.label_food_type.setText(econ.food_type or "—")
            self.label_ore.setText(f"{econ.ore_output:.1f}")
            self.label_ore_type.setText(econ.ore_type or "—")
            # Caixa e receita do último turno
            self.label_cash.setText(f"{float(econ.treasury):.1f}")
            self.label_last_revenue.setText(f"{float(econ.last_revenue):.1f}")
        else:
            self.label_workers.setText("0")
            self.label_food.setText("0.0")
            self.label_food_type.setText("—")
            self.label_ore.setText("0.0")
            self.label_ore_type.setText("—")
            self.label_cash.setText("—")
            self.label_last_revenue.setText("—")

        # --- DISPARA ATUALIZAÇÃO NAS ABAS MODULARES ---
        if hasattr(self.workforce_tab, 'update_display'):
            self.workforce_tab.update_display()
        if hasattr(self.trade_tab, 'update_display'):
            self.trade_tab.update_display()

        # --- ATUALIZA ABAS QUE AINDA SÃO INTERNAS ---
        self._update_garrison_summary()
        self._update_military_tab()
        self._refresh_military_panel()

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
        if not self.province or not self.planet:
            self.label_mil_cash.setText("💰 Cash: —")
            self.label_mil_queue.setText("📋 Queue: —")
            return

        tile = self.province.tile_coords
        econ = self.planet.econ_repo.get(tile)
        cash = float(econ.treasury) if econ else 0.0

        q = self.planet.production_queues.get(tile) if hasattr(self.planet.production_queues, "get") else None
        if q is None:
            # fallback: acessar dict interno (como você fez no Planet.process_production)
            q = self.planet.production_queues._by_tile.get(tile)

        queue_len = len(getattr(q, "items", []) or [])

        self.label_mil_cash.setText(f"💰 Cash: {cash:.1f}")
        self.label_mil_queue.setText(f"📋 Queue: {queue_len} item(s)")

    def _enqueue_unit(self, unit_key: str):
        """Tenta enfileirar a produção de uma unidade usando a facade de workforce."""
        if not self.workforce_facade or not self.province or not self.planet:
            return

        # Correção do Erro 3: usa self.workforce_facade
        if not self.province or not self.planet or not self.workforce_facade:
            return

        tile = self.province.tile_coords
        owner = self.province.owner
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
        if self.planet.graph.has_node(tile):
            biome = self.planet.graph.nodes[tile].get("bioma", "")

        cat_name = stats.category.name if hasattr(stats.category, "name") else "LAND"

        if cat_name == "NAVAL":
            has_water = self._tile_has_water_access(self.planet, tile) # Corrigido para passar planet
            if not has_water:
                self.status_label.setText(f"❌ Cannot produce {unit_key}: no water access")
                self.status_label.setStyleSheet("color: #F44336; font-size: 11px;")
                return
        elif cat_name == "LAND":
            water_biomes = {"Ocean", "Sea"}
            if biome in water_biomes:
                self.status_label.setText(f"❌ Cannot produce {unit_key} in {biome}")
                self.status_label.setStyleSheet("color: #F44336; font-size: 11px;")
                return

        # Correção do Erro 2: Bloco com indentação correta
        # Lógica de enfileiramento usando a facade
        ok = self.workforce_facade.enqueue_military_unit(unit_key)

        if ok:
            stats = UNIT_STATS.get(unit_key)
            cost = stats.cost if stats else 0
            icon = UNIT_ICONS.get(unit_key, "")
            self.status_label.setText(f"✅ Queued: {icon} {unit_key.replace('_', ' ').title()} ({cost:.0f}G)")
            self.status_label.setStyleSheet("color: #4CAF50; font-size: 11px;")
            if hasattr(self.workforce_tab, 'update_display'):
                self.workforce_tab.update_display()
            self.update_display()
        else:
            self.status_label.setText(f"❌ Failed to queue {unit_key}")
            self.status_label.setStyleSheet("color: #F44336; font-size: 11px;")

    # =====================================================================
    # HELPERS
    # =====================================================================

    def _count_units_in_tile(self, tile: tuple[int, int]) -> dict[str, int]:
        """Helper para chamar a função de contagem de unidades."""
        if not self.province or not self.planet:
            return {}
        owner_id = self.province.owner.id if self.province.owner else None
        return count_units_in_tile(self.planet, tile, owner_id)

    def _tile_has_water_access(self, planet: Planet, tile: tuple[int, int]) -> bool:
        """Verifica se um tile tem acesso a um corpo d'água adjacente."""
        if not planet.graph.has_node(tile):
            return False

        water_biomes = {"Coast", "Sea", "Ocean"}
        if planet.graph.nodes[tile].get("bioma", "") in water_biomes:
            return True

        for neighbor in planet.graph.neighbors(tile):
            nb_biome = planet.graph.nodes[neighbor].get("bioma", "")
            if nb_biome in water_biomes:
                return True
        return False

    @staticmethod
    def _get_allowed_categories_for_biome(
            biome: str, tile: tuple[int, int], planet: Planet
    ) -> str:
        """Determina as categorias de unidades (Terrestre, Naval, Aérea) permitidas em um bioma."""
        water_biomes = {"Coast", "Sea", "Ocean"}
        allowed = []

        if biome not in {"Ocean", "Sea"}:
            allowed.append("L")  # Land

        is_water = biome in water_biomes
        has_water_neighbor = False
        if planet.graph.has_node(tile):
            for nb in planet.graph.neighbors(tile):
                if planet.graph.nodes[nb].get("bioma", "") in water_biomes:
                    has_water_neighbor = True
                    break

        if is_water or has_water_neighbor:
            allowed.append("N")  # Naval

        allowed.append("A")  # Air

        return "/".join(allowed) if allowed else "None"

    def _emit_go_to(self):
        """Emite o sinal para centrar a câmera na província."""
        if self.province:
            self.go_to_province_requested.emit(self.province)

    @staticmethod
    def _group_style(color: str) -> str:
        """Retorna o CSS para um QGroupBox estilizado."""
        return f"""
            QGroupBox {{
                font-weight: bold; border: 1px solid #3a3a3a; border-radius: 5px;
                margin-top: 10px; padding-top: 10px; background-color: #252525;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; left: 10px; padding: 0 5px; color: {color};
            }}
        """
