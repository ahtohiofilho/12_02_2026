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

    # ------------------------------------------------------------------
    # NOVO: calibração por raio do planeta
    # ------------------------------------------------------------------

    def set_distance_from_planet_radius(
        self,
        radius: float,
        *,
        distance_factor: float = 2.2,
        min_factor: float = 1.05,
        max_factor: float = 6.0,
        near_factor: float = 0.02,
        far_factor: float = 25.0,
        clamp_current_angles: bool = True,
    ) -> None:
        """
        Ajusta distância inicial, limites e clipping (near/far) com base no raio do planeta.

        - distance = radius * distance_factor
        - min/max_distance = radius * min_factor / max_factor
        - near/far proporcionais ao raio (importante para evitar clipping/z-fighting)

        Não muda o foco (origem) nem aplica flip.
        """
        r = float(radius)
        if not math.isfinite(r) or r <= 1e-8:
            return

        # raio base do sistema (mantém sua semântica "fator")
        self.fator = r

        # distância e limites
        self.distance = r * float(distance_factor)
        self.min_distance = r * float(min_factor)
        self.max_distance = r * float(max_factor)

        # garante coerência caso fatores venham errados
        if self.max_distance < self.min_distance:
            self.max_distance, self.min_distance = self.min_distance, self.max_distance

        # clipping plane escalado
        self.near = max(0.001, r * float(near_factor))
        self.far = max(self.near + 1.0, r * float(far_factor))

        # opcional: garantir que azimuth/elevation respeitam clamps existentes
        if clamp_current_angles:
            if self.elevation < self.min_elevation:
                self.elevation = self.min_elevation
            elif self.elevation > self.max_elevation:
                self.elevation = self.max_elevation

        # marca projeção suja e recalcula posição
        self._projection_dirty = True
        self._update_position()

    @staticmethod
    def estimate_radius_from_centers_map(centers_map: dict) -> float:
        """
        Estima o raio do planeta a partir de centers_map (tile -> glm.vec3 ou sequência xyz).
        Usa mediana para robustez.
        """
        if not centers_map:
            return 0.0

        rs: list[float] = []
        for c in centers_map.values():
            try:
                x, y, z = float(c.x), float(c.y), float(c.z)
            except Exception:
                try:
                    x, y, z = float(c[0]), float(c[1]), float(c[2])
                except Exception:
                    continue

            rr = math.sqrt(x * x + y * y + z * z)
            if rr > 1e-8 and math.isfinite(rr):
                rs.append(rr)

        if not rs:
            return 0.0

        rs.sort()
        return float(rs[len(rs) // 2])

    # ------------------------------------------------------------------

    def _update_position(self) -> None:
        ce = math.cos(self.elevation)
        se = math.sin(self.elevation)
        sa = math.sin(self.azimuth)
        ca = math.cos(self.azimuth)

        x = self.distance * ce * sa
        y = self.distance * se
        z = self.distance * ce * ca

        self.position[...] = (x, y, z)
        self.target[...] = (0.0, 0.0, 0.0)

        self.front = _normalize(self.target - self.position)
        self.right = _normalize(np.cross(self.front, self._world_up))
        self.up = _normalize(np.cross(self.right, self.front))

        self._view_dirty = True

    def orbit(self, delta_azimuth: float, delta_elevation: float) -> None:
        self.azimuth += float(delta_azimuth)
        self.elevation += float(delta_elevation)

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
        if hasattr(point_3d, "x"):
            x, y, z = float(point_3d.x), float(point_3d.y), float(point_3d.z)
        else:
            x, y, z = (float(point_3d[0]), float(point_3d[1]), float(point_3d[2]))

        norm = math.sqrt(x * x + y * y + z * z)
        if norm == 0.0:
            return

        dx, dy, dz = x / norm, y / norm, z / norm

        self.azimuth = math.atan2(dx, dz)
        self.elevation = math.asin(dy)

        if self.elevation < self.min_elevation:
            self.elevation = self.min_elevation
        elif self.elevation > self.max_elevation:
            self.elevation = self.max_elevation

        self._update_position()
