from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout
from ui.sidebar import Sidebar
# Antes era: from ui.scene3d import Scene3D
from ui.scene_widget import SceneWidget # 1. Mude o import

class MainWindow(QMainWindow):
    # Adicione 'controller' ao __init__
    def __init__(self, controller):
        super().__init__()
        self.setWindowTitle("Global Arena")

        # Widget central
        central = QWidget()
        layout = QHBoxLayout(central)

        # Sidebar ocupa 40%
        self.sidebar = Sidebar()
        layout.addWidget(self.sidebar, stretch=4)

        # Cena 3D ocupa 60%
        # Antes era: self.scene = Scene3D()
        self.scene = SceneWidget(controller) # 2. Passe o controller para o construtor

        layout.addWidget(self.scene, stretch=6)

        self.setCentralWidget(central)
        self.showMaximized()
