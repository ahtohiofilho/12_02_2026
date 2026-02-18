# controller.py
from __future__ import annotations

from typing import Optional, Sequence, Tuple
from ui.window import MainWindow
from core.planet import Planet
from input.input_manager import InputManager

Tile = Tuple[int, int]


class Controller:
    """
    Boas práticas (aqui):
      - Controller orquestra UI <-> Game (Planet) e repassa comandos para a Scene.
      - Controller NÃO fala diretamente com OpenGL/renderers; fala com self.window.scene.
      - Rotas: Controller expõe métodos para "setar/limpar" rota na Scene.
    """

    def __init__(self, app):
        self.app = app
        self.window = None
        self.game: Planet | None = None
        self.input_manager: InputManager | None = None

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

        # Se você tiver/for criar sinais de input para tile selecionado/hover:
        # self.input_manager.tile_clicked.connect(self._on_tile_clicked)
        # self.input_manager.tile_hovered.connect(self._on_tile_hovered)

    @property
    def camera(self):
        """Acesso à câmera para input/ações."""
        if self.window and self.window.scene:
            return self.window.scene.camera
        return None

    @property
    def scene(self):
        """Fachada para operações de render/UI do mundo (sem acessar OpenGL direto)."""
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

        # Melhor prática: scene encapsula o PlanetRenderer
        if hasattr(self.scene, "set_route_path"):
            self.scene.set_route_path(path_tiles)
        else:
            # fallback (caso você ainda não tenha implementado scene.set_route_path)
            if hasattr(self.scene, "planet_renderer"):
                self.scene.planet_renderer.set_route_path(path_tiles)

        self.scene.update()

    def _clear_route_overlay(self):
        self._set_route_overlay(None)

    # ----------------------------
    # Ações de UI
    # ----------------------------
    def _on_go_to_capital(self):
        """
        Move a câmera para focar na capital da civilização do jogador.
        """
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
        """Chamado quando o sinal 'turn_advanced' é emitido pela UI."""
        if not self.game:
            print("⚠️ Nenhum planeta ativo. Crie um planeta primeiro.")
            return

        print("\n🏭 Processando produção e economia...")
        production_reports = self.game.process_production()
        if production_reports:
            for report in production_reports:
                print(f"   -> Produzido: {report.get('produced')}")
        else:
            print("   -> Nenhuma produção concluída neste turno.")

        self.game.economy.invalidar_cache()
        print("💰 Economia e produção processadas.")

        print("\n⚔️ Resolvendo movimentos e combates...")
        engine = self.game.turn_engine
        report = engine.resolve_turn()

        print(f"\n⏩ Turno {report.turn_number} resolvido!")
        print(f"   Ordens de movimento processadas: {report.total_orders}")
        print(f"   Batalhas ocorridas: {report.total_battles}")

        print("\nController: Atualizando a UI após o avanço do turno...")
        if self.window and hasattr(self.window.sidebar, "civ_manager_view"):
            self.window.sidebar.civ_manager_view.update_display()

        if self.scene:
            self.scene.update()

    def set_hover_trade_route(self, path_tiles: Sequence[Tuple[int, int]]) -> None:
        """Chamado pela UI ao detectar hover em rota comercial"""
        if self.scene:
            self.scene.set_route_path(path_tiles)

    def clear_hover_trade_route(self) -> None:
        """Chamado pela UI ao sair do hover"""
        self.set_hover_trade_route(None)