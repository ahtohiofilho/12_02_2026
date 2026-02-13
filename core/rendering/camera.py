import math
import numpy as np
import glm


# Função utilitária que estava sendo usada no seu código
def normalize(v):
    norm = np.linalg.norm(v)
    if norm == 0:
        return v
    return v / norm


class Camera:
    def __init__(self, distance=5.0):
        """
        Câmera orbital sempre focada na origem (0,0,0)
        """
        # Parâmetros orbitais
        self.fator = distance
        self.distance = distance  # Distância da origem
        self.azimuth = math.radians(45.0)  # Começar com um ângulo para não ver de frente
        self.elevation = math.radians(30.0)  # E um pouco de cima
        self.selected_tile_position = None

        # Limites de segurança
        self.min_distance = self.fator / 2
        self.max_distance = self.fator * 2
        self.min_elevation = -math.pi / 2 + 0.1  # Quase -90°
        self.max_elevation = math.pi / 2 - 0.1  # Quase +90°

        # Parâmetros de projeção
        self.fov = 45.0
        self.aspect_ratio = 1.0
        self.near = 0.1
        self.far = 100.0

        # Cache e flag de sujeira
        self._projection_matrix = None
        self._projection_dirty = True
        self._view_matrix = None
        self._view_dirty = True

        self.target = np.array([0.0, 0.0, 0.0])

        # Calcula posição inicial
        self._update_position()

    def _update_position(self):
        """Atualiza a posição da câmera e marca view matrix como suja"""
        x = self.distance * math.cos(self.elevation) * math.sin(self.azimuth)
        y = self.distance * math.sin(self.elevation)
        z = self.distance * math.cos(self.elevation) * math.cos(self.azimuth)

        self.position = np.array([x, y, z])
        self.target = np.array([0.0, 0.0, 0.0])

        # Vetores da câmera
        self.front = normalize(self.target - self.position)
        # Ordem corrigida para sistema de coordenadas destro (padrão OpenGL)
        self.right = normalize(np.cross(self.front, np.array([0.0, 1.0, 0.0])))
        self.up = normalize(np.cross(self.right, self.front))

        # Marca view matrix como suja
        self._view_dirty = True

    def orbit(self, delta_azimuth, delta_elevation):
        """Rotaciona a câmera ao redor da origem"""
        self.azimuth += delta_azimuth
        self.elevation += delta_elevation

        # Limita elevação para evitar flip
        self.elevation = max(self.min_elevation, min(self.elevation, self.max_elevation))

        self._update_position()

    def zoom(self, delta):
        """Aproxima/afasta a câmera da origem"""
        self.distance += delta
        self.distance = max(self.min_distance, min(self.distance, self.max_distance))
        self._update_position()

    def get_view_matrix(self):
        if self._view_dirty or self._view_matrix is None:
            view = glm.lookAt(
                glm.vec3(self.position),
                glm.vec3(0, 0, 0),
                glm.vec3(self.up)
            )
            self._view_matrix = np.array(view)
            self._view_dirty = False
        return self._view_matrix

    def _calculate_view_matrix_lookat(self):
        """Cálculo de matriz de view usando uma abordagem 'lookAt' manual"""
        z_axis = normalize(self.position - self.target)
        x_axis = normalize(np.cross(np.array([0.0, 1.0, 0.0]), z_axis))
        y_axis = np.cross(z_axis, x_axis)

        translation = np.identity(4)
        translation[3, 0] = -self.position[0]
        translation[3, 1] = -self.position[1]
        translation[3, 2] = -self.position[2]

        rotation = np.identity(4)
        rotation[0, 0:3] = x_axis
        rotation[1, 0:3] = y_axis
        rotation[2, 0:3] = z_axis

        # A ordem correta é Rotação * Translação
        return rotation @ translation

    def get_projection_matrix(self):
        if self._projection_dirty or self._projection_matrix is None:
            proj = glm.perspective(
                glm.radians(self.fov),
                self.aspect_ratio,
                self.near,
                self.far
            )
            self._projection_matrix = np.array(proj)  # sem .T (pela regra acima)
            self._projection_dirty = False
        return self._projection_matrix

    def _calculate_projection_matrix(self):
        """Cálculo real da matriz de projeção"""
        f = 1.0 / math.tan(math.radians(self.fov) / 2.0)

        # Matriz de projeção em perspectiva (row-major)
        return np.array([
            [f / self.aspect_ratio, 0, 0, 0],
            [0, f, 0, 0],
            [0, 0, (self.far + self.near) / (self.near - self.far), -1],
            [0, 0, (2 * self.far * self.near) / (self.near - self.far), 0]
        ])

    def set_aspect_ratio(self, width, height):
        """Define o aspect ratio e marca a matriz de projeção como suja"""
        new_aspect = width / height if height > 0 else 1.0
        if abs(new_aspect - self.aspect_ratio) > 1e-6:
            self.aspect_ratio = new_aspect
            self._projection_dirty = True

    def look_at_tile(self, point_3d):
        """Reorienta a câmera para focar em um tile específico MANTENDO FOCO NA ORIGEM"""
        if hasattr(point_3d, 'x'):
            tile_pos = np.array([point_3d.x, point_3d.y, point_3d.z])
        else:
            tile_pos = np.array(point_3d)

        # CORREÇÃO: Inverter o eixo X para corresponder à renderização
        # A renderização usa: model_matrix = glm.scale(model_matrix, glm.vec3(-1.0, 1.0, 1.0))
        corrected_tile_pos = np.array([-tile_pos[0], tile_pos[1], tile_pos[2]])

        print(f"[Camera.look_at_tile] Posição original do tile: {tile_pos}")
        print(f"[Camera.look_at_tile] Posição corrigida (X invertido): {corrected_tile_pos}")

        # Normaliza para obter direção na esfera unitária
        direction_to_tile = corrected_tile_pos / np.linalg.norm(corrected_tile_pos)

        # Calcula novos ângulos orbitais
        self.azimuth = math.atan2(direction_to_tile[0], direction_to_tile[2])
        self.elevation = math.asin(direction_to_tile[1])

        # Limita a elevação
        self.elevation = max(self.min_elevation, min(self.elevation, self.max_elevation))

        self._update_position()
