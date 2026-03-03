# ui/scene.py
from __future__ import annotations

from typing import Optional, Sequence, Tuple

from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6 import QtCore

import OpenGL.GL as gl

from core.rendering.planet_renderer import PlanetRenderer
from core.rendering.camera import Camera

Tile = Tuple[int, int]


class SceneWidget(QOpenGLWidget):
    """
    Cena 3D (OpenGL) com PlanetRenderer.

    Regras de arquitetura:
      - Controller chama APENAS métodos da SceneWidget (fachada): set_planet_data(), set_route_path(), set_fow().
      - SceneWidget NÃO deve chamar OpenGL fora de initializeGL/resizeGL/paintGL (ou makeCurrent explicitamente).
      - set_fow() não faz upload GL direto: apenas marca "dirty" e o upload ocorre no paintGL.

    Extensão:
      - "Route reveal": tiles de uma rota podem ser forçados a aparecer (vis=1.0) enquanto o overlay estiver ativo,
        sem alterar o Fog of War real do jogo. Também é timing-safe (upload no paintGL).
    """

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller

        self.renderer = PlanetRenderer(self.controller)
        # Compat com código antigo (se houver):
        self.planet_renderer = self.renderer

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

        # ----------------------------
        # FoW "pending" (evita GL fora do contexto, ex.: F9 no eventFilter)
        # ----------------------------
        self._pending_fow: tuple[set[Tile], set[Tile]] | None = None
        self._fow_dirty: bool = False
        self._queued_initial_fow: bool = False

        # ----------------------------
        # NOVO: Route reveal "pending" (tiles da rota forçados a aparecer)
        # ----------------------------
        self._pending_route_reveal: set[Tile] | None = None
        self._route_reveal_dirty: bool = False

    # ----------------------------
    # Fachada para o Controller
    # ----------------------------
    def set_planet_data(self, planet_object) -> None:
        if not planet_object:
            return

        # --- Planeta (tiles) ---
        self.renderer.set_tile_data(planet_object.polygons_map, planet_object.centers_map)

        tile_colors: dict[Tile, tuple[int, int, int]] = {}
        for node, data in planet_object.graph.nodes(data=True):
            biome = data.get("bioma", "Ocean")
            tile_colors[node] = self.cores_biomas.get(biome, (255, 0, 255))
        self.renderer.set_tile_colors(tile_colors)

        # --- Bandeiras (Civilizations/Provinces) ---
        if hasattr(self.renderer, "set_civilization_data"):
            self.renderer.set_civilization_data(planet_object)

        # --- Unidades (se existir) ---
        tur = getattr(self.renderer, "tile_units_renderer", None)
        if tur is not None:
            tur.set_data(planet_object, self.renderer.centros_3d_tiles)

        # --- Câmera: calibrar uma vez por planeta/id ---
        pid = str(getattr(planet_object, "id", "") or "")
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
                    distance_factor=3.0,
                    min_factor=1.2,
                    max_factor=10.0,
                    near_factor=0.02,
                    far_factor=50.0,
                )
                self.camera.set_aspect_ratio(self.width(), self.height())
                if pid:
                    self._camera_calibrated_planet_id = pid

        # Marcar para (re)criar recursos GL no próximo frame
        self.renderer.dados_atualizados = True
        self.update()

    def set_route_path(self, path_tiles: Optional[Sequence[Tile]]) -> None:
        if not self.renderer:
            return

        normalized: list[Tile] | None = None
        if path_tiles:
            normalized = []
            for t in path_tiles:
                if isinstance(t, (list, tuple)) and len(t) >= 2:
                    normalized.append((int(t[0]), int(t[1])))
            if not normalized:
                normalized = None

        self.renderer.set_route_path(normalized)
        self.update()

    def update_units_data(self, planet_object) -> None:
        if not planet_object:
            return

        tur = getattr(self.renderer, "tile_units_renderer", None)
        if tur is not None:
            # Propagar civ controlada para o renderer
            if hasattr(self.controller, "controlled_civ_id"):
                tur._controlled_civ_id = self.controller.controlled_civ_id
            tur.set_data(planet_object, self.renderer.centros_3d_tiles)

        self.update()

    # ----------------------------
    # FoW (fachada): NÃO chama GL aqui
    # ----------------------------
    def set_fow(self, explored, visible) -> None:
        """
        Recebe explored/visible e agenda o upload para o próximo paintGL.
        Isso evita GL_INVALID_OPERATION quando chamado de eventFilter/teclas (ex.: F9).
        """
        self._pending_fow = (set(explored), set(visible))
        self._fow_dirty = True
        self.update()  # pede repaint

    def _apply_pending_fow_if_needed(self) -> None:
        if not self._fow_dirty or self._pending_fow is None:
            return
        if not self.renderer or self.camera is None:
            return
        if self.renderer.needs_init():
            return

        explored, visible = self._pending_fow
        self._fow_dirty = False

        # Upload GL (permitido aqui: estamos no paintGL)
        self.renderer.update_visibility_texture(explored, visible)

        # CPU-side filters (não-GL)
        tur = getattr(self.renderer, "tile_units_renderer", None)
        if tur is not None:
            tur.visible_tiles = visible
            if hasattr(self.controller, "controlled_civ_id"):
                tur._controlled_civ_id = self.controller.controlled_civ_id

        cfr = getattr(self.renderer, "civ_flag_renderer", None)
        if cfr is not None:
            cfr.explored_tiles = explored
            cfr.visible_tiles = visible

    # ----------------------------
    # Color picking (precisa makeCurrent)
    # ----------------------------
    def get_tile_under_mouse(self, x, y):
        if not self.renderer or not getattr(self.renderer, "color_picker", None):
            return None
        if not self.renderer.color_picker.initialized:
            return None
        if not self.camera:
            return None

        self.makeCurrent()
        try:
            return self.renderer.color_picker.get_tile_at_pixel(
                x, y,
                self.width(), self.height(),
                self.camera,
            )
        except Exception as e:
            print(f"⚠️ [Scene] Erro no color picker: {e}")
            return None
        finally:
            self.doneCurrent()

    # ----------------------------
    # Ciclo de vida OpenGL (QOpenGLWidget)
    # ----------------------------
    def initializeGL(self) -> None:
        gl.glClearColor(0.0, 0.0, 0.0, 1.0)
        gl.glEnable(gl.GL_DEPTH_TEST)

        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

        self.camera = Camera(distance=5.0)
        self.camera.set_aspect_ratio(self.width(), self.height())

    def resizeGL(self, w: int, h: int) -> None:
        w = max(1, w)
        h = max(1, h)
        gl.glViewport(0, 0, w, h)
        if self.camera:
            self.camera.set_aspect_ratio(w, h)

    def paintGL(self) -> None:
        if not self.camera:
            return

        gl.glClearColor(0.0, 0.0, 0.0, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

        if self.renderer.needs_init():
            ok = self.renderer.init_gl()
            if ok and not getattr(self, "_queued_initial_fow", False):
                self._queued_initial_fow = True
                # agenda update_fow fora do paintGL (mas ele só vai setar pending)
                QtCore.QTimer.singleShot(0, self.controller.update_fow)

        # 1) aplica FoW real primeiro (atualiza last_fow no renderer)
        self._apply_pending_fow_if_needed()

        view_matrix = self.camera.get_view_matrix()
        projection_matrix = self.camera.get_projection_matrix()

        cam_pos = getattr(self.camera, "position", [0.0, 0.0, 5.0])
        if callable(cam_pos):
            cam_pos = cam_pos()

        self.renderer.render(view_matrix, projection_matrix, cam_pos)

    def set_active_stack_uid(self, stack_uid: str | None) -> None:
        tur = getattr(self.renderer, "tile_units_renderer", None)
        if tur is not None:
            tur.active_stack_uid = stack_uid
        self.update()
