# controller.py
from ui.window import MainWindow
from core.planet import Planet
from input.input_manager import InputManager


class Controller:
    def __init__(self, app):
        self.app = app
        self.window = None
        self.current_planet = None
        self.input_manager = None  # Será inicializado depois

    def run(self):
        self.window = MainWindow(controller=self)

        # Inicializa InputManager APÓS criar a janela principal
        self.input_manager = InputManager(self)
        self.input_manager.install_global_filter(self.app)

        self.connect_signals()
        self.window.show()

    def connect_signals(self):
        self.window.sidebar.btn_exit.clicked.connect(self.app.quit)
        self.window.sidebar.btn_create.clicked.connect(self.action_create_planet)

    def action_create_planet(self):
        print("Controller: Recebido pedido para criar um novo planeta.")

        # 1. Instancia a classe
        self.current_planet = Planet(n=5)

        # Checagem e logs para garantir que o objeto foi criado corretamente
        if self.current_planet:
            print("Controller: Novo objeto Planeta está ativo.")
            print(f" -> Nós no grafo: {self.current_planet.graph.number_of_nodes()}")
            print(f" -> Total de vértices: {len(self.current_planet.all_vertices)}")

            # 2. A etapa final e crucial: entregar o planeta para a UI.
            print("Controller: Enviando dados do planeta para a UI...")
            self.window.scene.set_planet_data(self.current_planet)
        else:
            print("❌ ERRO: A criação do planeta falhou e retornou None.")

        # ===== ADICIONE AQUI =====
        if self.current_planet:
            print("✅ Controller: Planeta criado com sucesso!")
            print(f"  Número de polígonos: {len(self.current_planet.polygons_map)}")
            print(f"  Vértices únicos: {len(self.current_planet.all_vertices)}")

            # Verifica se centers_map não está vazio antes de acessar
            if self.current_planet.centers_map:
                first_center = next(iter(self.current_planet.centers_map.values()))
                print(f"  Centro do primeiro tile: {first_center}")
            else:
                print("⚠️  AVISO: centers_map está vazio!")
        else:
            print("❌ Controller: Falha na criação do planeta!")
        # ===== FIM DA ADIÇÃO =====

    @property
    def camera(self):
        """Fornece acesso à câmera para o InputManager"""
        if self.window and self.window.scene:
            return self.window.scene.camera
        return None

    def _on_turn_advanced(self):
        """Chamado quando Enter é pressionado — resolve todas as ordens do turno."""
        if not self.current_planet:
            print("⚠️ Nenhum planeta ativo. Crie um planeta primeiro.")
            return

        engine = self.current_planet.turn_engine

        # Fase 1: ordens já foram submetidas via UI ao longo do turno
        # ex.: engine.submit_order(stack_uid="...", dst_tile=(5, 1))

        # Fase 2: resolver tudo de uma vez
        report = engine.resolve_turn()

        # Fase 3: feedback
        print(f"⏩ Turno {report.turn_number} resolvido!")
        print(f"   Ordens processadas: {report.total_orders}")
        print(f"   Batalhas: {report.total_battles}")

        for r in report.results:
            print(f"   [{r.result_type.name}] {r.stack_uid[:8]}... → {r.dst_tile}: {r.reason}")
