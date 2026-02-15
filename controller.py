# controller.py

from ui.window import MainWindow
from core.planet import Planet
from input.input_manager import InputManager


class Controller:
    def __init__(self, app):
        self.app = app
        self.window = None
        # MODIFICAÇÃO: Renomeado para 'game' para refletir a lógica do jogo.
        self.game = None
        self.input_manager = None

    def run(self):
        self.window = MainWindow(controller=self)
        self.input_manager = InputManager(self)
        self.input_manager.install_global_filter(self.app)
        self.connect_signals()
        self.window.show()

    def connect_signals(self):
        # Conexões da sidebar inicial (menu)
        self.window.sidebar.btn_exit.clicked.connect(self.app.quit)
        self.window.sidebar.btn_create.clicked.connect(self.action_create_planet)

        # === NOVA CONEXÃO ===
        # Conecta o sinal do botão "Go to Capital" da UI ao nosso novo método.
        # O caminho é: window -> sidebar -> civ_manager_view -> sinal
        if self.window and hasattr(self.window.sidebar, 'civ_manager_view'):
            self.window.sidebar.civ_manager_view.go_to_capital_requested.connect(self._on_go_to_capital)

    def action_create_planet(self):
        print("Controller: Recebido pedido para criar um novo planeta.")

        # Usa 'self.game' em vez de 'current_planet'
        self.game = Planet(fator=5)

        if self.game:
            print("Controller: Novo objeto Planeta (self.game) está ativo.")
            print(f" -> Nós no grafo: {self.game.graph.number_of_nodes()}")

            print("Controller: Enviando dados do planeta para a UI...")
            self.window.scene.set_planet_data(self.game)

            print("Controller: Notificando a Sidebar para abrir o painel da civilização...")
            self.window.sidebar.on_planet_loaded(True)
        else:
            print("❌ ERRO: A criação do planeta falhou e retornou None.")
            self.window.sidebar.on_planet_loaded(False)

    @property
    def camera(self):
        """Fornece acesso à câmera para o InputManager e outros métodos."""
        if self.window and self.window.scene:
            return self.window.scene.camera
        return None

    # === NOVO MÉTODO ===
    def _on_go_to_capital(self):
        """
        Move a câmera para focar na capital da civilização do jogador.
        Este método é chamado pelo sinal 'go_to_capital_requested' da UI.
        """
        print("Controller: Recebido pedido para ir para a capital.")

        # 1. Validações de segurança
        if not self.game:
            print("⚠️ Controller: Jogo não carregado.")
            return
        if not self.camera:
            print("⚠️ Controller: Câmera não disponível.")
            return

        # 2. Obter os dados necessários
        player_civ = self.game.player_civ
        if not player_civ:
            print("⚠️ Controller: Civilização do jogador não encontrada.")
            return

        capital_coords = player_civ.capital_coords
        if not capital_coords:
            print(f"⚠️ Controller: Civilização '{player_civ.name}' não possui capital.")
            return

        # 3. Obter a coordenada 3D do centro do tile
        tile_centers_3d = self.game.centers_map
        if capital_coords not in tile_centers_3d:
            print(f"⚠️ Controller: Coordenada 3D para o tile {capital_coords} não encontrada.")
            return

        capital_3d_center = tile_centers_3d[capital_coords]

        # 4. Chamar o método da câmera
        print(f"Controller: Movendo câmera para a capital em {capital_coords} (3D: {capital_3d_center})")
        self.camera.look_at_tile(capital_3d_center)

        # 5. Forçar uma atualização da cena para a mudança ser imediata
        if self.window and self.window.scene:
            self.window.scene.update()

    def _on_turn_advanced(self):
        """Chamado quando o sinal 'turn_advanced' é emitido pela UI."""
        if not self.game:
            print("⚠️ Nenhum planeta ativo. Crie um planeta primeiro.")
            return

        engine = self.game.turn_engine
        report = engine.resolve_turn()

        print(f"⏩ Turno {report.turn_number} resolvido!")
        print(f"   Ordens processadas: {report.total_orders}")
        # ... (resto dos logs)

        print("Controller: Atualizando a UI após o avanço do turno...")
        self.window.sidebar.civ_manager_view.update_display()
