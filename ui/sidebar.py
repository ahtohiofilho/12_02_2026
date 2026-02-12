from PySide6.QtWidgets import QFrame, QVBoxLayout, QPushButton, QSizePolicy, QSpacerItem
from PySide6.QtCore import Qt


class Sidebar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFrameStyle(QFrame.NoFrame)
        self.setMinimumWidth(200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignTop)

        # === TOPO: Botões de ação (Criar Planeta, etc.) ===
        self.btn_create = QPushButton("Create Planet")
        self.btn_create.setFixedWidth(140)
        self.btn_create.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(self.btn_create, alignment=Qt.AlignCenter)

        # Espaço flexível que empurra o botão de sair para baixo
        layout.addStretch(1)

        # === FUNDO: Botão de sair (estilo diferente) ===
        self.btn_exit = QPushButton("Exit")
        self.btn_exit.setFixedWidth(100)  # Um pouco menor
        self.btn_exit.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(self.btn_exit, alignment=Qt.AlignCenter)

        self.setStyleSheet("""
            Sidebar {
                background-color: #0b3d0b;
                border-right: 2px solid #1a5c1a;
            }

            /* Botões padrão (topo) */
            QPushButton {
                background-color: #1a5c1a;
                color: #f4e7a1;
                border: 2px solid #2d7a2d;
                padding: 10px 15px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #2d7a2d;
                border-color: #f4e7a1;
            }
            QPushButton:pressed {
                background-color: #0f2f0f;
            }

            /* Botão de sair (fundo) - estilo diferente */
            QPushButton#exitButton {
                background-color: #5c1a1a;  /* Vermelho escuro */
                color: #f4e7a1;
                border: 2px solid #7a2d2d;
                padding: 8px 15px;
                font-size: 12px;
            }
            QPushButton#exitButton:hover {
                background-color: #7a2d2d;
                border-color: #ff6b6b;
            }
            QPushButton#exitButton:pressed {
                background-color: #3d0f0f;
            }
        """)

        # Aplicar ID ao botão de sair para o estilo específico
        self.btn_exit.setObjectName("exitButton")