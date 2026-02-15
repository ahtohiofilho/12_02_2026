# ui/scene.py
from __future__ import annotations

from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent
import OpenGL.GL as gl

from core.rendering.planet_renderer import PlanetRenderer
from core.rendering.camera import Camera


class SceneWidget(QOpenGLWidget):
    """
    Cena 3D (OpenGL moderno) que renderiza:
      - Planeta (PlanetRenderer)
      - Bandeiras por civilização/províncias (via CivFlag dentro do PlanetRenderer)

    Integração esperada no PlanetRenderer:
      - self.civ_flag_renderer (instância de core.rendering.civ_flag.CivFlag)
      - método: set_civilization_data(planet)
      - no render(): chamar civ_flag_renderer.render(view, projection) após o planeta
      - cleanup_gl(): limpar recursos do civ_flag_renderer

    Observação: este módulo não cria shaders nem buffers de bandeira; só dispara os hooks.
    """

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.renderer = PlanetRenderer(self.controller)
        self.camera: Camera | None = None
        self.last_mouse_pos = None

        self.cores_biomas = {
            "Ocean": (0, 23, 98),
            "Sea": (8, 33, 113),
            "Coast": (12, 71, 108),
            "Meadow": (91, 174, 70),
            "Savanna": (231, 190, 141),
            "Forest": (75, 129, 66),
            "Desert": (242, 242, 166),
            "Hills": (201, 147, 121),
            "Mountains": (158, 86, 86),
            "Ice": (245, 255, 245),
        }

        # (Opcional) pede um depth buffer melhor pro overlay (bandeiras) ficar estável
        fmt = self.format()
        fmt.setDepthBufferSize(24)
        fmt.setStencilBufferSize(8)
        self.setFormat(fmt)

        # Se quiser MSAA:
        # fmt.setSamples(4)
        # self.setFormat(fmt)

    def set_planet_data(self, planet_object):
        """
        Recebe Planet e atualiza:
          - geometria + cores do planeta
          - dados das bandeiras (capitais/províncias), se o renderer suportar
        """
        if not planet_object:
            return

        # --- Planeta (tiles) ---
        self.renderer.set_tile_data(planet_object.polygons_map, planet_object.centers_map)

        tile_colors = {}
        for node, data in planet_object.graph.nodes(data=True):
            biome = data.get("bioma", "Ocean")
            tile_colors[node] = self.cores_biomas.get(biome, (255, 0, 255))
        self.renderer.set_tile_colors(tile_colors)

        # --- Bandeiras (Civilizations/Provinces) ---
        # Hook: PlanetRenderer deve repassar pro CivFlag internamente.
        if hasattr(self.renderer, "set_civilization_data"):
            try:
                self.renderer.set_civilization_data(planet_object)
            except TypeError:
                # Se sua assinatura antiga ainda for set_civilization_data(planeta)
                self.renderer.set_civilization_data(planet_object)

        self.renderer.dados_atualizados = True
        self.update()

    def initializeGL(self):
        gl.glClearColor(0.05, 0.05, 0.1, 1.0)
        gl.glEnable(gl.GL_DEPTH_TEST)

        # Transparência (bandeiras). O renderer de bandeiras também pode habilitar/desabilitar.
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

        # Inicializa a câmera orbital
        self.camera = Camera(distance=15.0)
        self.camera.set_aspect_ratio(self.width(), self.height())

    def resizeGL(self, w, h):
        gl.glViewport(0, 0, w, h)
        if self.camera:
            self.camera.set_aspect_ratio(w, h)

    def paintGL(self):
        if not self.camera:
            return

        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

        if self.renderer.needs_init():
            self.renderer.init_gl()

        view_matrix = self.camera.get_view_matrix()
        projection_matrix = self.camera.get_projection_matrix()

        # PlanetRenderer deve renderizar planeta e, se integrado, bandeiras (CivFlag)
        self.renderer.render(view_matrix, projection_matrix)

    # --- Controles de Câmera ---
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.last_mouse_pos = event.position()

    def mouseMoveEvent(self, event: QMouseEvent):
        if (event.buttons() & Qt.LeftButton) and self.last_mouse_pos is not None and self.camera is not None:
            dx = event.position().x() - self.last_mouse_pos.x()
            dy = event.position().y() - self.last_mouse_pos.y()

            sensitivity = 0.005
            self.camera.orbit(delta_azimuth=dx * sensitivity, delta_elevation=dy * sensitivity)

            self.last_mouse_pos = event.position()
            self.update()

    def wheelEvent(self, event):
        if not self.camera:
            return
        delta = event.angleDelta().y()
        zoom_sensitivity = -0.01
        self.camera.zoom(delta * zoom_sensitivity)
        self.update()
