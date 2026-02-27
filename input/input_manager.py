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
        self.update_timer.start(19)  # ~60 FPS

        self._left_click_pos = None

        # ── Hover / Preview de rota ──
        self._hover_timer = QTimer()
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(50)  # 50ms debounce
        self._hover_timer.timeout.connect(self._process_hover)
        self._pending_hover_pos = None   # (x, y) do mouse pendente
        self._current_hover_pos = None   # rastreia o mouse constantemente
        self._last_hover_tile = None     # evita recalcular se tile não mudou

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

            # Guardrails: não conflitar com atalhos do SO/app
            if key_event.modifiers() & (Qt.ControlModifier | Qt.AltModifier):
                return False

            # Não disparar hotkey enquanto digita em inputs de texto
            if self._is_text_input_focused():
                return False

            # Escape → deselecionar stack
            if key == Qt.Key_Escape:
                if event.type() == QEvent.KeyPress and not key_event.isAutoRepeat():
                    self.controller.on_deselect()
                return True

            # ── Tab / Shift+Tab → ciclar civilização (debug mode) ──
            if key in (Qt.Key_Tab, Qt.Key_Backtab):
                if event.type() == QEvent.KeyPress and not key_event.isAutoRepeat():
                    backward = key == Qt.Key_Backtab or bool(key_event.modifiers() & Qt.ShiftModifier)
                    self.controller.cycle_controlled_civ(-1 if backward else 1)
                return True  # sempre consome para não mudar foco de widget

            # Turn hotkey (evento discreto)
            if key in self.TURN_KEYS:
                if event.type() == QEvent.KeyPress and not key_event.isAutoRepeat():
                    ctrl = self.controller
                    if ctrl and hasattr(ctrl, "_on_turn_advanced"):
                        ctrl._on_turn_advanced()
                    return True
                return True

            # ── Shift → Mostra preview de rota se pressionado ──
            if key == Qt.Key_Shift:
                if event.type() == QEvent.KeyPress and not key_event.isAutoRepeat():
                    # Força o recálculo do hover imediatamente no local atual do mouse
                    if hasattr(self, '_current_hover_pos') and self._current_hover_pos:
                        self._pending_hover_pos = self._current_hover_pos
                        self._hover_timer.start(0)
                elif event.type() == QEvent.KeyRelease and not key_event.isAutoRepeat():
                    # Limpa o preview quando solta o Shift
                    self._restore_command_overlay()
                    self._last_hover_tile = None
                return False  # Retorna False para permitir que outros atalhos com Shift funcionem

            # F9 alterna modo "fog of war" e modo "ver tudo"
            if key == Qt.Key_F9 and event.type() == QEvent.KeyPress and not key_event.isAutoRepeat():
                self.controller.debug_fow_reveal_all = not self.controller.debug_fow_reveal_all
                self.controller.update_fow()
                if self.controller.scene:
                    self.controller.scene.update()
                return True

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
            elif event.type() == QEvent.MouseButtonRelease:
                return self._handle_mouse_release(event)
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
    # HANDLERS DE MOUSE
    # ==========================================
    def _handle_mouse_press(self, event: QMouseEvent) -> bool:
        scene = self.controller.scene
        if not scene:
            return False

        # Botão Esquerdo: Seleção de unidade OU arrasto de câmera
        if event.button() == Qt.LeftButton:
            self.last_mouse_pos = event.position()
            self._left_click_pos = event.position()
            return True

        # Botão Direito: Comando de movimento
        elif event.button() == Qt.RightButton:
            x = event.position().x()
            y = event.position().y()
            tile_coords = scene.get_tile_under_mouse(x, y)
            if tile_coords:
                self.controller.on_tile_right_clicked(tile_coords)
            return True

        return False

    def _handle_mouse_release(self, event: QMouseEvent) -> bool:
        """Detecta se foi click (não drag) para selecionar stack."""
        if event.button() == Qt.LeftButton:
            scene = self.controller.scene
            if not scene:
                return False

            if self._left_click_pos is not None:
                dx = abs(event.position().x() - self._left_click_pos.x())
                dy = abs(event.position().y() - self._left_click_pos.y())

                CLICK_THRESHOLD = 5.0  # pixels
                if dx < CLICK_THRESHOLD and dy < CLICK_THRESHOLD:
                    x = event.position().x()
                    y = event.position().y()
                    tile_coords = scene.get_tile_under_mouse(x, y)
                    if tile_coords:
                        self.controller.on_tile_left_clicked(tile_coords)

            self._left_click_pos = None
            self.last_mouse_pos = None
            return True

        return False

    def _handle_mouse_move(self, event: QMouseEvent) -> bool:
        if not self.controller.camera or not self.controller.scene:
            return False

        # ── Arrasto de câmera (botão esquerdo pressionado) ──
        if (event.buttons() & Qt.LeftButton) and self.last_mouse_pos is not None:
            dx = event.position().x() - self.last_mouse_pos.x()
            dy = event.position().y() - self.last_mouse_pos.y()

            sensitivity = 0.005
            self.controller.camera.orbit(
                delta_azimuth=dx * sensitivity,
                delta_elevation=dy * sensitivity,
            )

            self.last_mouse_pos = event.position()
            self.controller.scene.update()
            return True

        # ── Hover livre (sem botão pressionado) → preview de rota ──
        pos = event.position()
        self._current_hover_pos = (pos.x(), pos.y()) # Salva a posição contínua
        self._pending_hover_pos = (pos.x(), pos.y())
        self._hover_timer.start()  # reinicia debounce
        return False  # não consome — permite propagação normal


    def _handle_wheel(self, event: QWheelEvent) -> bool:
        if not self.controller.camera or not self.controller.scene:
            return False

        delta = event.angleDelta().y()
        zoom_sensitivity = -0.01
        self.controller.camera.zoom(delta * zoom_sensitivity)
        self.controller.scene.update()
        return True

    # ==========================================
    # HOVER / PREVIEW DE ROTA
    # ==========================================

    def _process_hover(self):
        """Chamado após debounce — calcula cursor e exibe preview da rota."""
        if not self._pending_hover_pos:
            return

        x, y = self._pending_hover_pos
        self._pending_hover_pos = None

        controller = self.controller
        scene = controller.scene

        if not scene or not controller.game:
            return

        # Resolve tile sob o mouse
        tile_coords = scene.get_tile_under_mouse(x, y)

        # ── 1. ATUALIZAÇÃO DO CURSOR (Independente do Shift) ──
        if hasattr(controller, 'update_cursor_for_tile'):
            controller.update_cursor_for_tile(tile_coords)

        # Só continua para o preview de rota se tiver stack selecionada
        if not hasattr(controller, 'selection') or not controller.selection.has_selection:
            return

        # Se é o mesmo tile do último hover, não recalcula o dijkstra da rota
        if tile_coords == self._last_hover_tile:
            return
        self._last_hover_tile = tile_coords

        # ── 2. PREVIEW DA ROTA (Apenas se Shift pressionado) ──
        modifiers = QApplication.keyboardModifiers()
        if not (modifiers & Qt.ShiftModifier):
            self._restore_command_overlay()
            return

        if tile_coords is None:
            # Mouse fora do planeta → restaura overlay do comando real
            self._restore_command_overlay()
            return

        # Delega ao controller para calcular a rota
        controller.on_tile_hovered(tile_coords)

    def _restore_command_overlay(self):
        """Restaura o overlay do comando pendente (se houver) ou limpa."""
        controller = self.controller

        if not controller.game or not hasattr(controller, 'selection'):
            if hasattr(controller, '_clear_route_overlay'):
                controller._clear_route_overlay()
            return

        if not controller.selection.has_selection:
            if hasattr(controller, '_clear_route_overlay'):
                controller._clear_route_overlay()
            return

        cmd = controller.game.command_manager.get_command(
            controller.selection.selected_stack_uid
        )
        if cmd and cmd.path:
            controller._set_route_overlay(cmd.path)
        else:
            if hasattr(controller, '_clear_route_overlay'):
                controller._clear_route_overlay()

        if controller.scene:
            controller.scene.update()

    def clear_hover_state(self):
        """Reseta o estado de hover (chamado ao deselecionar)."""
        self._last_hover_tile = None
        self._pending_hover_pos = None
        self._hover_timer.stop()

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
            camera.orbit(-self.rotation_speed, 0)
            moved = True
        if self.keys_pressed.get(Qt.Key_D):
            camera.orbit(self.rotation_speed, 0)
            moved = True
        if self.keys_pressed.get(Qt.Key_W):
            camera.orbit(0, self.rotation_speed)
            moved = True
        if self.keys_pressed.get(Qt.Key_S):
            camera.orbit(0, -self.rotation_speed)
            moved = True

        # Zoom
        if self.keys_pressed.get(Qt.Key_Q):
            camera.zoom(self.zoom_speed)
            moved = True
        if self.keys_pressed.get(Qt.Key_E):
            camera.zoom(-self.zoom_speed)
            moved = True

        if moved:
            if self.controller.scene:
                self.controller.scene.update()
