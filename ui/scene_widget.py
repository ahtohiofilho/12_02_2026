from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent
import OpenGL.GL as gl
from core.rendering.planet_renderer import PlanetRenderer
from core.rendering.camera import Camera


class SceneWidget(QOpenGLWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.renderer = PlanetRenderer(self.controller)
        self.camera = None  # Será inicializado em initializeGL
        self.last_mouse_pos = None

        # ... (self.cores_biomas permanece igual)
        self.cores_biomas = {
            'Ocean': (0, 23, 98), 'Sea': (8, 33, 113), 'Coast': (12, 71, 108),
            'Meadow': (91, 174, 70), 'Savanna': (231, 190, 141), 'Forest': (75, 129, 66),
            'Desert': (242, 242, 166), 'Hills': (201, 147, 121), 'Mountains': (158, 86, 86),
            'Ice': (245, 255, 245)
        }

    # ... (set_planet_data permanece igual)
    def set_planet_data(self, planet_object):
        if not planet_object:
            return
        self.renderer.set_tile_data(planet_object.polygons_map, planet_object.centers_map)
        tile_colors = {}
        for node, data in planet_object.graph.nodes(data=True):
            biome = data.get('bioma', 'Ocean')
            tile_colors[node] = self.cores_biomas.get(biome, (255, 0, 255))
        self.renderer.set_tile_colors(tile_colors)
        self.renderer.dados_atualizados = True
        self.update()

    def initializeGL(self):
        gl.glClearColor(0.05, 0.05, 0.1, 1.0)
        gl.glEnable(gl.GL_DEPTH_TEST)
        #gl.glEnable(gl.GL_CULL_FACE)

        # Inicializa a sua câmera, definindo uma distância inicial
        self.camera = Camera(distance=15.0)
        self.camera.set_aspect_ratio(self.width(), self.height())

    def resizeGL(self, w, h):
        gl.glViewport(0, 0, w, h)
        if self.camera:
            # Chama o método correto para atualizar o aspect ratio
            self.camera.set_aspect_ratio(w, h)

    def paintGL(self):
        if not self.camera:
            return

        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

        if self.renderer.needs_init():
            self.renderer.init_gl()

        # Pega as matrizes numpy da sua câmera
        view_matrix = self.camera.get_view_matrix()
        projection_matrix = self.camera.get_projection_matrix()

        # ===== DEBUG: VERIFICAÇÃO DAS MATRIZES =====
        print("\n" + "=" * 50)
        print("🔍 Matriz View (câmera):")
        print(view_matrix)  # Imprime a matriz 4x4
        print("\n🔍 Matriz Projection (câmera):")
        print(projection_matrix)
        print("=" * 50 + "\n")
        # ===== FIM DO DEBUG =====

        # O seu PlanetRenderer já espera matrizes numpy e faz a transposição (view_matrix.T)
        self.renderer.render(view_matrix, projection_matrix)

    # --- Controles de Câmera Adaptados ---
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.last_mouse_pos = event.position()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.LeftButton:
            if self.last_mouse_pos is not None:
                dx = event.position().x() - self.last_mouse_pos.x()
                dy = event.position().y() - self.last_mouse_pos.y()

                # Converte o movimento do mouse em radianos para a câmera orbital
                sensitivity = 0.005
                self.camera.orbit(delta_azimuth=dx * sensitivity, delta_elevation=dy * sensitivity)

                self.last_mouse_pos = event.position()
                self.update()

    def wheelEvent(self, event):
        # O delta do scroll é usado para o zoom
        delta = event.angleDelta().y()
        zoom_sensitivity = -0.01  # Negativo para zoom in ao rolar para frente
        self.camera.zoom(delta * zoom_sensitivity)
        self.update()
