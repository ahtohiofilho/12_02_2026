# ui/civ_manager.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTabWidget, QGroupBox, QPushButton, QFrame,
    QGridLayout, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap

from core.planet import Planet
from core.civilization import Civilization
from ui.widgets import compact_button


class CivilizationManagerWidget(QWidget):
    """
    Painel de gerenciamento da civilização do jogador, adaptado para a nova estrutura.
    Exibe informações de overview, províncias, exército e diplomacia.
    """
    province_selected = Signal(object)  # Emitirá um objeto Province

    # 1. DECLARAR O SINAL QUE ESTAVA FALTANDO.
    go_to_capital_requested = Signal()

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.current_civ: Civilization | None = None
        self.current_planet: Planet | None = None

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._init_ui()

    def set_data(self, civ: Civilization, planet: Planet):
        """
        Define a civilização e o planeta a serem gerenciados.
        """
        self.current_civ = civ
        self.current_planet = planet
        self.update_display()

    def _init_ui(self):
        """Inicializa a interface do widget."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header com bandeira, nome e turno
        self.header_frame = self._create_header()
        layout.addWidget(self.header_frame)

        # Abas de Gerenciamento
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #3a3a3a; background-color: #2a2a2a; }
            QTabBar::tab { background-color: #333; color: #ccc; padding: 8px 16px; margin-right: 2px; }
            QTabBar::tab:selected { background-color: #2a2a2a; color: #fff; border-bottom: 2px solid #4CAF50; }
            QTabBar::tab:hover { background-color: #3a3a3a; }
        """)

        self.tab_overview = self._create_overview_tab()
        self.tab_widget.addTab(self.tab_overview, "📊 Overview")

        self.tab_widget.addTab(QWidget(), "🏛️ Provinces")
        self.tab_widget.addTab(QWidget(), "⚔️ Military")
        self.tab_widget.addTab(QWidget(), "🤝 Diplomacy")

        layout.addWidget(self.tab_widget, 1)

        # Rodapé com controles do jogo
        self.footer_frame = self._create_footer()
        layout.addWidget(self.footer_frame)

    def _create_header(self) -> QFrame:
        """Cria o header com bandeira, nome e informações de turno."""
        frame = QFrame()
        frame.setStyleSheet("background-color: #2a2a2a; border-bottom: 2px solid #4CAF50;")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.flag_label = QLabel()
        self.flag_label.setFixedSize(48, 30)
        self.flag_label.setStyleSheet("border: 2px solid #555; border-radius: 3px; background-color: #333;")
        layout.addWidget(self.flag_label)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        self.name_label = QLabel("Civilization")
        self.name_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.name_label.setStyleSheet("color: #4CAF50; border: none;")
        info_layout.addWidget(self.name_label)

        layout.addLayout(info_layout, 1)

        turn_layout = QVBoxLayout()
        turn_layout.setAlignment(Qt.AlignTop | Qt.AlignRight)

        self.turn_label = QLabel("Turn 0")
        self.turn_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.turn_label.setStyleSheet("color: #FFD700; border: none;")
        turn_layout.addWidget(self.turn_label, 0, Qt.AlignRight)

        layout.addLayout(turn_layout)

        return frame

    def _create_footer(self) -> QFrame:
        """Cria o rodapé com botões de salvar, menu, etc. (botões compactos: texto + padding)."""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QSizePolicy

        def _compact_button(text: str) -> QPushButton:
            b = QPushButton(text)
            # não expandir horizontalmente; altura fixa pelo estilo/min-height do QSS
            b.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
            b.adjustSize()
            return b

        frame = QFrame()
        frame.setStyleSheet("background-color: #252525; border-top: 1px solid #3a3a3a;")

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        btn_save = _compact_button("💾 Save")
        layout.addWidget(btn_save, 0, Qt.AlignLeft)

        layout.addStretch()

        btn_menu = _compact_button("🔙 Menu")
        layout.addWidget(btn_menu, 0, Qt.AlignRight)

        btn_exit = _compact_button("🚪 Exit")
        btn_exit.clicked.connect(self.controller.app.quit)
        layout.addWidget(btn_exit, 0, Qt.AlignRight)

        return frame

    def _create_overview_tab(self) -> QWidget:
        """Cria a aba de "Visão Geral" com estatísticas e economia."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Grupo: Estatísticas
        group_stats = QGroupBox("📈 Statistics")
        stats_layout = QGridLayout(group_stats)
        stats_layout.addWidget(QLabel("🏛️ Provinces:"), 0, 0)
        self.label_provinces_count = QLabel("0")
        stats_layout.addWidget(self.label_provinces_count, 0, 1)
        stats_layout.addWidget(QLabel("👥 Total Workers:"), 1, 0)
        self.label_total_workers = QLabel("0")
        stats_layout.addWidget(self.label_total_workers, 1, 1)
        stats_layout.addWidget(QLabel("⚔️ Military Units:"), 2, 0)
        self.label_military_units = QLabel("0")
        stats_layout.addWidget(self.label_military_units, 2, 1)
        layout.addWidget(group_stats)

        # Grupo: Economia
        group_economy = QGroupBox("💰 Economy")
        economy_layout = QGridLayout(group_economy)
        economy_layout.addWidget(QLabel("💵 Total Treasury:"), 0, 0)
        self.label_total_treasury = QLabel("N/A")
        economy_layout.addWidget(self.label_total_treasury, 0, 1)
        economy_layout.addWidget(QLabel("📈 Last Income:"), 1, 0)
        self.label_last_income = QLabel("N/A")
        economy_layout.addWidget(self.label_last_income, 1, 1)
        economy_layout.addWidget(QLabel("🌾 Food Production:"), 2, 0)
        self.label_food_production = QLabel("0.0")
        economy_layout.addWidget(self.label_food_production, 2, 1)
        economy_layout.addWidget(QLabel("⛏️ Ore Production:"), 3, 0)
        self.label_ore_production = QLabel("0.0")
        economy_layout.addWidget(self.label_ore_production, 3, 1)
        layout.addWidget(group_economy)

        # Grupo: Capital
        group_capital = QGroupBox("⭐ Capital")
        capital_layout = QVBoxLayout(group_capital)
        self.label_capital_info = QLabel("No capital")
        capital_layout.addWidget(self.label_capital_info)

        self.btn_go_to_capital = compact_button("📍 Go to Capital")
        self.btn_go_to_capital.clicked.connect(self.go_to_capital_requested.emit)
        capital_layout.addWidget(self.btn_go_to_capital, 0, Qt.AlignLeft)
        layout.addWidget(group_capital)
        layout.addStretch()
        return widget

    def update_display(self):
        if not self.current_civ or not self.current_planet:
            return
        self._update_header()
        self._update_overview()

    def _update_header(self):
        self.name_label.setText(self.current_civ.name)
        self.turn_label.setText(f"Turn {self.current_planet.turn_engine.turn_number}")

    def _update_overview(self):
        civ = self.current_civ
        planet = self.current_planet
        self.label_provinces_count.setText(str(len(civ.provinces)))
        civ_province_tiles = {p.tile_coords for p in civ.provinces}
        total_workers = sum(
            econ_state.workers
            for econ_state in planet.econ_repo.all()
            if econ_state.tile in civ_province_tiles
        )
        self.label_total_workers.setText(str(total_workers))
        total_units = sum(
            len(stack.units)
            for stack in planet.stacks.stacks_by_uid.values()
            if stack.owner_id == civ.id
        )
        self.label_military_units.setText(str(total_units))
        self.label_total_treasury.setText("N/A")
        self.label_last_income.setText("N/A")
        total_food = sum(
            s.food_output for s in planet.econ_repo.all() if s.tile in civ_province_tiles
        )
        total_ore = sum(
            s.ore_output for s in planet.econ_repo.all() if s.tile in civ_province_tiles
        )
        self.label_food_production.setText(f"{total_food:.1f}")
        self.label_ore_production.setText(f"{total_ore:.1f}")
        capital_coords = civ.capital_coords
        capital_province = next((p for p in civ.provinces if p.tile_coords == capital_coords), None)
        if capital_province:
            capital_econ = planet.econ_repo.get(capital_coords)
            workers_in_capital = capital_econ.workers if capital_econ else 0
            self.label_capital_info.setText(
                f"📍 {capital_province.name}\n"
                f"Coords: {capital_coords}\n"
                f"Workers: {workers_in_capital}"
            )
            # Garantir que o botão esteja habilitado
            self.btn_go_to_capital.setEnabled(True)
        else:
            self.label_capital_info.setText("Capital not found")
            # Desabilitar o botão se não houver capital
            self.btn_go_to_capital.setEnabled(False)

        self.update()  # Força um repaint para garantir a atualização visual
