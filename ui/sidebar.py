# ui/sidebar.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget
from .civ_manager import CivilizationManagerWidget
from .province.detail_panel import ProvinceDetailPanel
from .selection_panel import SelectionPanel
from PySide6.QtCore import Signal


class SideBar(QWidget):
    stack_selected = Signal(str)
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

        # Estado do "tile stacks" (inicializa para evitar estado fantasma)
        self._tile_stacks_tile = None
        self._tile_stacks_uids: list[str] = []
        self._active_stack_uid: str | None = None

        # === CONEXÕES INTERNAS ===
        self.civ_manager_view.province_selected.connect(self._on_province_selected)
        self.province_detail.back_requested.connect(self._on_back_from_province)
        self.province_detail.go_to_province_requested.connect(self._on_go_to_province)

        # Conexões do SelectionPanel
        self.selection_panel.back_requested.connect(self._on_back_from_selection)
        self.selection_panel.cancel_command_requested.connect(self._on_cancel_command)
        self.selection_panel.go_to_tile_requested.connect(self._on_go_to_tile)

        # ✅ Re-emite seleção de stack (SelectionPanel → SideBar → Controller)
        # Isso remove dependência de "stacks_panel" no Controller.
        if hasattr(self.selection_panel, "stack_selected"):
            self.selection_panel.stack_selected.connect(self.stack_selected.emit)

    def set_tile_stacks(self, tile_coords, stacks, active_stack_uid: str | None, controlled_civ_id: int):
        """
        Complementa a UI atual (SelectionPanel / ProvinceDetail) com a lista de stacks do tile.
        Não cria uma tela nova.
        """
        self._tile_stacks_tile = tile_coords
        self._tile_stacks_uids = [s.uid for s in stacks]
        self._active_stack_uid = active_stack_uid

        # 1) Atualiza o SelectionPanel (onde você quer que apareça a lista)
        if hasattr(self.selection_panel, "set_tile_stacks"):
            self.selection_panel.set_tile_stacks(
                tile_coords=tile_coords,
                stacks=stacks,
                active_stack_uid=active_stack_uid,
                controlled_civ_id=controlled_civ_id,
            )

        # 2) Opcional: também atualizar a aba Units do ProvinceDetail se você quiser
        # (só se esse painel tiver um método semelhante)
        if hasattr(self.province_detail, "set_tile_stacks"):
            self.province_detail.set_tile_stacks(
                tile_coords=tile_coords,
                stacks=stacks,
                active_stack_uid=active_stack_uid,
                controlled_civ_id=controlled_civ_id,
            )

    def set_active_stack_uid(self, active_stack_uid: str | None):
        """Só muda checked/highlight, sem reconstruir lista."""
        self._active_stack_uid = active_stack_uid

        if hasattr(self.selection_panel, "set_active_stack_uid"):
            self.selection_panel.set_active_stack_uid(active_stack_uid)

        if hasattr(self.province_detail, "set_active_stack_uid"):
            self.province_detail.set_active_stack_uid(active_stack_uid)

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
        current = self.stacked_widget.currentIndex()
        if current == 3:
            return
        self._pre_selection_page = current
        if current == 2:
            self._pre_selection_tab = self.province_detail.tab_widget.currentIndex()
        else:
            self._pre_selection_tab = None

    def _restore_screen_snapshot(self) -> None:
        if self._pre_selection_page is not None:
            self.stacked_widget.setCurrentIndex(self._pre_selection_page)
            if self._pre_selection_page == 2 and self._pre_selection_tab is not None:
                self.province_detail.tab_widget.setCurrentIndex(self._pre_selection_tab)
        else:
            self.stacked_widget.setCurrentIndex(1)
        self._pre_selection_page = None
        self._pre_selection_tab = None

    # ================================================================
    # NAVEGAÇÃO
    # ================================================================

    def on_planet_loaded(self, success: bool):
        if success and self.controller.game:
            # ✅ MUDANÇA: usa controlled_civ em vez de player_civ
            civ = self.controller.controlled_civ
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
        self._save_screen_snapshot()
        self.selection_panel.update_from_selection(self.controller)
        self.stacked_widget.setCurrentIndex(3)

    def update_selection_panel(self):
        if self.stacked_widget.currentIndex() == 3:
            self.selection_panel.update_from_selection(self.controller)

    def update_units_views(self) -> None:
        """
        Atualiza qualquer UI que dependa da seleção/comando da stack.
        Serve para o caso em que a stack está sendo exibida:
          - no SelectionPanel (page 3)
          - embutida na aba Units da província (page 2)
        """
        # Se o painel de seleção estiver aberto
        if self.stacked_widget.currentIndex() == 3:
            self.selection_panel.update_from_selection(self.controller)

        # Se o painel de província estiver aberto
        if self.stacked_widget.currentIndex() == 2:
            # Aba Units (tab_units) existe no seu ProvinceDetailPanel
            try:
                self.province_detail.tab_units.update_display()
            except Exception:
                # fallback defensivo (não derruba UI se algo mudar)
                if hasattr(self.province_detail, "tab_units") and hasattr(self.province_detail.tab_units, "update_display"):
                    self.province_detail.tab_units.update_display()

    def hide_selection_panel(self):
        if self.stacked_widget.currentIndex() == 3:
            self._restore_screen_snapshot()

    def _on_back_from_selection(self):
        self.controller.selection.clear()
        self.controller._clear_route_overlay()
        if self.controller.scene:
            self.controller.scene.update()
        self._restore_screen_snapshot()

    def _on_cancel_command(self):
        ctrl = self.controller
        if ctrl.game and ctrl.selection.has_selection:
            ctrl.game.command_manager.cancel_command(ctrl.selection.selected_stack_uid)
            ctrl._clear_route_overlay()
            ctrl.selection.preview_path = None
            print("🚫 Comando cancelado via painel.")
        self.update_units_views()
        if ctrl.scene:
            ctrl.scene.update()

    def _on_go_to_tile(self, tile_coords):
        planet = self.controller.game
        camera = self.controller.camera
        if not planet or not camera:
            return
        center_3d = planet.centers_map.get(tile_coords)
        if center_3d:
            camera.look_at_tile(center_3d)
            if self.controller.scene:
                self.controller.scene.update()
