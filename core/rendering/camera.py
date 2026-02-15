# core/rendering/camera.py
import math
import numpy as np
import glm


def _normalize(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    if n == 0.0:
        return v
    return v / n


class Camera:
    """
    Câmera orbital focada na origem (0,0,0).

    Convenção (consolidada / eficiente):
    - NÃO aplica flip no eixo X em look_at_tile().
      Se você quiser espelhar o mundo, faça isso no renderer (uModel) de forma consistente.
    """

    __slots__ = (
        "fator",
        "distance",
        "azimuth",
        "elevation",
        "selected_tile_position",
        "min_distance",
        "max_distance",
        "min_elevation",
        "max_elevation",
        "fov",
        "aspect_ratio",
        "near",
        "far",
        "_projection_matrix",
        "_projection_dirty",
        "_view_matrix",
        "_view_dirty",
        "position",
        "target",
        "front",
        "right",
        "up",
        "_world_up",
    )

    def __init__(self, distance: float = 5.0):
        # Parâmetros orbitais
        self.fator = float(distance)
        self.distance = float(distance)
        self.azimuth = math.radians(45.0)
        self.elevation = math.radians(30.0)
        self.selected_tile_position = None

        # Limites
        self.min_distance = self.fator / 2.0
        self.max_distance = self.fator * 2.0
        self.min_elevation = -math.pi / 2.0 + 0.1
        self.max_elevation = math.pi / 2.0 - 0.1

        # Projeção
        self.fov = 45.0
        self.aspect_ratio = 1.0
        self.near = 0.1
        self.far = 100.0

        # Cache
        self._projection_matrix = None
        self._projection_dirty = True
        self._view_matrix = None
        self._view_dirty = True

        # Vetores
        self._world_up = np.array([0.0, 1.0, 0.0], dtype=np.float64)
        self.target = np.array([0.0, 0.0, 0.0], dtype=np.float64)
        self.position = np.array([0.0, 0.0, 0.0], dtype=np.float64)

        self.front = np.array([0.0, 0.0, -1.0], dtype=np.float64)
        self.right = np.array([1.0, 0.0, 0.0], dtype=np.float64)
        self.up = np.array([0.0, 1.0, 0.0], dtype=np.float64)

        self._update_position()

    def _update_position(self) -> None:
        ce = math.cos(self.elevation)
        se = math.sin(self.elevation)
        sa = math.sin(self.azimuth)
        ca = math.cos(self.azimuth)

        # Orbital em torno da origem
        x = self.distance * ce * sa
        y = self.distance * se
        z = self.distance * ce * ca

        self.position[...] = (x, y, z)
        self.target[...] = (0.0, 0.0, 0.0)

        # Base da câmera
        self.front = _normalize(self.target - self.position)
        # Sistema destro (OpenGL): right = front x world_up
        self.right = _normalize(np.cross(self.front, self._world_up))
        self.up = _normalize(np.cross(self.right, self.front))

        self._view_dirty = True

    def orbit(self, delta_azimuth: float, delta_elevation: float) -> None:
        self.azimuth += float(delta_azimuth)
        self.elevation += float(delta_elevation)

        # Clamp elevação
        if self.elevation < self.min_elevation:
            self.elevation = self.min_elevation
        elif self.elevation > self.max_elevation:
            self.elevation = self.max_elevation

        self._update_position()

    def zoom(self, delta: float) -> None:
        self.distance += float(delta)

        if self.distance < self.min_distance:
            self.distance = self.min_distance
        elif self.distance > self.max_distance:
            self.distance = self.max_distance

        self._update_position()

    def get_view_matrix(self) -> np.ndarray:
        if self._view_dirty or self._view_matrix is None:
            view = glm.lookAt(
                glm.vec3(float(self.position[0]), float(self.position[1]), float(self.position[2])),
                glm.vec3(0.0, 0.0, 0.0),
                glm.vec3(float(self.up[0]), float(self.up[1]), float(self.up[2])),
            )
            self._view_matrix = np.array(view, dtype=np.float32, copy=False)
            self._view_dirty = False
        return self._view_matrix

    def get_projection_matrix(self) -> np.ndarray:
        if self._projection_dirty or self._projection_matrix is None:
            proj = glm.perspective(
                glm.radians(float(self.fov)),
                float(self.aspect_ratio),
                float(self.near),
                float(self.far),
            )
            self._projection_matrix = np.array(proj, dtype=np.float32, copy=False)
            self._projection_dirty = False
        return self._projection_matrix

    def set_aspect_ratio(self, width: float, height: float) -> None:
        h = float(height)
        new_aspect = float(width) / h if h > 0.0 else 1.0
        if abs(new_aspect - self.aspect_ratio) > 1e-6:
            self.aspect_ratio = new_aspect
            self._projection_dirty = True

    def look_at_tile(self, point_3d) -> None:
        """
        Reorienta a câmera para que a direção (a partir da origem) aponte para o tile,
        mantendo o alvo na origem. NÃO aplica flip de eixo.
        """
        if hasattr(point_3d, "x"):
            x, y, z = float(point_3d.x), float(point_3d.y), float(point_3d.z)
        else:
            x, y, z = (float(point_3d[0]), float(point_3d[1]), float(point_3d[2]))

        # Direção na esfera (unitária)
        norm = math.sqrt(x * x + y * y + z * z)
        if norm == 0.0:
            return

        dx, dy, dz = x / norm, y / norm, z / norm

        # Ângulos orbitais
        self.azimuth = math.atan2(dx, dz)
        self.elevation = math.asin(dy)

        # Clamp elevação
        if self.elevation < self.min_elevation:
            self.elevation = self.min_elevation
        elif self.elevation > self.max_elevation:
            self.elevation = self.max_elevation

        self._update_position()
