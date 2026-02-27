# core/rendering/planet_renderer.py
from __future__ import annotations

import numpy as np
import OpenGL.GL as gl
import glm

from core.rendering.civ_flag import CivFlag
from core.rendering.route_overlay import RouteOverlayRenderer
from core.rendering.color_picker import TileColorPicker
from core.rendering.tile_units_renderer import TileUnitsRenderer


class PlanetRenderer:
    """
    Renderer do planeta com FoW via textura 1D (uVisibilityTexture).

    ✅ Consolidação "à prova de timing":
    - Se Controller chamar update_fow() antes do OpenGL estar inicializado,
      a atualização é armazenada em _pending_fow e aplicada assim que a
      visibility_texture for criada em init_gl().
    """

    def __init__(self, controller):
        print(f"🔴 PlanetRenderer.__init__ chamado! ID: {id(self)}")
        self.vao = None
        self.vbo_vertices = None
        self.vbo_tile_indices = None
        self.ebo_indices = None
        self.index_count = 0
        self.shader_program = 0

        self.tile_coords_to_index: dict[tuple[int, int], int] = {}
        self.tile_colors = {}
        self.all_vertices = np.array([])
        self.all_indices = np.array([], dtype=np.uint32)
        self.all_tile_indices = np.array([], dtype=np.uint32)

        self.initializado = False
        self.dados_atualizados = False

        self.civ_flag_renderer = CivFlag()
        self.controller = controller
        self.route_renderer = RouteOverlayRenderer()
        self.color_picker = TileColorPicker(self)

        # Renderer unificado de unidades (militares + trabalhadores)
        self.tile_units_renderer = TileUnitsRenderer()

        # Recursos para highlight
        self.highlight_shader_program = 0
        self.highlight_initialized = False
        self._highlight_cache = {
            "tile_coords": None,
            "vao": None,
            "vbo": None,
            "vertex_count": 0,
        }
        self.tile_vertex_range = {}

        # ----------------------------
        # FoW timing-safe (NOVO)
        # ----------------------------
        self.visibility_texture = None
        self._pending_fow: tuple[set, set] | None = None  # (explored_tiles, visible_tiles)

        # Shader principal do planeta
        self.vertex_shader_source = """
        #version 330 core
        layout (location = 0) in vec3 aPos;
        layout (location = 1) in uint aTileIndex;

        uniform mat4 uModel;
        uniform mat4 uView;
        uniform mat4 uProjection;

        flat out uint tileIndex;

        void main()
        {
            gl_Position = uProjection * uView * uModel * vec4(aPos, 1.0);
            tileIndex = aTileIndex;
        }
        """

        self.fragment_shader_source = """
        #version 330 core
        out vec4 FragColor;

        uniform sampler1D uTileColorTexture;
        uniform sampler1D uVisibilityTexture; // Textura de visão
        uniform int uNumTiles;

        flat in uint tileIndex;

        void main()
        {
            if (int(tileIndex) >= uNumTiles || int(tileIndex) < 0) {
                FragColor = vec4(1.0, 0.0, 0.0, 1.0);
                return;
            }

            float texCoord = (float(tileIndex) + 0.5) / float(uNumTiles);
            vec3 baseColor = texture(uTileColorTexture, texCoord).rgb;
            float vis = texture(uVisibilityTexture, texCoord).r;

            if (vis < 0.1) {
                // INEXPLORADO: Preto/Cinza muito escuro
                FragColor = vec4(0.05, 0.05, 0.07, 1.0);
            } else if (vis < 0.6) {
                // NEBLINA (FOG): Explorado, mas sem visão
                FragColor = vec4(baseColor * 0.35, 1.0);
            } else {
                // VISÍVEL: Cor normal
                FragColor = vec4(baseColor, 1.0);
            }
        }
        """

        # Shaders para highlight
        self.highlight_vertex_shader_source = """
        #version 330 core
        layout (location = 0) in vec3 aPos;

        uniform mat4 uModel;
        uniform mat4 uView;
        uniform mat4 uProjection;

        void main()
        {
            vec3 pos = aPos * 1.003; // evita z-fighting
            gl_Position = uProjection * uView * uModel * vec4(pos, 1.0);
        }
        """

        self.highlight_fragment_shader_source = """
        #version 330 core
        out vec4 FragColor;

        uniform vec4 uHighlightColor;

        void main()
        {
            FragColor = uHighlightColor;
        }
        """

    def set_controller(self, controller):
        """Define a referência ao controller"""
        self.controller = controller
        print(f"[PlanetRenderer] Controller referenciado: {controller is not None}")

    def set_tile_data(self, coord_vert, centros_3d_tiles):
        self.coord_vert = coord_vert
        self.centros_3d_tiles = centros_3d_tiles

        all_vertices_list = []
        all_indices_list = []
        all_tile_indices_list = []
        current_global_index = 0

        self.tile_vertex_range = {}
        sorted_coords = sorted(coord_vert.keys())
        self.tile_coords_to_index = {coords: idx for idx, coords in enumerate(sorted_coords)}

        for coords in sorted_coords:
            vertices_np = coord_vert.get(coords)
            if vertices_np is None or (hasattr(vertices_np, "size") and vertices_np.size == 0):
                continue

            current_tile_index = self.tile_coords_to_index[coords]
            num_vertices = len(vertices_np)
            if num_vertices < 3:
                continue

            start_index = current_global_index
            self.tile_vertex_range[current_tile_index] = (start_index, num_vertices)

            for vertex in vertices_np:
                all_vertices_list.append(vertex)
                all_tile_indices_list.append(current_tile_index)
                current_global_index += 1

            for i in range(1, num_vertices - 1):
                all_indices_list.extend([start_index, start_index + i, start_index + i + 1])

        self.all_vertices = np.array(all_vertices_list, dtype=np.float32).reshape(-1).astype(np.float32, copy=False)
        self.all_indices = np.array(all_indices_list, dtype=np.uint32)
        self.all_tile_indices = np.array(all_tile_indices_list, dtype=np.uint32)
        self.index_count = int(self.all_indices.size)

        # Mudou geometria/indices -> precisa reinicializar GL
        self.dados_atualizados = True
        self.initializado = False
        return True

    def set_civilization_data(self, planeta):
        if hasattr(self, "centros_3d_tiles") and self.centros_3d_tiles:
            self.civ_flag_renderer.set_civilization_data(planeta, self.centros_3d_tiles)

    def set_tile_colors(self, tile_colors_dict):
        self.tile_colors = tile_colors_dict
        num_tiles = len(self.tile_coords_to_index)

        if num_tiles == 0:
            print("[PlanetRenderer] Aviso: Nenhum tile para definir cores.")
            return

        sorted_colors = []
        for coords in sorted(self.tile_coords_to_index.keys()):
            color = tile_colors_dict.get(coords, [127.0, 127.0, 127.0])
            color_normalized = [c / 255.0 for c in color]
            sorted_colors.extend(color_normalized)

        color_array = np.array(sorted_colors, dtype=np.float32).reshape((num_tiles, 3))
        self.tile_color_texture_data = color_array

    def needs_init(self):
        if len(self.all_vertices) == 0:
            return False
        return (not self.initializado) or self.dados_atualizados

    def init_gl(self):
        print("\n" + "=" * 50)
        print(f"🔧 PlanetRenderer.init_gl INICIADO (ID: {id(self)})")
        self.initializado = False

        if len(self.all_vertices) == 0 or len(self.all_indices) == 0:
            print("❌ ERRO CRÍTICO: all_vertices ou all_indices VAZIO!")
            return False

        try:
            self.cleanup_gl()

            # Shaders
            vertex_shader = self.compile_shader(self.vertex_shader_source, gl.GL_VERTEX_SHADER)
            fragment_shader = self.compile_shader(self.fragment_shader_source, gl.GL_FRAGMENT_SHADER)
            if vertex_shader == 0 or fragment_shader == 0:
                return False

            self.shader_program = gl.glCreateProgram()
            gl.glAttachShader(self.shader_program, vertex_shader)
            gl.glAttachShader(self.shader_program, fragment_shader)
            gl.glLinkProgram(self.shader_program)

            if not gl.glGetProgramiv(self.shader_program, gl.GL_LINK_STATUS):
                gl.glDeleteProgram(self.shader_program)
                self.shader_program = 0
                return False

            gl.glDeleteShader(vertex_shader)
            gl.glDeleteShader(fragment_shader)

            self.uniform_locations = {
                "uView": gl.glGetUniformLocation(self.shader_program, "uView"),
                "uProjection": gl.glGetUniformLocation(self.shader_program, "uProjection"),
                "uModel": gl.glGetUniformLocation(self.shader_program, "uModel"),
                "uNumTiles": gl.glGetUniformLocation(self.shader_program, "uNumTiles"),
                "uTileColorTexture": gl.glGetUniformLocation(self.shader_program, "uTileColorTexture"),
                "uVisibilityTexture": gl.glGetUniformLocation(self.shader_program, "uVisibilityTexture"),
            }

            # VAO e Buffers
            self.vao = gl.glGenVertexArrays(1)
            gl.glBindVertexArray(self.vao)

            self.vbo_vertices = gl.glGenBuffers(1)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_vertices)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, self.all_vertices.nbytes, self.all_vertices, gl.GL_STATIC_DRAW)
            gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, None)
            gl.glEnableVertexAttribArray(0)

            self.vbo_tile_indices = gl.glGenBuffers(1)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_tile_indices)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, self.all_tile_indices.nbytes, self.all_tile_indices, gl.GL_STATIC_DRAW)
            gl.glVertexAttribIPointer(1, 1, gl.GL_UNSIGNED_INT, 0, None)
            gl.glEnableVertexAttribArray(1)

            self.ebo_indices = gl.glGenBuffers(1)
            gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.ebo_indices)
            gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, self.all_indices.nbytes, self.all_indices, gl.GL_STATIC_DRAW)
            gl.glBindVertexArray(0)

            # ----------------------------
            # Textura 1D - Cores
            # ----------------------------
            self.tile_color_texture = gl.glGenTextures(1)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_1D, self.tile_color_texture)
            gl.glTexParameteri(gl.GL_TEXTURE_1D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
            gl.glTexParameteri(gl.GL_TEXTURE_1D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
            gl.glTexParameteri(gl.GL_TEXTURE_1D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)

            if hasattr(self, "tile_color_texture_data") and self.tile_color_texture_data is not None:
                num_colors = int(self.tile_color_texture_data.shape[0])
                gl.glTexImage1D(
                    gl.GL_TEXTURE_1D, 0, gl.GL_RGB32F,
                    num_colors, 0, gl.GL_RGB, gl.GL_FLOAT, self.tile_color_texture_data
                )
            else:
                dummy_color = np.array([0.5, 0.5, 0.5], dtype=np.float32)
                gl.glTexImage1D(gl.GL_TEXTURE_1D, 0, gl.GL_RGB32F, 1, 0, gl.GL_RGB, gl.GL_FLOAT, dummy_color)

            # ----------------------------
            # Textura 1D - Visibilidade (FoW)
            # ----------------------------
            self.visibility_texture = gl.glGenTextures(1)
            gl.glActiveTexture(gl.GL_TEXTURE1)
            gl.glBindTexture(gl.GL_TEXTURE_1D, self.visibility_texture)
            gl.glTexParameteri(gl.GL_TEXTURE_1D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
            gl.glTexParameteri(gl.GL_TEXTURE_1D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
            gl.glTexParameteri(gl.GL_TEXTURE_1D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)

            num_tiles_vis = len(self.tile_coords_to_index) if len(self.tile_coords_to_index) > 0 else 1
            default_vis = np.zeros(num_tiles_vis, dtype=np.float32)  # modo jogo: começa tudo inexplorado

            gl.glTexImage1D(
                gl.GL_TEXTURE_1D, 0, gl.GL_R32F,
                num_tiles_vis, 0, gl.GL_RED, gl.GL_FLOAT, default_vis
            )

            self._init_highlight_shader()

            # Sub-renderers
            if self.civ_flag_renderer:
                try:
                    self.civ_flag_renderer.init_gl()
                except Exception:
                    pass

            if self.route_renderer:
                try:
                    self.route_renderer.init_gl()
                except Exception:
                    pass

            if self.tile_units_renderer:
                try:
                    self.tile_units_renderer.init_gl()
                except Exception:
                    pass

            if self.color_picker:
                try:
                    self.color_picker.init_gl()
                except Exception:
                    pass

            self.initializado = True
            self.dados_atualizados = False
            print("✅ PlanetRenderer.init_gl concluído com sucesso")

            # ✅ Aplicar FoW pendente (timing-safe)
            self._apply_pending_fow_if_any()

            # ✅ Força um repaint imediato após FoW/texturas estarem prontas
            # (evita o primeiro frame "preto demais" até o usuário mexer na câmera)
            try:
                if self.controller and getattr(self.controller, "scene", None):
                    self.controller.scene.update()
            except Exception:
                pass

            return True

        except Exception as e:
            print(f"💥 ERRO CRÍTICO durante init_gl: {e}")
            self.cleanup_gl()
            self.dados_atualizados = True
            return False

    def update_visibility_texture(self, explored_tiles: set, visible_tiles: set) -> None:
        """
        Atualiza a textura de FoW na GPU com os dados mais recentes.

        Timing-safe:
        - Se o renderer ainda não tem mapeamento/texture (init_gl não rodou), guarda em _pending_fow.
        """
        explored_tiles = set(explored_tiles or ())
        visible_tiles = set(visible_tiles or ())

        # ✅ Repasse do FoW para o renderer de bandeiras (para filtrar instâncias)
        if getattr(self, "civ_flag_renderer", None) is not None:
            try:
                self.civ_flag_renderer.set_fow(explored_tiles, visible_tiles)

                # ✅ IMPORTANTE: as instâncias de bandeiras são "cacheadas".
                # Recria instâncias agora para aplicar o filtro de FoW.
                if hasattr(self.civ_flag_renderer, "refresh_instances"):
                    self.civ_flag_renderer.refresh_instances()
            except Exception:
                pass

        # Se ainda não temos o mapeamento (coords -> índice), não dá pra montar o array
        if not getattr(self, "tile_coords_to_index", None):
            self._pending_fow = (set(explored_tiles), set(visible_tiles))
            return

        # Se a textura ainda não existe, guarda para aplicar quando existir
        tex = getattr(self, "visibility_texture", None)
        if not tex:
            self._pending_fow = (set(explored_tiles), set(visible_tiles))
            return

        num_tiles = len(self.tile_coords_to_index)
        vis_array = np.zeros(num_tiles, dtype=np.float32)

        # Preenche: 1.0 visível, 0.5 explorado, 0.0 desconhecido
        for coords, idx in self.tile_coords_to_index.items():
            if coords in visible_tiles:
                vis_array[idx] = 1.0
            elif coords in explored_tiles:
                vis_array[idx] = 0.5

        gl.glActiveTexture(gl.GL_TEXTURE1)
        gl.glBindTexture(gl.GL_TEXTURE_1D, tex)
        gl.glTexSubImage1D(
            gl.GL_TEXTURE_1D,
            0,
            0,
            num_tiles,
            gl.GL_RED,
            gl.GL_FLOAT,
            vis_array,
        )

    def _apply_pending_fow_if_any(self) -> None:
        """
        Aplica a última atualização de FoW que tenha sido chamada antes do init_gl().
        """
        pending = getattr(self, "_pending_fow", None)
        if not pending:
            return
        explored_tiles, visible_tiles = pending
        self._pending_fow = None
        try:
            self.update_visibility_texture(explored_tiles, visible_tiles)
        except Exception:
            # Se der erro (ex.: contexto não pronto por algum motivo), deixa o default.
            pass

    def _init_highlight_shader(self):
        try:
            vertex_shader = self.compile_shader(self.highlight_vertex_shader_source, gl.GL_VERTEX_SHADER)
            fragment_shader = self.compile_shader(self.highlight_fragment_shader_source, gl.GL_FRAGMENT_SHADER)
            if vertex_shader == 0 or fragment_shader == 0:
                return

            self.highlight_shader_program = gl.glCreateProgram()
            gl.glAttachShader(self.highlight_shader_program, vertex_shader)
            gl.glAttachShader(self.highlight_shader_program, fragment_shader)
            gl.glLinkProgram(self.highlight_shader_program)

            if not gl.glGetProgramiv(self.highlight_shader_program, gl.GL_LINK_STATUS):
                gl.glDeleteProgram(self.highlight_shader_program)
                self.highlight_shader_program = 0
                return

            gl.glDeleteShader(vertex_shader)
            gl.glDeleteShader(fragment_shader)

            self.highlight_uniform_locations = {
                "uView": gl.glGetUniformLocation(self.highlight_shader_program, "uView"),
                "uProjection": gl.glGetUniformLocation(self.highlight_shader_program, "uProjection"),
                "uModel": gl.glGetUniformLocation(self.highlight_shader_program, "uModel"),
                "uHighlightColor": gl.glGetUniformLocation(self.highlight_shader_program, "uHighlightColor"),
            }
            self.highlight_initialized = True
        except Exception:
            self.highlight_initialized = False

    def compile_shader(self, source, shader_type):
        shader = gl.glCreateShader(shader_type)
        if shader == 0:
            return 0
        gl.glShaderSource(shader, source)
        gl.glCompileShader(shader)
        if not gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS):
            gl.glDeleteShader(shader)
            return 0
        return shader

    def render(self, view_matrix, projection_matrix, camera_position=None, camera_up=None, hover_highlight_tile=None):
        if not self.initializado:
            if self.dados_atualizados:
                self.init_gl()
            if not self.initializado:
                return

        # === 1. PLANETA ===
        gl.glUseProgram(self.shader_program)
        gl.glBindVertexArray(self.vao)

        # Cor
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_1D, self.tile_color_texture)
        gl.glUniform1i(self.uniform_locations["uTileColorTexture"], 0)

        # Visibilidade (FoW)
        gl.glActiveTexture(gl.GL_TEXTURE1)
        gl.glBindTexture(gl.GL_TEXTURE_1D, getattr(self, "visibility_texture", 0))
        gl.glUniform1i(self.uniform_locations["uVisibilityTexture"], 1)

        model_matrix = glm.mat4(1.0)
        gl.glUniformMatrix4fv(self.uniform_locations["uView"], 1, gl.GL_FALSE, view_matrix.T)
        gl.glUniformMatrix4fv(self.uniform_locations["uProjection"], 1, gl.GL_FALSE, projection_matrix.T)
        gl.glUniformMatrix4fv(self.uniform_locations["uModel"], 1, gl.GL_FALSE, glm.value_ptr(model_matrix))
        gl.glUniform1i(self.uniform_locations["uNumTiles"], len(self.tile_coords_to_index))

        gl.glDrawElements(gl.GL_TRIANGLES, self.index_count, gl.GL_UNSIGNED_INT, None)

        gl.glBindVertexArray(0)
        gl.glUseProgram(0)

        # === 2. HIGHLIGHT ===
        if hover_highlight_tile is not None:
            self._render_tile_highlight(hover_highlight_tile, view_matrix, projection_matrix)

        # === 3. ROTAS ===
        if self.route_renderer is not None:
            if hasattr(self, "centros_3d_tiles") and self.centros_3d_tiles:
                self.route_renderer.update_if_dirty(
                    self.centros_3d_tiles, lift=0.04, steps_per_segment=8, flip_x=False
                )
                self.route_renderer.render(
                    view_matrix, projection_matrix,
                    color=(0.1, 0.9, 1.0, 1.0),
                    width=3.0,
                    depth_test=True,
                )

        # === 4. BANDEIRAS ===
        if self.civ_flag_renderer.instances and self.civ_flag_renderer.initialized:
            self.civ_flag_renderer.render(view_matrix, projection_matrix)

        # === 5. UNIDADES ===
        if getattr(self.tile_units_renderer, "initialized", False):
            cam_pos = camera_position if camera_position is not None else [0.0, 0.0, 5.0]
            self.tile_units_renderer.render(view_matrix, projection_matrix, cam_pos)

    def _render_tile_highlight(self, tile_coords, view_matrix, projection_matrix, color=(1.0, 0.843, 0.0, 0.5)):
        if not self.highlight_initialized or self.highlight_shader_program == 0:
            return
        if tile_coords not in self.tile_coords_to_index:
            return

        cache = self._highlight_cache
        if cache["tile_coords"] != tile_coords:
            if cache["vao"] is not None:
                gl.glDeleteVertexArrays(1, [cache["vao"]])
            if cache["vbo"] is not None:
                gl.glDeleteBuffers(1, [cache["vbo"]])
            cache["vao"] = None
            cache["vbo"] = None

            tile_index = self.tile_coords_to_index[tile_coords]
            vertex_indices = [i for i, ti in enumerate(self.all_tile_indices) if ti == tile_index]
            if len(vertex_indices) < 3:
                cache["tile_coords"] = None
                cache["vertex_count"] = 0
                return

            tile_vertices = []
            for vi in vertex_indices:
                base = vi * 3
                if base + 2 < len(self.all_vertices):
                    tile_vertices.extend([self.all_vertices[base], self.all_vertices[base + 1], self.all_vertices[base + 2]])

            if len(tile_vertices) < 9:
                return
            tile_vertices_np = np.array(tile_vertices, dtype=np.float32)

            cache["vao"] = gl.glGenVertexArrays(1)
            cache["vbo"] = gl.glGenBuffers(1)

            gl.glBindVertexArray(cache["vao"])
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, cache["vbo"])
            gl.glBufferData(gl.GL_ARRAY_BUFFER, tile_vertices_np.nbytes, tile_vertices_np, gl.GL_STATIC_DRAW)
            gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, None)
            gl.glEnableVertexAttribArray(0)
            gl.glBindVertexArray(0)

            cache["tile_coords"] = tile_coords
            cache["vertex_count"] = len(tile_vertices_np) // 3

        if cache["vao"] is None or cache["vertex_count"] < 3:
            return

        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glDepthMask(gl.GL_FALSE)
        gl.glDisable(gl.GL_CULL_FACE)

        gl.glUseProgram(self.highlight_shader_program)
        gl.glBindVertexArray(cache["vao"])

        model_matrix = glm.mat4(1.0)
        model_matrix = glm.scale(model_matrix, glm.vec3(-1.0, 1.0, 1.0))
        gl.glUniformMatrix4fv(self.highlight_uniform_locations["uView"], 1, gl.GL_FALSE, view_matrix.T)
        gl.glUniformMatrix4fv(self.highlight_uniform_locations["uProjection"], 1, gl.GL_FALSE, projection_matrix.T)
        gl.glUniformMatrix4fv(self.highlight_uniform_locations["uModel"], 1, gl.GL_FALSE, glm.value_ptr(model_matrix))
        gl.glUniform4f(
            self.highlight_uniform_locations["uHighlightColor"],
            color[0], color[1], color[2], color[3]
        )
        gl.glDrawArrays(gl.GL_TRIANGLE_FAN, 0, cache["vertex_count"])

        gl.glBindVertexArray(0)
        gl.glDepthMask(gl.GL_TRUE)
        gl.glEnable(gl.GL_CULL_FACE)
        gl.glDisable(gl.GL_BLEND)

    def get_tile_at_pixel(self, x, y, widget_width, widget_height):
        if self.color_picker is not None and self.color_picker.initialized:
            # OBS: esse self.controller.camera pode não existir; quem tem camera é a SceneWidget.
            # Mantive sua lógica, mas considere ajustar para receber a camera via parâmetro.
            if self.controller and getattr(self.controller, "camera", None):
                return self.color_picker.get_tile_at_pixel(x, y, widget_width, widget_height, self.controller.camera)
        return None

    def get_tile_info(self, coords):
        return None

    def cleanup_gl(self):
        if self.vao:
            gl.glDeleteVertexArrays(1, [self.vao])
        if self.vbo_vertices:
            gl.glDeleteBuffers(1, [self.vbo_vertices])
        if self.vbo_tile_indices:
            gl.glDeleteBuffers(1, [self.vbo_tile_indices])
        if self.ebo_indices:
            gl.glDeleteBuffers(1, [self.ebo_indices])

        if hasattr(self, "tile_color_texture") and self.tile_color_texture:
            gl.glDeleteTextures(1, [self.tile_color_texture])

        if getattr(self, "visibility_texture", None):
            gl.glDeleteTextures(1, [self.visibility_texture])

        if self.shader_program:
            gl.glDeleteProgram(self.shader_program)

        self.vao = None
        self.vbo_vertices = None
        self.vbo_tile_indices = None
        self.ebo_indices = None

        self.tile_color_texture = None
        self.visibility_texture = None
        self.shader_program = 0

        if self.highlight_shader_program:
            gl.glDeleteProgram(self.highlight_shader_program)
            self.highlight_shader_program = 0

        cache = self._highlight_cache
        if cache["vao"] is not None:
            gl.glDeleteVertexArrays(1, [cache["vao"]])
        if cache["vbo"] is not None:
            gl.glDeleteBuffers(1, [cache["vbo"]])
        self._highlight_cache = {"tile_coords": None, "vao": None, "vbo": None, "vertex_count": 0}
        self.highlight_initialized = False

        self.initializado = False
        print("🧹 [PlanetRenderer] Recursos limpos")

    def set_route_path(self, path_tiles):
        if self.route_renderer is not None:
            self.route_renderer.state.set_path(path_tiles)
