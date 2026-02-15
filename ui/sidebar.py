# ui/sidebar.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QStackedWidget
from .civ_manager import CivilizationManagerWidget


class SideBar(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller

        # Layout principal da sidebar
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Usamos um QStackedWidget para alternar entre o menu inicial e o painel do jogo
        self.stacked_widget = QStackedWidget()
        self.layout.addWidget(self.stacked_widget)

        # Widget do Menu Inicial (índice 0)
        self.menu_widget = self._create_menu_widget()
        self.stacked_widget.addWidget(self.menu_widget)

        # Widget de Gerenciamento da Civilização (índice 1)
        # Este painel é criado mas fica escondido até um planeta ser carregado
        self.civ_manager_view = CivilizationManagerWidget(self.controller)
        self.stacked_widget.addWidget(self.civ_manager_view)

    def _create_menu_widget(self):
        """Cria o widget do menu inicial com 'Criar Planeta' e 'Sair'."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.btn_create = QPushButton("🌌 Create Planet")
        layout.addWidget(self.btn_create)

        self.btn_exit = QPushButton("🚪 Exit")
        layout.addWidget(self.btn_exit)

        layout.addStretch()
        return widget

    def on_planet_loaded(self, success: bool):
        """
        Slot que é chamado pelo Controller quando um planeta é carregado (ou falha).
        Alterna a visão do QStackedWidget.
        """
        # === CORREÇÃO APLICADA AQUI ===
        # Trocamos self.controller.current_planet por self.controller.game
        if success and self.controller.game:
            print("SideBar: Planeta carregado, configurando painel da civilização.")

            # Pega os dados da civilização e do planeta a partir do 'game'
            civ = self.controller.game.player_civ
            planet = self.controller.game

            # Passa os dados para o painel de gerenciamento
            self.civ_manager_view.set_data(civ, planet)

            # Alterna para a visão do painel do jogo (índice 1)
            self.stacked_widget.setCurrentIndex(1)
        else:
            print("SideBar: Falha ao carregar planeta, mostrando menu inicial.")
            # Em caso de falha, volta para o menu inicial (índice 0)
            self.stacked_widget.setCurrentIndex(0)

