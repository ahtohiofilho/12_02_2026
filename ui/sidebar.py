# ui/sidebar.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget
from .civ_manager import CivilizationManagerWidget
from .province.detail_panel import ProvinceDetailPanel


class SideBar(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.stacked_widget = QStackedWidget()
        self.layout.addWidget(self.stacked_widget)

        # Índice 0: Menu inicial
        self.menu_widget = self._create_menu_widget()
        self.stacked_widget.addWidget(self.menu_widget)

        # Índice 1: Gerenciamento da civilização
        self.civ_manager_view = CivilizationManagerWidget(self.controller)
        self.stacked_widget.addWidget(self.civ_manager_view)

        # Índice 2: Detalhe da província
        self.province_detail = ProvinceDetailPanel()
        self.stacked_widget.addWidget(self.province_detail)

        # === CONEXÕES INTERNAS ===
        print("SideBar: Conectando province_selected ao handler...")
        self.civ_manager_view.province_selected.connect(self._on_province_selected)
        self.province_detail.back_requested.connect(self._on_back_from_province)
        self.province_detail.go_to_province_requested.connect(self._on_go_to_province)
        print("SideBar: Conexões internas estabelecidas.")

    def _create_menu_widget(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QWidget, QGridLayout
        from ui.widgets import compact_button

        widget = QWidget()
        grid = QGridLayout(widget)
        grid.setContentsMargins(16, 16, 16, 16)
        grid.setSpacing(12)

        grid.setRowStretch(0, 0)
        grid.setRowStretch(1, 1)
        grid.setRowStretch(2, 0)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 0)
        grid.setColumnStretch(2, 1)

        self.btn_create = compact_button("🌌 Create Planet")
        grid.addWidget(self.btn_create, 0, 1, alignment=Qt.AlignHCenter | Qt.AlignTop)

        self.btn_exit = compact_button("🚪 Exit")
        self.btn_exit.setObjectName("dangerButton")
        grid.addWidget(self.btn_exit, 2, 2, alignment=Qt.AlignRight | Qt.AlignBottom)

        return widget

    def on_planet_loaded(self, success: bool):
        if success and self.controller.game:
            print("SideBar: Planeta carregado, configurando painel da civilização.")
            civ = self.controller.game.player_civ
            planet = self.controller.game
            self.civ_manager_view.set_data(civ, planet)
            self.stacked_widget.setCurrentIndex(1)
        else:
            print("SideBar: Falha ao carregar planeta, mostrando menu inicial.")
            self.stacked_widget.setCurrentIndex(0)

    def _on_province_selected(self, province):
        """Abre o painel de detalhes da província."""
        print(f"SideBar: Abrindo detalhes da província '{province.name}'")
        planet = self.controller.game
        if not planet:
            print("SideBar: ERRO - planet é None!")
            return
        self.province_detail.set_province(province, planet)
        self.stacked_widget.setCurrentIndex(2)
        print(f"SideBar: Índice do stacked_widget agora = {self.stacked_widget.currentIndex()}")

    def _on_back_from_province(self):
        """Volta do detalhe da província para o civ manager."""
        print("SideBar: Voltando para o painel da civilização.")
        self.stacked_widget.setCurrentIndex(1)

    def _on_go_to_province(self, province):
        """Move a câmera para a província selecionada."""
        planet = self.controller.game
        if not planet:
            return

        camera = self.controller.camera
        if not camera:
            return

        tile_centers = planet.centers_map
        if province.tile_coords not in tile_centers:
            print(f"⚠️ Coordenada 3D para {province.tile_coords} não encontrada.")
            return

        center_3d = tile_centers[province.tile_coords]
        print(f"SideBar: Movendo câmera para '{province.name}' em {province.tile_coords}")
        camera.look_at_tile(center_3d)

        if self.controller.window and self.controller.window.scene:
            self.controller.window.scene.update()
