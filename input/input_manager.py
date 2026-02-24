# input/input_manager.py
from PySide6.QtCore import QObject, QTimer, QEvent, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication, QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox
from collections import defaultdict


class InputManager(QObject):
    """
    Gerenciador global de input.

    Captura teclas de navegação da câmera independentemente de qual widget está focado.
    Captura eventos de mouse EXCLUSIVAMENTE quando ocorrem sobre o SceneWidget.
    Usa um event filter instalado na aplicação para captura.
    """

    # Teclas que serão capturadas globalmente para controle de câmera
    CAMERA_KEYS = {Qt.Key_W, Qt.Key_S, Qt.Key_A, Qt.Key_D, Qt.Key_Q, Qt.Key_E}
    TURN_KEYS = {Qt.Key_Return}

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.keys_pressed = defaultdict(bool)

        # Variáveis de estado do mouse
        self.last_mouse_pos = None

        # Velocidades (para rotação/zoom orbital)
        self.rotation_speed = 0.02
        self.zoom_speed = 0.2

        # Timer para movimento contínuo
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._process_input)
        self.update_timer.start(16)  # ~60 FPS

    def install_global_filter(self, app: QApplication):
        """
        Instala o event filter na aplicação para captura global de teclas e cliques.
        Deve ser chamado após criar a QApplication.
        """
        app.installEventFilter(self)
        print("✅ [InputManager] Global event filter installed")

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """
        Intercepta eventos da aplicação inteira.
        """
        # ==========================================
        # 1. EVENTOS DE TECLADO (Global)
        # ==========================================
        if event.type() in (QEvent.KeyPress, QEvent.KeyRelease):
            key_event: QKeyEvent = event
            key = key_event.key()

            # Guardrails corporativos: não conflitar com atalhos do SO/app
            if key_event.modifiers() & (Qt.ControlModifier | Qt.AltModifier):
                return False

            # Não disparar hotkey enquanto digita em inputs de texto
            if self._is_text_input_focused():
                return False

            # Turn hotkey (evento discreto)
            if key in self.TURN_KEYS:
                if event.type() == QEvent.KeyPress and not key_event.isAutoRepeat():
                    ctrl = self.controller
                    if ctrl and hasattr(ctrl, "_on_turn_advanced"):
                        ctrl._on_turn_advanced()
                    return True  # consome
                return True  # consome keyrelease também (evita propagação)

            # Camera keys (estado contínuo)
            if key not in self.CAMERA_KEYS:
                return False

            if event.type() == QEvent.KeyPress:
                self.keys_pressed[key] = True
                return True

            if event.type() == QEvent.KeyRelease:
                if not key_event.isAutoRepeat():
                    self.keys_pressed[key] = False
                return True

        # ==========================================
        # 2. EVENTOS DE MOUSE (Apenas no SceneWidget)
        # ==========================================
        scene = self.controller.scene
        if scene and obj == scene:
            if event.type() == QEvent.MouseButtonPress:
                return self._handle_mouse_press(event)
            elif event.type() == QEvent.MouseMove:
                return self._handle_mouse_move(event)
            elif event.type() == QEvent.Wheel:
                return self._handle_wheel(event)

        return False

    def _is_text_input_focused(self) -> bool:
        """Verifica se o widget focado é um campo de entrada de texto."""
        focused = QApplication.focusWidget()
        if focused is None:
            return False
        return isinstance(focused, (QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox))

    # ==========================================
    # HANDLERS DE MOUSE (Transferidos da SceneWidget)
    # ==========================================
    def _handle_mouse_press(self, event: QMouseEvent) -> bool:
        scene = self.controller.scene

        # Botão Esquerdo: Inicia o arrasto (rotação da câmera)
        if event.button() == Qt.LeftButton:
            self.last_mouse_pos = event.position()
            return True

        # Botão Direito: Color Picking (Seleção de Tile)
        elif event.button() == Qt.RightButton:
            x = event.position().x()
            y = event.position().y()

            tile_coords = scene.get_tile_under_mouse(x, y)

            if tile_coords:
                print(f"🎯 [InputManager] Clicou no tile: {tile_coords}")
                # TODO: No futuro, chamar self.controller.on_tile_clicked(tile_coords)
            else:
                print("🌊 [InputManager] Clicou no espaço/fundo preto.")
            return True

        return False

    def _handle_mouse_move(self, event: QMouseEvent) -> bool:
        if not self.controller.camera or not self.controller.scene:
            return False

        if (event.buttons() & Qt.LeftButton) and self.last_mouse_pos is not None:
            dx = event.position().x() - self.last_mouse_pos.x()
            dy = event.position().y() - self.last_mouse_pos.y()

            sensitivity = 0.005
            self.controller.camera.orbit(delta_azimuth=dx * sensitivity, delta_elevation=dy * sensitivity)

            self.last_mouse_pos = event.position()
            self.controller.scene.update()
            return True

        return False

    def _handle_wheel(self, event: QWheelEvent) -> bool:
        if not self.controller.camera or not self.controller.scene:
            return False

        delta = event.angleDelta().y()
        zoom_sensitivity = -0.01
        self.controller.camera.zoom(delta * zoom_sensitivity)
        self.controller.scene.update()
        return True

    # ==========================================
    # PROCESSAMENTO DE ESTADO CONTÍNUO (Loop 60 FPS)
    # ==========================================
    def _process_input(self):
        """Processa input de teclado para controle orbital contínuo."""
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
            if self.controller.scene:
                self.controller.scene.update()
