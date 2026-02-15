# ui/widgets.py
from PySide6.QtWidgets import QPushButton, QSizePolicy

def compact_button(text: str) -> QPushButton:
    b = QPushButton(text)
    # Horizontal: não expande, fica no tamanho ideal
    b.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    # garante que o cálculo do sizeHint leve o estilo em conta
    b.adjustSize()
    return b
