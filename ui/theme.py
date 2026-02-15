# ui/theme.py
APP_QSS = """
/* ===== Base geral ===== */
QMainWindow, QWidget {
    background-color: #1E1F22;
    color: #E6E6E6;
    font-size: 13px;
}

QWidget#centralWidget {
    background-color: #1E1F22;
}

/* ===== Sidebar ===== */
QFrame#Sidebar {
    background-color: #2B2D31;
    border-right: 1px solid #3A3D43;
}

/* ===== Botões (padrão) ===== */
QPushButton {
    background-color: #3A3D43;
    color: #E6E6E6;
    border: 1px solid #4A4E57;

    /* padding padrão: texto + folga */
    padding: 6px 12px;

    border-radius: 6px;

    /* evita que alguns estilos deixem botão “alto demais” */
    min-height: 24px;
}

QPushButton:hover {
    background-color: #454952;
    border-color: #5A5F6B;
}

QPushButton:pressed {
    background-color: #2F3136;
}

/* ===== Botão especial (Exit) =====
   Use: btn_exit.setObjectName("dangerButton")
*/
QPushButton#dangerButton {
    background-color: #7A1E1E;
    border: 1px solid #A33A3A;
    color: #FFFFFF;
}

QPushButton#dangerButton:hover {
    background-color: #8E2424;
    border-color: #C24A4A;
}

QPushButton#dangerButton:pressed {
    background-color: #611717;
}

/* ===== Tooltip ===== */
QToolTip {
    background-color: #2B2D31;
    color: #E6E6E6;
    border: 1px solid #4A4E57;
}
"""
