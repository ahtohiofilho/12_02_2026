# ui/sidebar.py

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget

from .civ_manager import CivilizationManagerWidget
from .province.detail_panel import ProvinceDetailPanel
from .selection_panel import SelectionPanel


class SideBar(QWidget):
    """
    Sidebar com navegação em pilha (page stack):

    - QStackedWidget continua sendo a base.
    - Ao abrir Unit Command (SelectionPanel), a SideBar "empilha" a página atual
      (e aba, se for ProvinceDetail).
    - Ao fechar Unit Command (Back / hide_selection_panel), a SideBar "desempilha"
      e volta para a tela de baixo (ex.: ProvinceDetail), preservando a aba.

    Isso implementa o comportamento "Unit Command por cima" sem overlay flutuante.
    """

    stack_selected = Signal(str)

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller

        # Pilha de navegação: (page_index, tab_index_or_None)
        self._nav_stack: list[tuple[int, int | None]] = []

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

        # Índice 3: Painel de seleção/comando (Unit Command)
        self.selection_panel = SelectionPanel(self.controller)
        self.stacked_widget.addWidget(self.selection_panel)

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

        # Re-emite seleção de stack (SelectionPanel → SideBar → Controller)
        if hasattr(self.selection_panel, "stack_selected"):
            self.selection_panel.stack_selected.connect(self.stack_selected.emit)

    # ================================================================
    # Tile stacks plumbing
    # ================================================================

    def set_tile_stacks(self, tile_coords, stacks, active_stack_uid: str | None, controlled_civ_id: int):
        """
        Complementa a UI atual (SelectionPanel / ProvinceDetail) com a lista de stacks do tile.
        Não cria uma tela nova.
        """
        self._tile_stacks_tile = tile_coords
        self._tile_stacks_uids = [s.uid for s in stacks]
        self._active_stack_uid = active_stack_uid

        # 1) Atualiza o SelectionPanel (onde aparece a lista)
        if hasattr(self.selection_panel, "set_tile_stacks"):
            self.selection_panel.set_tile_stacks(
                tile_coords=tile_coords,
                stacks=stacks,
                active_stack_uid=active_stack_uid,
                controlled_civ_id=controlled_civ_id,
            )

        # 2) Opcional: também atualizar a aba Units do ProvinceDetail (se suportar)
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

    # ================================================================
    # Menu widget
    # ================================================================

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
    # Navegação base
    # ================================================================

    def on_planet_loaded(self, success: bool):
        if success and self.controller.game:
            civ = self.controller.controlled_civ  # controlled_civ (debug-aware)
            planet = self.controller.game
            self.civ_manager_view.set_data(civ, planet)
            self.stacked_widget.setCurrentIndex(1)
            self._nav_stack.clear()
        else:
            self.stacked_widget.setCurrentIndex(0)
            self._nav_stack.clear()

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
    # Page stack (push/pop)
    # ================================================================

    def _push_current_page(self) -> None:
        """Guarda a página atual (e tab, se ProvinceDetail)."""
        idx = self.stacked_widget.currentIndex()
        tab = None
        if idx == 2 and hasattr(self.province_detail, "tab_widget"):
            tab = self.province_detail.tab_widget.currentIndex()
        self._nav_stack.append((idx, tab))

    def _pop_page(self) -> None:
        """Volta para a página anterior guardada."""
        if self._nav_stack:
            idx, tab = self._nav_stack.pop()
            self.stacked_widget.setCurrentIndex(idx)
            if idx == 2 and tab is not None and hasattr(self.province_detail, "tab_widget"):
                self.province_detail.tab_widget.setCurrentIndex(tab)
        else:
            self.stacked_widget.setCurrentIndex(1)  # fallback: civ manager

    # ================================================================
    # Selection panel (Unit Command) — "por cima" via pilha
    # ================================================================

    def show_selection_panel(self):
        """
        Abre o Unit Command "por cima" da tela atual:
        empilha página atual e vai para index 3.
        """
        if self.stacked_widget.currentIndex() == 3:
            self.selection_panel.update_from_selection(self.controller)
            return

        self._push_current_page()
        self.selection_panel.update_from_selection(self.controller)
        self.stacked_widget.setCurrentIndex(3)

    def update_selection_panel(self):
        if self.stacked_widget.currentIndex() == 3:
            self.selection_panel.update_from_selection(self.controller)

    def hide_selection_panel(self):
        """Fecha Unit Command e revela a tela de baixo (pop)."""
        if self.stacked_widget.currentIndex() == 3:
            self._pop_page()

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
            try:
                self.province_detail.tab_units.update_display()
            except Exception:
                if (
                    hasattr(self.province_detail, "tab_units")
                    and hasattr(self.province_detail.tab_units, "update_display")
                ):
                    self.province_detail.tab_units.update_display()

    # ================================================================
    # Selection panel callbacks
    # ================================================================

    def _on_back_from_selection(self):
        self.controller.selection.clear()
        self.controller._clear_route_overlay()
        if self.controller.scene:
            self.controller.scene.update()

        # ✅ volta para a página anterior (província, civ manager, etc.)
        self.hide_selection_panel()

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
