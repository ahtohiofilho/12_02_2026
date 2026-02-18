# core/rendering/route_overlay.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import math
import numpy as np
import OpenGL.GL as gl


Tile = tuple[int, int]


def _slerp(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    dot = float(np.clip(np.dot(a, b), -1.0, 1.0))
    omega = math.acos(dot)
    if omega < 1e-6:
        return a
    so = math.sin(omega)
    return (math.sin((1.0 - t) * omega) / so) * a + (math.sin(t * omega) / so) * b


def path_tiles_to_points(
    centers_3d_tiles: dict[Tile, object],
    path_tiles: Optional[Sequence[Tile]],
    *,
    lift: float = 0.004,
    steps_per_segment: int = 8,
    flip_x: bool = True,
) -> Optional[np.ndarray]:
    """
    Converte tiles (x,y) em uma polyline 3D sobre a esfera usando SLERP entre centros.
    centers_3d_tiles[tile] precisa ter atributos x,y,z (glm.vec3 serve).
    """
    if not path_tiles:
        return None

    centers: list[np.ndarray] = []
    for tile in path_tiles:
        if isinstance(tile, list):
            tile = (tile[0], tile[1])
        c = centers_3d_tiles.get(tile)
        if c is None:
            continue
        x = -c.x if flip_x else c.x
        centers.append(np.array([x, c.y, c.z], dtype=np.float32))

    if len(centers) < 2:
        return None

    pts: list[np.ndarray] = []
    k = max(1, int(steps_per_segment))

    for i in range(len(centers) - 1):
        p0 = centers[i]
        p1 = centers[i + 1]

        r0 = float(np.linalg.norm(p0))
        r1 = float(np.linalg.norm(p1))
        if r0 < 1e-8 or r1 < 1e-8:
            continue

        r = 0.5 * (r0 + r1)
        a = p0 / r0
        b = p1 / r1

        if i == 0:
            pts.append((a * (r + lift)).astype(np.float32))

        for j in range(1, k + 1):
            tt = j / k
            n = _slerp(a, b, tt)
            pts.append((n * (r + lift)).astype(np.float32))

    if len(pts) < 2:
        return None
    return np.vstack(pts)


@dataclass
class RouteOverlayState:
    path_tiles: Optional[list[Tile]] = None
    dirty: bool = True

    def set_path(self, path_tiles: Optional[Sequence[Tile]]) -> None:
        self.path_tiles = list(path_tiles) if path_tiles else None
        self.dirty = True


class RouteOverlayRenderer:
    def __init__(self) -> None:
        self.state = RouteOverlayState()

        self.initialized: bool = False
        self.shader_program: int = 0
        self.vao: int | None = None
        self.vbo: int | None = None
        self.vertex_count: int = 0

        self.uView = -1
        self.uProj = -1
        self.uColor = -1

        self._pts_cached: Optional[np.ndarray] = None

        self.vs = """
        #version 330 core
        layout (location = 0) in vec3 aPos;
        uniform mat4 uView;
        uniform mat4 uProjection;
        void main() {
            gl_Position = uProjection * uView * vec4(aPos, 1.0);
        }
        """

        self.fs = """
        #version 330 core
        out vec4 FragColor;
        uniform vec4 uColor;
        void main() {
            FragColor = uColor;
        }
        """

    def _compile(self, src: str, stype: int) -> int:
        sh = gl.glCreateShader(stype)
        gl.glShaderSource(sh, src)
        gl.glCompileShader(sh)
        ok = gl.glGetShaderiv(sh, gl.GL_COMPILE_STATUS)
        if not ok:
            log = gl.glGetShaderInfoLog(sh).decode(errors="replace")
            print(f"❌ [RouteOverlay] Shader compile error:\n{log}")
            gl.glDeleteShader(sh)
            return 0
        return sh

    def init_gl(self) -> bool:
        if self.initialized:
            return True

        vs = self._compile(self.vs, gl.GL_VERTEX_SHADER)
        fs = self._compile(self.fs, gl.GL_FRAGMENT_SHADER)
        if vs == 0 or fs == 0:
            return False

        prog = gl.glCreateProgram()
        gl.glAttachShader(prog, vs)
        gl.glAttachShader(prog, fs)
        gl.glLinkProgram(prog)

        gl.glDeleteShader(vs)
        gl.glDeleteShader(fs)

        ok = gl.glGetProgramiv(prog, gl.GL_LINK_STATUS)
        if not ok:
            log = gl.glGetProgramInfoLog(prog).decode(errors="replace")
            print(f"❌ [RouteOverlay] Program link error:\n{log}")
            gl.glDeleteProgram(prog)
            return False

        self.shader_program = prog
        self.uView = gl.glGetUniformLocation(self.shader_program, "uView")
        self.uProj = gl.glGetUniformLocation(self.shader_program, "uProjection")
        self.uColor = gl.glGetUniformLocation(self.shader_program, "uColor")

        self.vao = gl.glGenVertexArrays(1)
        self.vbo = gl.glGenBuffers(1)

        gl.glBindVertexArray(self.vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, 0, None, gl.GL_DYNAMIC_DRAW)

        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, None)
        gl.glEnableVertexAttribArray(0)

        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
        gl.glBindVertexArray(0)

        self.initialized = True
        return True

    def set_points(self, pts_xyz: Optional[np.ndarray]) -> None:
        if pts_xyz is None or len(pts_xyz) < 2:
            self.vertex_count = 0
            self._pts_cached = None
            return

        pts_xyz = np.asarray(pts_xyz, dtype=np.float32)
        if pts_xyz.ndim != 2 or pts_xyz.shape[1] != 3:
            raise ValueError(f"pts_xyz must be Nx3 float32, got shape={pts_xyz.shape}")

        self.vertex_count = int(pts_xyz.shape[0])
        self._pts_cached = pts_xyz

        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, pts_xyz.nbytes, pts_xyz, gl.GL_DYNAMIC_DRAW)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)

    def update_if_dirty(
        self,
        centers_3d_tiles: dict[Tile, object],
        *,
        lift: float = 0.004,
        steps_per_segment: int = 8,
        flip_x: bool = True,
    ) -> None:
        """
        Recalcula e sobe VBO se state.dirty=True.
        Deve ser chamado com contexto GL corrente (porque chama set_points()).
        """
        if not self.state.dirty:
            return

        pts = path_tiles_to_points(
            centers_3d_tiles,
            self.state.path_tiles,
            lift=lift,
            steps_per_segment=steps_per_segment,
            flip_x=flip_x,
        )
        self.set_points(pts)
        self.state.dirty = False

    def render(
        self,
        view_matrix,
        projection_matrix,
        *,
        color=(0.1, 0.9, 1.0, 1.0),
        width: float = 3.0,
        depth_test: bool = True,
    ) -> None:
        if not self.initialized or self.shader_program == 0 or self.vertex_count < 2:
            return

        if depth_test:
            gl.glEnable(gl.GL_DEPTH_TEST)
        else:
            gl.glDisable(gl.GL_DEPTH_TEST)

        gl.glUseProgram(self.shader_program)
        gl.glBindVertexArray(self.vao)

        # matrizes como np.ndarray 4x4 (se você estiver usando glm, converta antes)
        gl.glUniformMatrix4fv(self.uView, 1, gl.GL_FALSE, view_matrix.T)
        gl.glUniformMatrix4fv(self.uProj, 1, gl.GL_FALSE, projection_matrix.T)
        gl.glUniform4f(self.uColor, *color)

        gl.glLineWidth(width)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glDrawArrays(gl.GL_LINE_STRIP, 0, self.vertex_count)
        gl.glEnable(gl.GL_CULL_FACE)

        gl.glBindVertexArray(0)
        gl.glUseProgram(0)
