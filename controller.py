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

        # Estado visual inicial
        self._clear_route_overlay()
        self._on_go_to_capital()

    # ----------------------------
    # Rotas (overlay) — API do Controller
    # ----------------------------
    def _set_route_overlay(self, path_tiles):
        """
        path_tiles: list[(x,y)] | None
        Controller repassa para a Scene (que repassa pro PlanetRenderer).
        """
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
        """Restaura overlay do comando pendente ou limpa."""
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
        """Move a câmera para focar na capital da civilização do jogador."""
        print("Controller: Recebido pedido para ir para a capital.")

        if not self.game:
            print("⚠️ Controller: Jogo não carregado.")
            return
        if not self.camera:
            print("⚠️ Controller: Câmera não disponível.")
            return

        player_civ = self.game.player_civ
        if not player_civ:
            print("⚠️ Controller: Civilização do jogador não encontrada.")
            return

        capital_coords = player_civ.capital_coords
        if not capital_coords:
            print(f"⚠️ Controller: Civilização '{player_civ.name}' não possui capital.")
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

        # 1) Flush comandos → TurnEngine (agora submete apenas 1 step)
        cmd_count = self.game.command_manager.flush_to_engine()
        print(f"📋 {cmd_count} ordem(ns) submetida(s) ao TurnEngine.")

        # 2) Produção e economia
        print("\n🏭 Processando produção e economia...")
        production_reports = self.game.process_production()
        if production_reports:
            for r in production_reports:
                print(f"   -> Produzido: {r.get('produced')}")

        self.game.economy.invalidar_cache()

        # 3) Resolver turno (movimentos + combates de 1 step)
        print("\n⚔️ Resolvendo movimentos e combates...")
        turn_report = self.game.turn_engine.resolve_turn()

        print(f"\n⏩ Turno {turn_report.turn_number} resolvido!")
        print(f"   Ordens processadas: {turn_report.total_orders}")
        print(f"   Batalhas: {turn_report.total_battles}")

        # 4) Avançar comandos persistentes (atualiza remaining_path)
        self.game.command_manager.advance_persistent_commands()

        # 5) Atualizar overlay da seleção atual (se houver comando em andamento)
        if self.selection.has_selection:
            cmd = self.game.command_manager.get_command(
                self.selection.selected_stack_uid
            )
            if cmd and cmd.remaining_path:
                self._set_route_overlay(cmd.remaining_path)
            else:
                self._clear_route_overlay()
                # Comando terminou — limpar seleção
                self.selection.clear()
        else:
            self._clear_route_overlay()

        # 6) Limpar estado de hover
        if self.input_manager:
            self.input_manager.clear_hover_state()

        # 7) Atualizar UI
        self._update_ui_post_turn()

        # 8) Fechar painel de seleção se não há mais comando ativo
        if not self.selection.has_selection:
            if self.window and hasattr(self.window.sidebar, "hide_selection_panel"):
                self.window.sidebar.hide_selection_panel()

        # 9) Re-render 3D
        if self.scene:
            if hasattr(self.scene, "update_units_data"):
                self.scene.update_units_data(self.game)
            else:
                self.scene.update()

    def _update_ui_post_turn(self):
        """Atualização de UI pós-turno."""
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
        """Chamado pela UI ao detectar hover em rota comercial."""
        if self.scene:
            self.scene.set_route_path(path_tiles)

    def clear_hover_trade_route(self) -> None:
        """Chamado pela UI ao sair do hover."""
        self.set_hover_trade_route(None)

    # ----------------------------
    # Seleção de Stack
    # ----------------------------
    def on_tile_left_clicked(self, tile_coords):
        """
        Clique esquerdo em um tile:
          - Se tem stack própria → seleciona e abre painel
          - Se não → deseleciona e fecha painel
        """
        if not self.game:
            return

        player_civ = self.game.player_civ
        if not player_civ:
            return

        stacks = self.game.stacks.stacks_in_tile(tile_coords)
        player_stack = None
        for s in stacks:
            if s.owner_id == player_civ.id and not s.is_empty():
                player_stack = s
                break

        if player_stack:
            self.selection.select_stack(player_stack.uid, tile_coords)
            units_str = ", ".join(u.unit_key for u in player_stack.units)
            print(f"✅ Stack selecionada em {tile_coords}: [{units_str}]")

            # Mostrar path do comando pendente (se houver)
            cmd = self.game.command_manager.get_command(player_stack.uid)
            if cmd and cmd.path:
                self._set_route_overlay(cmd.path)
            else:
                self._clear_route_overlay()

            # Abrir painel de seleção na sidebar
            if self.window and hasattr(self.window.sidebar, "show_selection_panel"):
                self.window.sidebar.show_selection_panel()

        else:
            self.selection.clear()
            self._clear_route_overlay()
            print(f"ℹ️ Nenhuma stack própria em {tile_coords}. Seleção limpa.")

            # Limpar estado de hover
            if self.input_manager:
                self.input_manager.clear_hover_state()

            # Fechar painel de seleção
            if self.window and hasattr(self.window.sidebar, "hide_selection_panel"):
                self.window.sidebar.hide_selection_panel()

        if self.scene:
            self.scene.update()

    # ----------------------------
    # Comando de Movimento
    # ----------------------------
    def on_tile_right_clicked(self, tile_coords):
        """
        Clique direito em um tile:
          - Se tem stack selecionada → emite comando de movimento
          - Se não → abre painel de província
        """
        if not self.game:
            return

        if not self.selection.has_selection:
            self._on_tile_info(tile_coords)
            return

        player_civ = self.game.player_civ
        if not player_civ:
            return

        ok, msg, cmd = self.game.command_manager.issue_move_command(
            stack_uid=self.selection.selected_stack_uid,
            destination=tile_coords,
            owner_civ_id=player_civ.id,
        )

        if ok and cmd and cmd.path:
            print(f"✅ Comando aceito: {msg}")
            self._set_route_overlay(cmd.path)
            self.selection.preview_path = cmd.path

            # Resetar hover para que o overlay do comando prevaleça
            if self.input_manager:
                self.input_manager._last_hover_tile = None

        else:
            print(f"❌ Comando rejeitado: {msg}")
            self._clear_route_overlay()

        # Atualizar painel de seleção (mostra comando pendente)
        if self.window and hasattr(self.window.sidebar, "update_selection_panel"):
            self.window.sidebar.update_selection_panel()

        if self.scene:
            self.scene.update()

    # ----------------------------
    # Hover — Preview de rota
    # ----------------------------
    def on_tile_hovered(self, tile_coords):
        """
        Mouse sobre um tile com stack selecionada.
        Calcula preview do caminho em tempo real com custos variáveis.
        """
        if not self.game or not self.selection.has_selection:
            return

        stack = self.game.stacks.get_stack(self.selection.selected_stack_uid)
        if not stack or stack.is_empty():
            return

        # Hover no tile da própria stack → restaura overlay do comando real
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

        # 1) Tenta com budget (alcançável neste turno)
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
            # 2) Sem limite de budget (rota possível mas fora de alcance)
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
        """Abre painel de província ao clicar direito sem seleção."""
        if not self.game:
            return

        province = self.game.get_province(tile_coords)
        if province and self.window:
            self.window.sidebar._on_province_selected(province)

    def on_deselect(self):
        """ESC pressionado — limpa seleção, overlay e hover."""
        self.selection.clear()
        self._clear_route_overlay()

        if self.input_manager:
            self.input_manager.clear_hover_state()

        if self.window and hasattr(self.window.sidebar, "hide_selection_panel"):
            self.window.sidebar.hide_selection_panel()

        print("ℹ️ Seleção limpa (ESC).")

        if self.scene:
            self.scene.update()