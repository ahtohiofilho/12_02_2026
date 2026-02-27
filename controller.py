# controller.py
from __future__ import annotations

from typing import Optional, Sequence, Tuple
from ui.window import MainWindow
from core.planet import Planet
from input.input_manager import InputManager
from core.selection.state import SelectionState

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from config.unit_stats import get_unit_stats
from core.diplomacy import Relation
from core.commands.pathfinding import allowed_biomes_for_stack

Tile = Tuple[int, int]


class Controller:
    """
    Controller orquestra UI <-> Game (Planet) e repassa comandos para a Scene.
    """

    def __init__(self, app):
        self.app = app
        self.window: MainWindow | None = None
        self.game: Planet | None = None
        self.input_manager: InputManager | None = None
        self.selection = SelectionState()

        # ── Debug flags ──
        # debug_mode: habilita ferramentas de debug (ex.: trocar civ com Tab)
        self.debug_mode: bool = True

        # debug_fow_reveal_all: se True, ignora FoW e revela o mapa inteiro
        # (separei do debug_mode para você poder depurar sem necessariamente revelar tudo)
        self.debug_fow_reveal_all: bool = False

        # ── Debug: Civilização controlada (apenas se debug_mode=True) ──
        self._controlled_civ_index: int = 0

    # ----------------------------
    # Debug: Civilização controlada
    # ----------------------------
    @property
    def controlled_civ(self):
        if not self.game:
            return None
        if self.debug_mode:
            civs = self.game.civilizations
            if civs and 0 <= self._controlled_civ_index < len(civs):
                return civs[self._controlled_civ_index]
        return self.game.player_civ

    @property
    def controlled_civ_id(self) -> int:
        civ = self.controlled_civ
        return civ.id if civ else 0

    def cycle_controlled_civ(self, direction: int = 1):
        if not self.game or not self.debug_mode:
            return

        civs = self.game.civilizations
        if not civs:
            return

        self._controlled_civ_index = (self._controlled_civ_index + direction) % len(civs)
        civ = civs[self._controlled_civ_index]

        self.selection.clear()
        self._clear_route_overlay()

        print(f"🔄 [DEBUG] Controlando: {civ.name} (id={civ.id}, index={self._controlled_civ_index})")

        if self.window and hasattr(self.window.sidebar, "civ_manager_view"):
            self.window.sidebar.civ_manager_view.set_data(civ, self.game)

        if self.window and hasattr(self.window.sidebar, "hide_selection_panel"):
            self.window.sidebar.hide_selection_panel()

        # Atualiza a visão/Fog of War para a nova civilização
        self.update_fow()

        if self.scene:
            self.scene.update()

    def run(self):
        self.window = MainWindow(controller=self)
        self.input_manager = InputManager(self)
        self.input_manager.install_global_filter(self.app)
        self.connect_signals()
        self.window.show()

    def connect_signals(self):
        self.window.sidebar.btn_exit.clicked.connect(self.app.quit)
        self.window.sidebar.btn_create.clicked.connect(self.action_create_planet)

        if self.window and hasattr(self.window.sidebar, "civ_manager_view"):
            self.window.sidebar.civ_manager_view.go_to_capital_requested.connect(self._on_go_to_capital)

    @property
    def camera(self):
        if self.window and self.window.scene:
            return self.window.scene.camera
        return None

    @property
    def scene(self):
        return self.window.scene if (self.window and self.window.scene) else None

    # ----------------------------
    # Fog of War (NOVO)
    # ----------------------------
    def update_fow(self) -> None:
        """Aplica (na UI) o estado de Fog of War já calculado para a civ controlada."""
        if not self.game or not self.scene:
            return

        vis = getattr(self.game, "visibility", None)
        if vis is None:
            return

        set_fow = getattr(self.scene, "set_fow", None)
        if set_fow is None:
            # crítico: UI sem fachada -> FoW não pode ser aplicado
            print("⚠️ [CTRL] scene.set_fow() ausente; FoW não será aplicado.")
            return

        graph = getattr(self.game, "graph", None)
        if graph is None:
            # crítico: jogo sem grafo (estado corrompido)
            print("⚠️ [CTRL] game.graph ausente; FoW não será aplicado.")
            return

        all_tiles = set(graph.nodes)

        if getattr(self, "debug_fow_reveal_all", False):
            explored = all_tiles
            visible = all_tiles
        else:
            civ_id = int(self.controlled_civ_id)
            state = vis.get_state(civ_id)
            explored = state.explored
            visible = state.visible

        set_fow(explored, visible)

    # ----------------------------
    # Ciclo de vida do jogo
    # ----------------------------
    # controller.py (trecho do método action_create_planet)

    def action_create_planet(self) -> None:
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

        # Estado inicial do controller
        self._controlled_civ_index = 0
        if self.debug_mode:
            civ = self.controlled_civ
            if civ:
                print(f"🔧 [DEBUG MODE ATIVO] Controlando: {civ.name} (id={civ.id})")
                print("   Tab = próxima civ | Shift+Tab = civ anterior")

        self._clear_route_overlay()
        self._on_go_to_capital()

        # (1) Recalcula a visão inicial (regras estão centralizadas no VisibilityManager)
        vis = getattr(self.game, "visibility", None)
        if vis is None:
            print("⚠️ Controller: game.visibility is None (skip initial FoW compute)")
        else:
            vis.update_all_civs()  # <- sem vision_range aqui

        # (2) Aplica na UI (SceneWidget.set_fow faz o trabalho)
        self.update_fow()

        # (3) ✅ Inicializa bloqueio militar e mercado realista (para UI nascer coerente)
        try:
            self.game.update_military_block_state()
        except Exception as e:
            print(f"⚠️ Falha ao inicializar bloqueio militar: {e}")

        try:
            self.game.economy.invalidar_cache()
            self.game.economy.calcular_equilibrio(forcar_recalculo=True)
        except Exception as e:
            print(f"⚠️ Falha ao calcular mercado inicial: {e}")

        if self.scene:
            self.scene.update()

    # ----------------------------
    # Rotas (overlay)
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
    def _on_turn_advanced(self) -> None:
        if not self.game:
            print("⚠️ Nenhum planeta ativo.")
            return

        # 0) Envia ordens acumuladas para o TurnEngine
        cmd_count = self.game.command_manager.flush_to_engine()
        print(f"📋 {cmd_count} ordem(ns) submetida(s) ao TurnEngine.")

        # 1) Produção/economia do turno (fila + renda do turno anterior)
        #    (no seu Planet.process_production já chama economy.calcular_equilibrio(forcar_recalculo=True)
        #     para aplicar renda do turno anterior)
        print("\n🏭 Processando produção e economia...")
        production_reports = self.game.process_production()
        if production_reports:
            for r in production_reports:
                print(f"   -> Produzido: {r.get('produced')}")

        # 2) Resolve movimentos/combates (isso pode mudar quais tiles estão ocupados por militar)
        print("\n⚔️ Resolvendo movimentos e combates...")
        turn_report = self.game.turn_engine.resolve_turn()

        print(f"\n⏩ Turno {turn_report.turn_number} resolvido!")
        print(f"   Ordens processadas: {turn_report.total_orders}")
        print(f"   Batalhas: {turn_report.total_battles}")

        # 3) Avança comandos persistentes (UI/estado interno)
        self.game.command_manager.advance_persistent_commands()

        # 4) ✅ Atualiza bloqueio militar (precisa ser DEPOIS de movimentos/combates)
        try:
            self.game.update_military_block_state()
        except Exception as e:
            print(f"⚠️ Falha ao atualizar bloqueio militar: {e}")

        # 5) Overlay de rota / seleção (com base no estado pós-turno)
        if self.selection.has_selection:
            cmd = self.game.command_manager.get_command(self.selection.selected_stack_uid)
            if cmd and cmd.remaining_path:
                self._set_route_overlay(cmd.remaining_path)
            else:
                self._clear_route_overlay()
                self.selection.clear()
        else:
            self._clear_route_overlay()

        if self.input_manager:
            self.input_manager.clear_hover_state()

        # 6) Recalcula FoW (explored/visible) e aplica na UI
        vis = getattr(self.game, "visibility", None)
        if vis is None:
            print("⚠️ game.visibility is None (skip FoW recompute)")
        else:
            vis.update_all_civs()

        self.update_fow()

        # 7) ✅ Recalcula mercado global realista (para a UI refletir rotas/preços do novo estado)
        #    - depende de explored (visibilidade)
        #    - depende de bloqueio militar (trade_blocked_tiles_by_civ)
        try:
            self.game.economy.invalidar_cache()
            self.game.economy.calcular_equilibrio(forcar_recalculo=True)
        except Exception as e:
            print(f"⚠️ Falha ao recalcular mercado pós-turno: {e}")

        # 8) Atualizações de UI (painéis) e cena
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
    # Ações de Worker
    # ----------------------------
    def action_detach_worker(self, province) -> bool:
        """
        Agenda o destacamento de 1 worker fixo para o próximo turno.
        (antes executava imediatamente; agora enfileira)
        """
        if not self.game:
            return False

        from core.workforce.facade import ProvinceWorkforceFacade

        facade = ProvinceWorkforceFacade(planet=self.game, province=province)
        ok = facade.enqueue_detach_worker()  # ← mudança: era detach_worker()

        if ok:
            # Apenas atualiza a UI da fila — sem FoW/unidades ainda
            if self.window and hasattr(self.window.sidebar, "province_detail"):
                sb = self.window.sidebar
                try:
                    if hasattr(sb.province_detail, "update_display"):
                        sb.province_detail.update_display()
                except Exception:
                    pass

        return ok

    def action_reattach_worker(self, unit_uid: str, target_province) -> bool:
        """
        Reintegra um worker móvel em qualquer província.
        Chamado quando o jogador seleciona um worker e clica em 'Reintegrar'.
        """
        if not self.game:
            return False

        from core.workforce.facade import ProvinceWorkforceFacade

        ok = ProvinceWorkforceFacade.reattach_worker(
            unit_uid=unit_uid,
            target_province=target_province,
            planet=self.game,
        )

        if ok:
            # Worker sumiu do mapa → limpa seleção se era ele
            if self.selection.has_selection:
                stack = self.game.stacks.get_stack(self.selection.selected_stack_uid)
                if stack is None or stack.is_empty():
                    self.selection.clear()
                    self._clear_route_overlay()
                    if self.window and hasattr(self.window.sidebar, "hide_selection_panel"):
                        self.window.sidebar.hide_selection_panel()

            self.game.visibility.update_all_civs()
            self.update_fow()

            if self.scene:
                if hasattr(self.scene, "update_units_data"):
                    self.scene.update_units_data(self.game)
                else:
                    self.scene.update()

        return ok

    def action_found_province(self, unit_uid: str) -> bool:
        """
        Funda uma nova província no tile onde o worker móvel está.
        Chamado quando o jogador seleciona um worker e clica em 'Fundar Província'.
        """
        if not self.game:
            return False

        from core.workforce.facade import ProvinceWorkforceFacade

        ok = ProvinceWorkforceFacade.found_province(
            unit_uid=unit_uid,
            planet=self.game,
        )

        if ok:
            # Worker sumiu do mapa → limpa seleção
            self.selection.clear()
            self._clear_route_overlay()

            if self.window and hasattr(self.window.sidebar, "hide_selection_panel"):
                self.window.sidebar.hide_selection_panel()

            self.game.visibility.update_all_civs()
            self.update_fow()

            # Atualiza painel de província se estiver aberto
            self._update_ui_post_turn()

            if self.scene:
                if hasattr(self.scene, "update_units_data"):
                    self.scene.update_units_data(self.game)
                else:
                    self.scene.update()

        return ok

    # ----------------------------
    # Seleção de Stack
    # ----------------------------
    def on_tile_left_clicked(self, tile_coords):
        if not self.game:
            return

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

            province = self.game.get_province(tile_coords)
            if province and self.window:
                self.window.sidebar._on_province_selected(province)
            else:
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

            province = self.game.get_province(tile_coords)
            if province and self.window:
                self.window.sidebar._on_province_selected(province)

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

        civ = self.controlled_civ
        if not civ:
            return

        ok, msg, cmd = self.game.command_manager.issue_move_command(
            stack_uid=self.selection.selected_stack_uid,
            destination=tile_coords,
            owner_civ_id=civ.id,
            planet=self.game,
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

        if self.window and hasattr(self.window.sidebar, "update_units_views"):
            self.window.sidebar.update_units_views()
        elif self.window and hasattr(self.window.sidebar, "update_selection_panel"):
            self.window.sidebar.update_selection_panel()

        if self.scene:
            self.scene.update()

    def update_cursor_for_tile(self, tile_coords):
        """Avalia as regras e altera o cursor do mouse de acordo com a tradição 4X."""
        if not self.scene:
            return

        default_cursor = Qt.ArrowCursor

        if not self.game or not self.selection.has_selection or not tile_coords:
            self.scene.setCursor(default_cursor)
            return

        stack = self.game.stacks.get_stack(self.selection.selected_stack_uid)
        if not stack or stack.is_empty():
            self.scene.setCursor(default_cursor)
            return

        is_military = any(not get_unit_stats(u.unit_key).is_non_combat for u in stack.units)

        # ── 1. Verificação de Diplomacia e Cidades (Portos) ──
        owner_id = stack.owner_id
        target_civ_ids = set()
        is_friendly_city = False

        province = self.game.get_province(tile_coords)
        if province and province.owner:
            target_civ_ids.add(province.owner.id)
            # Permite navios em províncias aliadas/próprias (cidades funcionam como porto)
            if province.owner.id == owner_id or self.game.diplomacy.relation(owner_id,
                                                                             province.owner.id) == Relation.ALLY:
                is_friendly_city = True

        for s in self.game.stacks.stacks_in_tile(tile_coords):
            if not s.is_empty():
                target_civ_ids.add(s.owner_id)

        target_civ_ids.discard(owner_id)

        # ── 2. Verificação de Terreno Intransponível (Bioma) ──
        allowed_biomes = allowed_biomes_for_stack(self.game.graph, stack, self.game.stacks)
        biome = self.game.graph.nodes.get(tile_coords, {}).get("bioma", "")

        # Exceção: Navios podem entrar em biomas proibidos SE for uma cidade amigável!
        if not is_friendly_city and biome not in allowed_biomes:
            self.scene.setCursor(Qt.ForbiddenCursor)
            return

        # ── 3. Definição do Cursor Final ──
        if not target_civ_ids:
            self.scene.setCursor(Qt.PointingHandCursor)  # Movimento
            return

        has_enemy = False
        has_neutral = False

        for cid in target_civ_ids:
            rel = self.game.diplomacy.relation(owner_id, cid)
            if rel == Relation.ENEMY:
                has_enemy = True
            elif rel == Relation.NEUTRAL:
                has_neutral = True

        if has_enemy and is_military:
            self.scene.setCursor(Qt.CrossCursor)  # Combate (Mira)
        elif has_neutral:
            self.scene.setCursor(Qt.ForbiddenCursor)  # Bloqueado (Proibido entrar em neutro)
        else:
            self.scene.setCursor(Qt.PointingHandCursor)  # Movimento/Atracar

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
            planet=self.game,
            owner_id=stack.owner_id,
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
                planet=self.game,
                owner_id=stack.owner_id,
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

        if self.scene:
            self.scene.setCursor(Qt.ArrowCursor)

        if self.input_manager:
            self.input_manager.clear_hover_state()

        if self.window and hasattr(self.window.sidebar, "hide_selection_panel"):
            self.window.sidebar.hide_selection_panel()

        print("ℹ️ Seleção limpa (ESC).")

        if self.scene:
            self.scene.update()
