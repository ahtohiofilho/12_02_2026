# ui/theme.py
APP_QSS = """
/* ===== Base geral ===== */
QMainWindow, QWidget {
    background-color: #1E1F22;   /* cinza escuro */
    color: #E6E6E6;
    font-size: 13px;
}

/* O widget central (evita “faixas” claras) */
QWidget#centralWidget {
    background-color: #1E1F22;
}

/* ===== Sidebar ===== */
QFrame#Sidebar {
    background-color: #2B2D31;   /* um pouco mais claro para separar do fundo */
    border-right: 1px solid #3A3D43;
}

/* ===== Botões (neutros) ===== */
QPushButton {
    background-color: #3A3D43;
    color: #E6E6E6;
    border: 1px solid #4A4E57;
    padding: 8px 12px;
    border-radius: 6px;
}

QPushButton:hover {
    background-color: #454952;
    border-color: #5A5F6B;
}

QPushButton:pressed {
    background-color: #2F3136;
}

/* Botão Exit continua com o estilo atual (você disse que vai manter por enquanto).
   Se quiser que ele fique coerente também, depois a gente mexe aqui. */

/* ===== Layouts com separação suave (opcional) ===== */
QToolTip {
    background-color: #2B2D31;
    color: #E6E6E6;
    border: 1px solid #4A4E57;
}
"""
