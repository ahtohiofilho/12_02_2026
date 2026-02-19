# input/input_manager.py
from PySide6.QtCore import QObject, QTimer, QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox
from collections import defaultdict


class InputManager(QObject):
    """
    Gerenciador global de input.

    Captura teclas de navegação da câmera independentemente de qual widget está focado.
    Usa um event filter instalado na aplicação para captura global.
    """

    # Teclas que serão capturadas globalmente para controle de câmera
    CAMERA_KEYS = {Qt.Key_W, Qt.Key_S, Qt.Key_A, Qt.Key_D, Qt.Key_Q, Qt.Key_E}
    TURN_KEYS = {Qt.Key_Return}

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.keys_pressed = defaultdict(bool)

        # Velocidades (para rotação/zoom orbital)
        self.rotation_speed = 0.02
        self.zoom_speed = 0.2

        # Timer para movimento contínuo
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._process_input)
        self.update_timer.start(16)  # ~60 FPS

    def install_global_filter(self, app: QApplication):
        """
        Instala o event filter na aplicação para captura global de teclas.
        Deve ser chamado após criar a QApplication.
        """
        app.installEventFilter(self)
        print("✅ [InputManager] Global event filter installed")

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() not in (QEvent.KeyPress, QEvent.KeyRelease):
            return False

        key_event: QKeyEvent = event
        key = key_event.key()

        # Guardrails corporativos: não conflitar com atalhos do SO/app
        if key_event.modifiers() & (Qt.ControlModifier | Qt.AltModifier):
            return False

        # Não disparar hotkey enquanto digita em inputs
        if self._is_text_input_focused():
            return False

        # 1) Turn hotkey (evento discreto)
        if key in self.TURN_KEYS:
            if event.type() == QEvent.KeyPress and not key_event.isAutoRepeat():
                ctrl = self.controller
                if ctrl and hasattr(ctrl, "_on_turn_advanced"):
                    ctrl._on_turn_advanced()
                return True  # consome
            return True  # consome keyrelease também (evita propagação)

        # 2) Camera keys (estado contínuo)
        if key not in self.CAMERA_KEYS:
            return False

        if event.type() == QEvent.KeyPress:
            self.keys_pressed[key] = True
            return True

        if event.type() == QEvent.KeyRelease:
            if not key_event.isAutoRepeat():
                self.keys_pressed[key] = False
            return True

        return False

    def _is_text_input_focused(self) -> bool:
        """Verifica se o widget focado é um campo de entrada de texto."""
        focused = QApplication.focusWidget()
        if focused is None:
            return False
        return isinstance(focused, (QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox))

    # Métodos legados (mantidos para compatibilidade, mas não mais necessários)
    def key_press_event(self, event):
        """Legado: usado quando eventos vêm diretamente de um widget."""
        self.keys_pressed[event.key()] = True
        event.accept()

    def key_release_event(self, event):
        """Legado: usado quando eventos vêm diretamente de um widget."""
        self.keys_pressed[event.key()] = False
        event.accept()

    def _process_input(self):
        """Processa input para controle orbital."""
        if not self.controller or not hasattr(self.controller, 'camera') or not self.controller.camera:
            return

        camera = self.controller.camera
        moved = False

        # Rotação orbital
        if self.keys_pressed.get(Qt.Key_A):
            camera.orbit(-self.rotation_speed, 0)  # Esquerda
            moved = True
        if self.keys_pressed.get(Qt.Key_D):
            camera.orbit(self.rotation_speed, 0)  # Direita
            moved = True
        if self.keys_pressed.get(Qt.Key_W):
            camera.orbit(0, self.rotation_speed)  # Para cima
            moved = True
        if self.keys_pressed.get(Qt.Key_S):
            camera.orbit(0, -self.rotation_speed)  # Para baixo
            moved = True

        # Zoom
        if self.keys_pressed.get(Qt.Key_Q):
            camera.zoom(self.zoom_speed)  # Zoom out
            moved = True
        if self.keys_pressed.get(Qt.Key_E):
            camera.zoom(-self.zoom_speed)  # Zoom in
            moved = True

        # Redesenha se houve movimento
        if moved:
            # Atualiza o widget de cena diretamente
            if self.controller.window and self.controller.window.scene:
                self.controller.window.scene.update()
