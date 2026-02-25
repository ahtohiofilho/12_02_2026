from __future__ import annotations

from typing import Optional, Sequence, Tuple

from PySide6.QtOpenGLWidgets import QOpenGLWidget
import OpenGL.GL as gl

from core.rendering.planet_renderer import PlanetRenderer
from core.rendering.camera import Camera

Tile = Tuple[int, int]


class SceneWidget(QOpenGLWidget):
    """
    Cena 3D (OpenGL moderno) que renderiza:
      - Planeta (PlanetRenderer)
        - inclui overlay de rotas (RouteOverlayRenderer) se integrado no PlanetRenderer
        - inclui bandeiras (CivFlag) se integrado no PlanetRenderer

    Regra de arquitetura:
      - Controller chama métodos de SceneWidget (fachada): set_planet_data(), set_route_path(), etc.
      - SceneWidget encaminha para PlanetRenderer e pede update().
      - Captura de input (mouse/teclado) é delegada inteiramente ao InputManager.
    """

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.renderer = PlanetRenderer(self.controller)
        self.camera: Camera | None = None

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

        # (Opcional) depth/stencil melhores para overlays
        fmt = self.format()
        fmt.setDepthBufferSize(24)
        fmt.setStencilBufferSize(8)
        self.setFormat(fmt)

        self._camera_calibrated_planet_id: str | None = None

        # Se quiser MSAA:
        # fmt.setSamples(4)
        # self.setFormat(fmt)

    # ----------------------------
    # Fachada para o Controller
    # ----------------------------
    def set_planet_data(self, planet_object) -> None:
        """
        Recebe Planet e atualiza:
          - geometria + cores do planeta
          - dados das bandeiras (capitais/províncias), se o renderer suportar
          - distância inicial da câmera = 3x raio do planeta (uma vez por planeta/id)
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
        if hasattr(self.renderer, "set_civilization_data"):
            self.renderer.set_civilization_data(planet_object)

        # ==========================================================
        # --- Unidades Militares e Trabalhadores ---
        # Repassa o estado atual do jogo para atualizar as posições.
        # ==========================================================
        if hasattr(self.renderer, "tile_units_renderer") and self.renderer.tile_units_renderer is not None:
            # O planet_object contém a propriedade .stacks com as unidades!
            self.renderer.tile_units_renderer.set_data(planet_object, self.renderer.centros_3d_tiles)

        # --- Câmera: aplicar calibração UMA VEZ por planeta ---
        pid = str(getattr(planet_object, "id", "") or "")

        # Se não existir id, cai para "calibra sempre" (ou você pode escolher não calibrar).
        should_calibrate = (
                self.camera is not None
                and (
                        (pid and pid != getattr(self, "_camera_calibrated_planet_id", None))
                        or (not pid)
                )
        )

        if should_calibrate:
            radius = float(getattr(planet_object, "fator", 0.0) or 0.0)
            if radius > 0.0:
                self.camera.set_distance_from_planet_radius(
                    radius,
                    distance_factor=3.0,  # três vezes o raio
                    min_factor=1.2,  # zoom in não atravessa o planeta
                    max_factor=10.0,  # zoom out folgado
                    near_factor=0.02,  # escala com o planeta
                    far_factor=50.0,  # escala com o planeta
                )
                self.camera.set_aspect_ratio(self.width(), self.height())

                if pid:
                    self._camera_calibrated_planet_id = pid

        # Marcar para (re)criar recursos GL no próximo frame
        self.renderer.dados_atualizados = True
        self.update()

    def set_route_path(self, path_tiles: Optional[Sequence[Tile]]) -> None:
        """
        Define/limpa a rota a ser renderizada no planeta.
        - path_tiles: lista de (x,y) ou None para limpar
        """
        if not hasattr(self, "renderer") or self.renderer is None:
            return

        if hasattr(self.renderer, "set_route_path"):
            self.renderer.set_route_path(path_tiles)
        else:
            # fallback bem defensivo: se você ainda não criou set_route_path no PlanetRenderer
            if hasattr(self.renderer, "route_renderer") and self.renderer.route_renderer is not None:
                self.renderer.route_renderer.state.set_path(path_tiles)

        self.update()

    # ==========================================================
    # COLOR PICKING - FACHADA
    # ==========================================================
    def get_tile_under_mouse(self, x, y):
        """
        Retorna as coordenadas do tile sob o pixel (x, y).
        Precisa ativar o contexto OpenGL antes de qualquer chamada GL.
        """
        if not self.renderer or not self.renderer.color_picker:
            return None

        if not self.renderer.color_picker.initialized:
            return None

        if not self.camera:
            return None

        # ===== CORREÇÃO: ativar contexto GL =====
        self.makeCurrent()
        try:
            result = self.renderer.color_picker.get_tile_at_pixel(
                x, y,
                self.width(), self.height(),
                self.camera,
            )
        except Exception as e:
            print(f"⚠️ [Scene] Erro no color picker: {e}")
            result = None
        finally:
            self.doneCurrent()
        # ========================================

        return result

    # ----------------------------
    # Ciclo de vida OpenGL (QOpenGLWidget)
    # ----------------------------
    def initializeGL(self) -> None:
        gl.glClearColor(0.05, 0.05, 0.1, 1.0)
        gl.glEnable(gl.GL_DEPTH_TEST)

        # Transparência (overlays como bandeiras/rota/highlight)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

        # Inicializa a câmera orbital (placeholder).
        # A distância real será recalibrada quando set_planet_data() for chamado.
        self.camera = Camera(distance=5.0)
        self.camera.set_aspect_ratio(self.width(), self.height())

    def resizeGL(self, w: int, h: int) -> None:
        gl.glViewport(0, 0, w, h)
        if self.camera:
            self.camera.set_aspect_ratio(w, h)

    def paintGL(self) -> None:
        if not self.camera:
            return

        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

        if self.renderer.needs_init():
            self.renderer.init_gl()

        view_matrix = self.camera.get_view_matrix()
        projection_matrix = self.camera.get_projection_matrix()

        # Pegar a posição da câmera para o Billboarding (Sprites 2D em 3D)
        cam_pos = getattr(self.camera, 'position', [0.0, 0.0, 5.0])
        if callable(cam_pos):
            cam_pos = cam_pos()

        self.renderer.render(view_matrix, projection_matrix, cam_pos)

    def update_units_data(self, planet_object) -> None:
        """
        Lê novamente as pilhas (stacks) do planeta e atualiza
        os sprites 3D das unidades e trabalhadores.
        """
        if not planet_object:
            return

        if hasattr(self.renderer, "tile_units_renderer") and self.renderer.tile_units_renderer is not None:
            self.renderer.tile_units_renderer.set_data(planet_object, self.renderer.centros_3d_tiles)

        self.update()  # Manda a placa de vídeo desenhar o novo quadro
