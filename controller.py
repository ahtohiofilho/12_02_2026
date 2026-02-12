from ui.main_window import MainWindow
from core.planet import Planet  # <--- IMPORTAMOS A CLASSE Planet


class Controller:
    def __init__(self, app):
        self.app = app
        self.window = None
        self.current_planet = None

    def run(self):
        # self.window = MainWindow() # Antes
        self.window = MainWindow(controller=self)
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