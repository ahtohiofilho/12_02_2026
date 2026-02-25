# ui/sidebar.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget
from .civ_manager import CivilizationManagerWidget
from .province.detail_panel import ProvinceDetailPanel
from .selection_panel import SelectionPanel


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
        self.province_detail = ProvinceDetailPanel(self.controller)
        self.stacked_widget.addWidget(self.province_detail)

        # Índice 3: Painel de seleção/comando militar
        self.selection_panel = SelectionPanel(self.controller)
        self.stacked_widget.addWidget(self.selection_panel)

        # ── Snapshot da tela antes da seleção ──
        self._pre_selection_page: int | None = None
        self._pre_selection_tab: int | None = None

        # === CONEXÕES INTERNAS ===
        self.civ_manager_view.province_selected.connect(self._on_province_selected)
        self.province_detail.back_requested.connect(self._on_back_from_province)
        self.province_detail.go_to_province_requested.connect(self._on_go_to_province)

        # Conexões do SelectionPanel
        self.selection_panel.back_requested.connect(self._on_back_from_selection)
        self.selection_panel.cancel_command_requested.connect(self._on_cancel_command)
        self.selection_panel.go_to_tile_requested.connect(self._on_go_to_tile)

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

    # ================================================================
    # SNAPSHOT — memorizar / restaurar tela
    # ================================================================

    def _save_screen_snapshot(self) -> None:
        """Salva a página atual e a aba ativa (se for province_detail)."""
        current = self.stacked_widget.currentIndex()

        # Só salva se não estiver já no selection panel (evita sobrescrever)
        if current == 3:
            return

        self._pre_selection_page = current

        # Se estava no painel de província, salva a aba ativa
        if current == 2:
            self._pre_selection_tab = self.province_detail.tab_widget.currentIndex()
        else:
            self._pre_selection_tab = None

    def _restore_screen_snapshot(self) -> None:
        """Restaura a página e aba que estavam ativas antes da seleção."""
        if self._pre_selection_page is not None:
            self.stacked_widget.setCurrentIndex(self._pre_selection_page)

            # Restaurar aba do province detail se aplicável
            if self._pre_selection_page == 2 and self._pre_selection_tab is not None:
                self.province_detail.tab_widget.setCurrentIndex(self._pre_selection_tab)
        else:
            # Fallback: volta para o civ manager
            self.stacked_widget.setCurrentIndex(1)

        # Limpa snapshot
        self._pre_selection_page = None
        self._pre_selection_tab = None

    # ================================================================
    # NAVEGAÇÃO
    # ================================================================

    def on_planet_loaded(self, success: bool):
        if success and self.controller.game:
            civ = self.controller.game.player_civ
            planet = self.controller.game
            self.civ_manager_view.set_data(civ, planet)
            self.stacked_widget.setCurrentIndex(1)
        else:
            self.stacked_widget.setCurrentIndex(0)

    def _on_province_selected(self, province):
        planet = self.controller.game
        if not planet:
            return
        self.province_detail.set_province(province, planet)
        self.stacked_widget.setCurrentIndex(2)

    def _on_back_from_province(self):
        self.stacked_widget.setCurrentIndex(1)

    def _on_go_to_province(self, province):
        planet = self.controller.game
        if not planet:
            return
        camera = self.controller.camera
        if not camera:
            return
        tile_centers = planet.centers_map
        if province.tile_coords not in tile_centers:
            return
        center_3d = tile_centers[province.tile_coords]
        camera.look_at_tile(center_3d)
        if self.controller.scene:
            self.controller.scene.update()

    # ================================================================
    # SELECTION PANEL
    # ================================================================

    def show_selection_panel(self):
        """Memoriza a tela atual e abre o painel de seleção."""
        self._save_screen_snapshot()
        self.selection_panel.update_from_selection(self.controller)
        self.stacked_widget.setCurrentIndex(3)

    def update_selection_panel(self):
        """Atualiza o painel de seleção se estiver visível."""
        if self.stacked_widget.currentIndex() == 3:
            self.selection_panel.update_from_selection(self.controller)

    def hide_selection_panel(self):
        """Restaura a tela que estava aberta antes da seleção."""
        if self.stacked_widget.currentIndex() == 3:
            self._restore_screen_snapshot()

    def _on_back_from_selection(self):
        """◀ Back no painel de seleção → restaura tela anterior."""
        self.controller.selection.clear()
        self.controller._clear_route_overlay()
        if self.controller.scene:
            self.controller.scene.update()
        self._restore_screen_snapshot()

    def _on_cancel_command(self):
        """Cancela o comando pendente da stack selecionada."""
        ctrl = self.controller
        if ctrl.game and ctrl.selection.has_selection:
            ctrl.game.command_manager.cancel_command(ctrl.selection.selected_stack_uid)
            ctrl._clear_route_overlay()
            ctrl.selection.preview_path = None
            print("🚫 Comando cancelado via painel.")

        self.update_selection_panel()
        if ctrl.scene:
            ctrl.scene.update()

    def _on_go_to_tile(self, tile_coords):
        """Centraliza a câmera no tile da stack selecionada."""
        planet = self.controller.game
        camera = self.controller.camera
        if not planet or not camera:
            return
        center_3d = planet.centers_map.get(tile_coords)
        if center_3d:
            camera.look_at_tile(center_3d)
            if self.controller.scene:
                self.controller.scene.update()
