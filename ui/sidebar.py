# ui/sidebar.py
from PySide6.QtWidgets import QFrame, QVBoxLayout, QPushButton, QSizePolicy
from PySide6.QtCore import Qt

class Sidebar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("Sidebar")  # <-- importante pro QSS
        self.setFrameStyle(QFrame.NoFrame)
        self.setMinimumWidth(200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignTop)

        self.btn_create = QPushButton("Create Planet")
        self.btn_create.setFixedWidth(140)
        self.btn_create.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(self.btn_create, alignment=Qt.AlignCenter)

        layout.addStretch(1)

        self.btn_exit = QPushButton("Exit")
        self.btn_exit.setObjectName("exitButton")  # mantém o “danger”
        self.btn_exit.setFixedWidth(100)
        self.btn_exit.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(self.btn_exit, alignment=Qt.AlignCenter)
