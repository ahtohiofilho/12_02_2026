# controller.py
from __future__ import annotations

from typing import Optional, Sequence, Tuple
from ui.window import MainWindow
from core.planet import Planet
from input.input_manager import InputManager
from core.selection.state import SelectionState

Tile = Tuple[int, int]


class Controller:
    """
    Controller orquestra UI <-> Game (Planet) e repassa comandos para a Scene.
    Controller NÃO fala diretamente com OpenGL/renderers; fala com self.window.scene.
    """

    def __init__(self, app):
        self.app = app
        self.window = None
        self.game: Planet | None = None
        self.input_manager: InputManager | None = None
        self.selection = SelectionState()

        # ── Debug Mode ──
        self.debug_mode: bool = True  # Mude para False para desabilitar
        self._controlled_civ_index: int = 0  # índice na lista de civs

    # ----------------------------
    # Debug: Civilização controlada
    # ----------------------------
    @property
    def controlled_civ(self):
        """Retorna a civilização atualmente controlada."""
        if not self.game:
            return None
        if self.debug_mode:
            civs = self.game.civilizations
            if civs and 0 <= self._controlled_civ_index < len(civs):
                return civs[self._controlled_civ_index]
        return self.game.player_civ

    @property
    def controlled_civ_id(self) -> int:
        """ID da civ controlada."""
        civ = self.controlled_civ
        return civ.id if civ else 0

    def cycle_controlled_civ(self, direction: int = 1):
        """
        Cicla a civilização controlada.
        direction: +1 = próxima, -1 = anterior
        """
        if not self.game or not self.debug_mode:
            return

        civs = self.game.civilizations
        if not civs:
            return

        self._controlled_civ_index = (self._controlled_civ_index + direction) % len(civs)
        civ = civs[self._controlled_civ_index]

        # Limpar seleção ao trocar de civ
        self.selection.clear()
        self._clear_route_overlay()

        print(f"🔄 [DEBUG] Controlando: {civ.name} (id={civ.id}, index={self._controlled_civ_index})")

        # ✅ Atualizar sidebar com a nova civ
        if self.window and hasattr(self.window.sidebar, "civ_manager_view"):
            self.window.sidebar.civ_manager_view.set_data(civ, self.game)

        # Fechar painel de seleção
        if self.window and hasattr(self.window.sidebar, "hide_selection_panel"):
            self.window.sidebar.hide_selection_panel()

        if self.scene:
            self.scene.update()

    def run(self):
        self.window = MainWindow(controller=self)
        self.input_manager = InputManager(self)
        self.input_manager.install_global_filter(self.app)
        self.connect_signals()
        self.window.show()

    def connect_signals(self):
        # Sidebar (menu)
        self.window.sidebar.btn_exit.clicked.connect(self.app.quit)
        self.window.sidebar.btn_create.clicked.connect(self.action_create_planet)

        # Sidebar -> Controller
        if self.window and hasattr(self.window.sidebar, "civ_manager_view"):
            self.window.sidebar.civ_manager_view.go_to_capital_requested.connect(self._on_go_to_capital)

    @property
    def camera(self):
        """Acesso à câmera para input/ações."""
        if self.window and self.window.scene:
            return self.window.scene.camera
        return None

    @property
    def scene(self):
        """Fachada para operações de render/UI do mundo."""
        return self.window.scene if (self.window and self.window.scene) else None

    # ----------------------------
    # Ciclo de vida do jogo
    # ----------------------------
    def action_create_planet(self):
        print("Controller: Recebido pedido para criar um novo planeta.")

        self.game = Planet(fator=5)

        if not self.game:
            print("❌ ERRO: A criação do planeta falhou e retornou None.")
            if self.window:
                self.window.sidebar.on_planet_loaded(False)
            return

        print("Controller: Novo objeto Planeta (self.game) está ativo.")
        print(f" -> Nós no grafo: {self.game.graph.number_of_nodes()}")

        print("Controller: Enviando dados do planeta para a UI...")
        if self.scene:
            self.scene.set_planet_data(self.game)

        print("Controller: Notificando a Sidebar para abrir o painel da civilização...")
        if self.window:
            self.window.sidebar.on_planet_loaded(True)

        # Resetar debug index
        self._controlled_civ_index = 0
        if self.debug_mode:
            civ = self.controlled_civ
            if civ:
                print(f"🔧 [DEBUG MODE ATIVO] Controlando: {civ.name} (id={civ.id})")
                print(f"   Tab = próxima civ | Shift+Tab = civ anterior")

        # Estado visual inicial
        self._clear_route_overlay()
        self._on_go_to_capital()

    # ----------------------------
    # Rotas (overlay) — API do Controller
    # ----------------------------
    def _set_route_overlay(self, path_tiles):
        if not self.scene:
            return

        if hasattr(self.scene, "set_route_path"):
            self.scene.set_route_path(path_tiles)
        else:
            if hasattr(self.scene, "planet_renderer"):
                self.scene.planet_renderer.set_route_path(path_tiles)

        self.scene.update()

    def _clear_route_overlay(self):
        self._set_route_overlay(None)

    def _restore_or_clear_overlay(self):
        if self.game and self.selection.has_selection:
            cmd = self.game.command_manager.get_command(
                self.selection.selected_stack_uid
            )
            if cmd and cmd.path:
                self._set_route_overlay(cmd.path)
                return

        self._clear_route_overlay()

    # ----------------------------
    # Ações de UI
    # ----------------------------
    def _on_go_to_capital(self):
        print("Controller: Recebido pedido para ir para a capital.")

        if not self.game:
            print("⚠️ Controller: Jogo não carregado.")
            return
        if not self.camera:
            print("⚠️ Controller: Câmera não disponível.")
            return

        # Usa civ controlada em vez de player_civ
        civ = self.controlled_civ
        if not civ:
            print("⚠️ Controller: Civilização não encontrada.")
            return

        capital_coords = civ.capital_coords
        if not capital_coords:
            print(f"⚠️ Controller: Civilização '{civ.name}' não possui capital.")
            return

        tile_centers_3d = self.game.centers_map
        if capital_coords not in tile_centers_3d:
            print(f"⚠️ Controller: Coordenada 3D para o tile {capital_coords} não encontrada.")
            return

        capital_3d_center = tile_centers_3d[capital_coords]
        print(f"Controller: Movendo câmera para a capital em {capital_coords} (3D: {capital_3d_center})")
        self.camera.look_at_tile(capital_3d_center)

        if self.scene:
            self.scene.update()

    # ----------------------------
    # Turno
    # ----------------------------
    def _on_turn_advanced(self):
        if not self.game:
            print("⚠️ Nenhum planeta ativo.")
            return

        cmd_count = self.game.command_manager.flush_to_engine()
        print(f"📋 {cmd_count} ordem(ns) submetida(s) ao TurnEngine.")

        print("\n🏭 Processando produção e economia...")
        production_reports = self.game.process_production()
        if production_reports:
            for r in production_reports:
                print(f"   -> Produzido: {r.get('produced')}")

        self.game.economy.invalidar_cache()

        print("\n⚔️ Resolvendo movimentos e combates...")
        turn_report = self.game.turn_engine.resolve_turn()

        print(f"\n⏩ Turno {turn_report.turn_number} resolvido!")
        print(f"   Ordens processadas: {turn_report.total_orders}")
        print(f"   Batalhas: {turn_report.total_battles}")

        self.game.command_manager.advance_persistent_commands()

        if self.selection.has_selection:
            cmd = self.game.command_manager.get_command(
                self.selection.selected_stack_uid
            )
            if cmd and cmd.remaining_path:
                self._set_route_overlay(cmd.remaining_path)
            else:
                self._clear_route_overlay()
                self.selection.clear()
        else:
            self._clear_route_overlay()

        if self.input_manager:
            self.input_manager.clear_hover_state()

        self._update_ui_post_turn()

        if not self.selection.has_selection:
            if self.window and hasattr(self.window.sidebar, "hide_selection_panel"):
                self.window.sidebar.hide_selection_panel()

        if self.scene:
            if hasattr(self.scene, "update_units_data"):
                self.scene.update_units_data(self.game)
            else:
                self.scene.update()

    def _update_ui_post_turn(self):
        if self.window and hasattr(self.window.sidebar, "civ_manager_view"):
            self.window.sidebar.civ_manager_view.update_display()

        if self.window and hasattr(self.window.sidebar, "province_detail"):
            sb = self.window.sidebar
            try:
                is_open = hasattr(sb, "stacked_widget") and sb.stacked_widget.currentIndex() == 2
                if is_open:
                    if hasattr(sb.province_detail, "update_display"):
                        sb.province_detail.update_display()
                    else:
                        sb.province_detail._load_province_data()
            except Exception as e:
                print(f"⚠️ Falha ao atualizar painel: {e}")

    def set_hover_trade_route(self, path_tiles: Sequence[Tuple[int, int]]) -> None:
        if self.scene:
            self.scene.set_route_path(path_tiles)

    def clear_hover_trade_route(self) -> None:
        self.set_hover_trade_route(None)

    # ----------------------------
    # Seleção de Stack
    # ----------------------------
    def on_tile_left_clicked(self, tile_coords):
        if not self.game:
            return

        # Usa civ controlada em vez de player_civ
        civ = self.controlled_civ
        if not civ:
            return

        stacks = self.game.stacks.stacks_in_tile(tile_coords)
        own_stack = None
        for s in stacks:
            if s.owner_id == civ.id and not s.is_empty():
                own_stack = s
                break

        if own_stack:
            self.selection.select_stack(own_stack.uid, tile_coords)
            units_str = ", ".join(u.unit_key for u in own_stack.units)
            civ_label = f" [{civ.name}]" if self.debug_mode else ""
            print(f"✅ Stack selecionada em {tile_coords}{civ_label}: [{units_str}]")

            cmd = self.game.command_manager.get_command(own_stack.uid)
            if cmd and cmd.path:
                self._set_route_overlay(cmd.path)
            else:
                self._clear_route_overlay()

            if self.window and hasattr(self.window.sidebar, "show_selection_panel"):
                self.window.sidebar.show_selection_panel()

        else:
            self.selection.clear()
            self._clear_route_overlay()
            print(f"ℹ️ Nenhuma stack própria em {tile_coords}. Seleção limpa.")

            if self.input_manager:
                self.input_manager.clear_hover_state()

            if self.window and hasattr(self.window.sidebar, "hide_selection_panel"):
                self.window.sidebar.hide_selection_panel()

        if self.scene:
            self.scene.update()

    # ----------------------------
    # Comando de Movimento
    # ----------------------------
    def on_tile_right_clicked(self, tile_coords):
        if not self.game:
            return

        if not self.selection.has_selection:
            self._on_tile_info(tile_coords)
            return

        # Usa civ controlada
        civ = self.controlled_civ
        if not civ:
            return

        ok, msg, cmd = self.game.command_manager.issue_move_command(
            stack_uid=self.selection.selected_stack_uid,
            destination=tile_coords,
            owner_civ_id=civ.id,
        )

        if ok and cmd and cmd.path:
            print(f"✅ Comando aceito: {msg}")
            self._set_route_overlay(cmd.path)
            self.selection.preview_path = cmd.path

            if self.input_manager:
                self.input_manager._last_hover_tile = None

        else:
            print(f"❌ Comando rejeitado: {msg}")
            self._clear_route_overlay()

        if self.window and hasattr(self.window.sidebar, "update_selection_panel"):
            self.window.sidebar.update_selection_panel()

        if self.scene:
            self.scene.update()

    # ----------------------------
    # Hover — Preview de rota
    # ----------------------------
    def on_tile_hovered(self, tile_coords):
        if not self.game or not self.selection.has_selection:
            return

        stack = self.game.stacks.get_stack(self.selection.selected_stack_uid)
        if not stack or stack.is_empty():
            return

        if tile_coords == stack.tile:
            self._restore_or_clear_overlay()
            return

        from core.commands.pathfinding import (
            find_path,
            allowed_biomes_for_stack,
            movement_budget_for_stack,
        )

        allowed = allowed_biomes_for_stack(self.game.graph, stack, self.game.stacks)
        budget = movement_budget_for_stack(stack)
        unit_keys = [u.unit_key for u in stack.units]

        path = find_path(
            self.game.graph,
            stack.tile,
            tile_coords,
            movement_points=budget,
            allowed_biomes=allowed,
            unit_keys=unit_keys,
        )

        if path:
            self._set_route_overlay(path)
        else:
            path_unlimited = find_path(
                self.game.graph,
                stack.tile,
                tile_coords,
                movement_points=None,
                allowed_biomes=allowed,
                unit_keys=unit_keys,
            )
            if path_unlimited:
                self._set_route_overlay(path_unlimited)
            else:
                self._restore_or_clear_overlay()

        if self.scene:
            self.scene.update()

    # ----------------------------
    # Info de Província
    # ----------------------------
    def _on_tile_info(self, tile_coords):
        if not self.game:
            return

        province = self.game.get_province(tile_coords)
        if province and self.window:
            self.window.sidebar._on_province_selected(province)

    def on_deselect(self):
        self.selection.clear()
        self._clear_route_overlay()

        if self.input_manager:
            self.input_manager.clear_hover_state()

        if self.window and hasattr(self.window.sidebar, "hide_selection_panel"):
            self.window.sidebar.hide_selection_panel()

        print("ℹ️ Seleção limpa (ESC).")

        if self.scene:
            self.scene.update()
