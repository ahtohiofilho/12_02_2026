# core/rendering/civ_flag.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import OpenGL.GL as gl
import glm
from PIL import Image


@dataclass(slots=True)
class FlagInstance:
    tile_coords: tuple[int, int]
    center: glm.vec3
    civ_name: str
    border_rgb: tuple[float, float, float]
    is_capital: bool


class CivFlag:
    def __init__(self):
        self.instances: list[FlagInstance] = []

        self.shader_program: int = 0
        self.vao: int | None = None
        self.vbo: int | None = None

        self.initialized: bool = False

        self.flag_textures: dict[str, int] = {}  # civ_name -> texture_id
        self.current_planet_id: str | None = None

        self.uniform_locations: dict[str, int] = {}

        self.vertex_shader_source = """
        #version 330 core
        layout(location = 0) in vec3 aPos;
        layout(location = 1) in vec2 aTexCoord;

        uniform mat4 uModel;
        uniform mat4 uView;
        uniform mat4 uProjection;

        out vec2 vTexCoord;

        void main() {
            gl_Position = uProjection * uView * uModel * vec4(aPos, 1.0);
            vTexCoord = aTexCoord;
        }
        """

        self.fragment_shader_source = """
        #version 330 core
        in vec2 vTexCoord;
        out vec4 FragColor;

        uniform sampler2D uTexture;
        uniform vec3 uBorderColor;
        uniform float uBorderWidth;

        void main() {
            vec4 texColor = texture(uTexture, vTexCoord);

            float borderDist = min(min(vTexCoord.x, 1.0 - vTexCoord.x),
                                   min(vTexCoord.y, 1.0 - vTexCoord.y));

            if (borderDist < uBorderWidth) {
                float t = borderDist / uBorderWidth;
                texColor.rgb = mix(uBorderColor, texColor.rgb, t);
            }

            if (texColor.a < 0.1) discard;
            FragColor = texColor;
        }
        """

    # ---------- Data ----------
    def set_civilization_data(self, planet, centers_3d_tiles: dict[tuple[int, int], glm.vec3]) -> None:
        """
        Cria instâncias de bandeira a partir das civilizações do planeta.
        - Você pode decidir: capital only, ou todas províncias.
        Aqui vou colocar capital + (opcional) outras províncias.
        """
        self.instances.clear()
        if planet is None:
            return

        planet_id = getattr(planet, "id", "default")

        # Se mudou planeta, limpa texturas para evitar vazamento e inconsistência
        if planet_id != self.current_planet_id:
            self._clear_flag_textures()
            self.current_planet_id = planet_id

        civs = getattr(planet, "civilizations", None)
        if not civs:
            return

        for civ in civs:
            civ_name = civ.name
            civ_color = civ.color  # (r,g,b) 0..255
            border_rgb = (civ_color[0] / 255.0, civ_color[1] / 255.0, civ_color[2] / 255.0)

            # garante textura no cache (carrega lazy)
            if civ_name not in self.flag_textures:
                self.flag_textures[civ_name] = self._load_flag_texture(civ_name, planet_id)

            # --- escolha do que renderizar ---
            # 1) capital
            cap = civ.capital_coords
            center = centers_3d_tiles.get(cap)
            if center is not None:
                self.instances.append(
                    FlagInstance(tile_coords=cap, center=center, civ_name=civ_name, border_rgb=border_rgb, is_capital=True)
                )

            # 2) (opcional) outras províncias
            # se quiser só capital, comente este bloco
            for prov in civ.provinces:
                if prov.is_capital:
                    continue
                c = centers_3d_tiles.get(prov.tile_coords)
                if c is None:
                    continue
                self.instances.append(
                    FlagInstance(tile_coords=prov.tile_coords, center=c, civ_name=civ_name, border_rgb=border_rgb, is_capital=False)
                )

    # ---------- GL init ----------
    def init_gl(self) -> bool:
        if self.initialized:
            return True

        vs = self._compile_shader(self.vertex_shader_source, gl.GL_VERTEX_SHADER)
        fs = self._compile_shader(self.fragment_shader_source, gl.GL_FRAGMENT_SHADER)
        if vs == 0 or fs == 0:
            return False

        self.shader_program = gl.glCreateProgram()
        gl.glAttachShader(self.shader_program, vs)
        gl.glAttachShader(self.shader_program, fs)
        gl.glLinkProgram(self.shader_program)

        ok = gl.glGetProgramiv(self.shader_program, gl.GL_LINK_STATUS)
        if not ok:
            info = gl.glGetProgramInfoLog(self.shader_program)
            print(f"❌ [CivFlag] Erro link shader: {info}")
            gl.glDeleteProgram(self.shader_program)
            self.shader_program = 0
            return False

        gl.glDeleteShader(vs)
        gl.glDeleteShader(fs)

        self.uniform_locations = {
            "uModel": gl.glGetUniformLocation(self.shader_program, "uModel"),
            "uView": gl.glGetUniformLocation(self.shader_program, "uView"),
            "uProjection": gl.glGetUniformLocation(self.shader_program, "uProjection"),
            "uTexture": gl.glGetUniformLocation(self.shader_program, "uTexture"),
            "uBorderColor": gl.glGetUniformLocation(self.shader_program, "uBorderColor"),
            "uBorderWidth": gl.glGetUniformLocation(self.shader_program, "uBorderWidth"),
        }

        # Geometria do quad (pos + uv) — UV com U invertido (igual seu fix antigo)
        aspect = 144.0 / 89.0
        half_w = 0.5 * aspect
        half_h = 0.5

        vertices = np.array(
            [
                -half_w, -half_h, 0.0, 0.0, 0.0,
                half_w, -half_h, 0.0, 1.0, 0.0,
                half_w, half_h, 0.0, 1.0, 1.0,
                -half_w, half_h, 0.0, 0.0, 1.0,
            ],
            dtype=np.float32,
        )

        self.vao = gl.glGenVertexArrays(1)
        self.vbo = gl.glGenBuffers(1)

        gl.glBindVertexArray(self.vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, vertices.nbytes, vertices, gl.GL_STATIC_DRAW)

        stride = 5 * 4
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, None)

        gl.glEnableVertexAttribArray(1)
        gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, gl.ctypes.c_void_p(12))

        gl.glBindVertexArray(0)

        self.initialized = True
        return True

    def render(self, view_matrix, projection_matrix) -> None:
        if not self.initialized or self.shader_program == 0:
            return
        if not self.instances:
            return

        # Transparência (bandeira PNG)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glDepthMask(gl.GL_FALSE)

        gl.glUseProgram(self.shader_program)
        gl.glBindVertexArray(self.vao)

        gl.glUniformMatrix4fv(self.uniform_locations["uView"], 1, gl.GL_FALSE, view_matrix.T)
        gl.glUniformMatrix4fv(self.uniform_locations["uProjection"], 1, gl.GL_FALSE, projection_matrix.T)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glUniform1i(self.uniform_locations["uTexture"], 0)
        gl.glUniform1f(self.uniform_locations["uBorderWidth"], 0.02)

        base_scale = 0.08
        capital_scale = 0.10
        offset = 0.02

        current_tex = None

        for inst in self.instances:
            tex = self.flag_textures.get(inst.civ_name, 0)
            if not tex:
                continue

            if tex != current_tex:
                gl.glBindTexture(gl.GL_TEXTURE_2D, int(tex))
                current_tex = tex

            gl.glUniform3f(self.uniform_locations["uBorderColor"], *inst.border_rgb)

            # Seu render aplica flip no X (mundo espelhado). Mantemos igual ao CivIcon antigo:
            x, y, z = inst.center.x, inst.center.y, inst.center.z
            position = glm.vec3(x, y, z)

            normal = glm.normalize(position)
            position = position + normal * offset

            # Orientar topo da bandeira para o norte “na superfície”
            north_pole = glm.vec3(0, 1, 0)
            north_on_surface = north_pole - glm.dot(north_pole, normal) * normal
            if glm.length(north_on_surface) < 0.001:
                north_on_surface = glm.vec3(1, 0, 0)

            up = -glm.normalize(north_on_surface)
            right = glm.normalize(glm.cross(normal, up))

            scale = capital_scale if inst.is_capital else base_scale

            rotation = glm.mat4(
                glm.vec4(right * scale, 0),
                glm.vec4(up * scale, 0),
                glm.vec4(normal, 0),
                glm.vec4(0, 0, 0, 1),
            )

            model = glm.translate(glm.mat4(1.0), position) * rotation

            gl.glUniformMatrix4fv(self.uniform_locations["uModel"], 1, gl.GL_FALSE, glm.value_ptr(model))
            gl.glDrawArrays(gl.GL_TRIANGLE_FAN, 0, 4)

        gl.glBindVertexArray(0)
        gl.glUseProgram(0)

        gl.glDepthMask(gl.GL_TRUE)
        gl.glEnable(gl.GL_CULL_FACE)
        gl.glDisable(gl.GL_BLEND)

    # ---------- Texture IO ----------
    def _get_flag_path(self, civ_name: str, planet_id: str) -> Path:
        return Path("assets") / "worlds" / planet_id / "flags" / f"{civ_name}.png"

    def _load_flag_texture(self, civ_name: str, planet_id: str) -> int:
        path = self._get_flag_path(civ_name, planet_id)
        if not path.exists():
            print(f"⚠️ [CivFlag] Bandeira não encontrada: {path}")
            return 0

        try:
            img = Image.open(path).convert("RGBA")
            img_data = np.array(img, dtype=np.uint8)

            tex = gl.glGenTextures(1)
            gl.glBindTexture(gl.GL_TEXTURE_2D, tex)

            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)

            gl.glTexImage2D(
                gl.GL_TEXTURE_2D, 0, gl.GL_RGBA,
                img.width, img.height, 0,
                gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, img_data
            )
            return tex
        except Exception as e:
            print(f"❌ [CivFlag] Erro ao carregar bandeira {civ_name}: {e}")
            return 0

    def _clear_flag_textures(self) -> None:
        for tex in self.flag_textures.values():
            if tex:
                gl.glDeleteTextures(1, [tex])
        self.flag_textures.clear()

    # ---------- Shader helpers / cleanup ----------
    def _compile_shader(self, source: str, shader_type) -> int:
        sh = gl.glCreateShader(shader_type)
        if sh == 0:
            return 0
        gl.glShaderSource(sh, source)
        gl.glCompileShader(sh)
        ok = gl.glGetShaderiv(sh, gl.GL_COMPILE_STATUS)
        if not ok:
            info = gl.glGetShaderInfoLog(sh).decode()
            print(f"❌ [CivFlag] Shader compile error:\n{info}")
            gl.glDeleteShader(sh)
            return 0
        return sh

    def cleanup_gl(self) -> None:
        if self.vao:
            gl.glDeleteVertexArrays(1, [self.vao])
            self.vao = None
        if self.vbo:
            gl.glDeleteBuffers(1, [self.vbo])
            self.vbo = None
        if self.shader_program:
            gl.glDeleteProgram(self.shader_program)
            self.shader_program = 0

        self._clear_flag_textures()
        self.instances.clear()
        self.initialized = False
