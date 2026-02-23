import numpy as np
import OpenGL.GL as gl
import glm
from core.rendering.civ_flag import CivFlag
from core.rendering.route_overlay import RouteOverlayRenderer
# from .color_picking import PickingSystem # Comentado por enquanto
from core.rendering.tile_units_renderer import TileUnitsRenderer

class PlanetRenderer:
    def __init__(self, controller):
        print(f"🔴 PlanetRenderer.__init__ chamado! ID: {id(self)}")
        self.vao = None
        self.vbo_vertices = None
        self.vbo_tile_indices = None
        self.ebo_indices = None
        self.index_count = 0
        self.shader_program = 0
        self.tile_coords_to_index = {}
        self.tile_colors = {}
        self.all_vertices = np.array([])
        self.all_indices = np.array([], dtype=np.uint32)
        self.all_tile_indices = np.array([], dtype=np.uint32)
        self.initializado = False
        self.dados_atualizados = False
        self.civ_flag_renderer = CivFlag()
        #self.picking_system = None
        self.controller = controller
        self.route_renderer = RouteOverlayRenderer()

        # Renderer unificado de unidades (militares + trabalhadores)
        self.tile_units_renderer = TileUnitsRenderer()

        # Recursos para highlight
        self.highlight_shader_program = 0
        self.highlight_initialized = False
        self._highlight_cache = {
            'tile_coords': None,
            'vao': None,
            'vbo': None,
            'vertex_count': 0
        }
        self.tile_vertex_range = {}

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
        uniform int uNumTiles;

        flat in uint tileIndex;

        void main()
        {
            if (int(tileIndex) >= uNumTiles || int(tileIndex) < 0) {
                FragColor = vec4(1.0, 0.0, 0.0, 1.0);
                return;
            }

            float texCoord = (float(tileIndex) + 0.5) / float(uNumTiles);
            FragColor = vec4(texture(uTileColorTexture, texCoord).rgb, 1.0);
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
            // Levanta ligeiramente para evitar z-fighting
            vec3 pos = aPos * 1.003;
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
        """
        Monta buffers de geometria do planeta.

        Melhorias:
        - Cria tile_coords_to_index uma vez
        - Pré-computa o range de vértices por tile (tile_vertex_range) para highlight O(1)
        - Remove prints de debug
        """
        self.coord_vert = coord_vert
        self.centros_3d_tiles = centros_3d_tiles

        all_vertices_list = []
        all_indices_list = []
        all_tile_indices_list = []
        current_global_index = 0

        # Range de vértices por tile (para highlight rápido)
        # tile_index -> (start_vertex, vertex_count)
        self.tile_vertex_range = {}

        # Criar mapeamento coordenada -> índice uma vez (ordem estável)
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

            # Registrar bloco contíguo deste tile dentro do buffer final
            start_index = current_global_index
            self.tile_vertex_range[current_tile_index] = (start_index, num_vertices)

            # Adicionar vértices e tileIndex por vértice
            # (mantém all_tile_indices por compatibilidade com o pipeline atual)
            for vertex in vertices_np:
                all_vertices_list.append(vertex)
                all_tile_indices_list.append(current_tile_index)
                current_global_index += 1

            # Gerar índices de triângulo (triangle fan)
            for i in range(1, num_vertices - 1):
                all_indices_list.extend([start_index, start_index + i, start_index + i + 1])

        self.all_vertices = np.array(all_vertices_list, dtype=np.float32).reshape(-1).astype(np.float32, copy=False)
        self.all_indices = np.array(all_indices_list, dtype=np.uint32)
        self.all_tile_indices = np.array(all_tile_indices_list, dtype=np.uint32)
        self.index_count = int(self.all_indices.size)

        # Marcar para recriar recursos GL no próximo init_gl()
        self.dados_atualizados = True
        self.initializado = False

        return True

    def set_civilization_data(self, planeta):
        if hasattr(self, 'centros_3d_tiles') and self.centros_3d_tiles:
            self.civ_flag_renderer.set_civilization_data(planeta, self.centros_3d_tiles)

    def set_tile_colors(self, tile_colors_dict):
        """Recebe um dicionário mapeando coordenadas de tile para cores [R, G, B]."""
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
            return False  # Ainda não há planeta — nada a fazer
        return not self.initializado or self.dados_atualizados

    def init_gl(self):
        """
        Inicializa os recursos OpenGL do PlanetRenderer e sub-renderers (CivFlag + RouteOverlay se existir).

        Política:
          - PlanetRenderer é dono do pipeline do planeta (VAO/VBO/EBO + shader + textura 1D + highlight).
          - Sub-renderers (bandeiras/rotas) são inicializados aqui também (best-effort),
            garantindo criação no mesmo contexto OpenGL (QOpenGLWidget).

        Retorna True se o planeta inicializou; sub-renderers não derrubam o planeta se falharem.
        """
        print("\n" + "=" * 50)
        print(f"🔧 PlanetRenderer.init_gl INICIADO (ID: {id(self)})")

        # IMPORTANTE: não zere dados_atualizados aqui no começo.
        # Se algo falhar, você quer que o próximo frame tente de novo.
        self.initializado = False

        # Verificação crítica de dados ANTES de qualquer operação OpenGL
        if len(self.all_vertices) == 0:
            print("❌ ERRO CRÍTICO: all_vertices VAZIO!")
            return False
        if len(self.all_indices) == 0:
            print("❌ ERRO CRÍTICO: all_indices VAZIO!")
            return False

        print(f"  Total de vértices: {len(self.all_vertices) // 3} ({(len(self.all_vertices) // 3):,})")
        print(f"  Total de índices: {len(self.all_indices):,}")
        print(f"  Total de tiles: {len(self.tile_coords_to_index)}")

        try:
            # Limpeza se já foi inicializado anteriormente (ou se restou lixo)
            self.cleanup_gl()

            # === SHADER PRINCIPAL DO PLANETA ===
            vertex_shader = self.compile_shader(self.vertex_shader_source, gl.GL_VERTEX_SHADER)
            fragment_shader = self.compile_shader(self.fragment_shader_source, gl.GL_FRAGMENT_SHADER)
            if vertex_shader == 0 or fragment_shader == 0:
                print("❌ Falha ao compilar shaders básicos")
                return False

            self.shader_program = gl.glCreateProgram()
            gl.glAttachShader(self.shader_program, vertex_shader)
            gl.glAttachShader(self.shader_program, fragment_shader)
            gl.glLinkProgram(self.shader_program)

            success = gl.glGetProgramiv(self.shader_program, gl.GL_LINK_STATUS)
            if not success:
                info_log = gl.glGetProgramInfoLog(self.shader_program)
                print(f"❌ Erro ao linkar shader principal: {info_log}")
                gl.glDeleteProgram(self.shader_program)
                self.shader_program = 0
                return False

            print(f"✅ Shader principal compilado (ID={self.shader_program})")
            gl.glDeleteShader(vertex_shader)
            gl.glDeleteShader(fragment_shader)

            # Cache de uniforms
            self.uniform_locations = {
                "uView": gl.glGetUniformLocation(self.shader_program, "uView"),
                "uProjection": gl.glGetUniformLocation(self.shader_program, "uProjection"),
                "uModel": gl.glGetUniformLocation(self.shader_program, "uModel"),
                "uNumTiles": gl.glGetUniformLocation(self.shader_program, "uNumTiles"),
                "uTileColorTexture": gl.glGetUniformLocation(self.shader_program, "uTileColorTexture"),
            }

            uniform_errors = 0
            for uniform_name, location in self.uniform_locations.items():
                if location == -1:
                    print(f"⚠️ Uniform não encontrado: '{uniform_name}'")
                    uniform_errors += 1
            if uniform_errors > 0:
                print(f"⚠️ {uniform_errors} uniforms não encontrados")

            # === VAO E BUFFERS ===
            self.vao = gl.glGenVertexArrays(1)
            gl.glBindVertexArray(self.vao)

            # VBO: posições
            self.vbo_vertices = gl.glGenBuffers(1)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_vertices)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, self.all_vertices.nbytes, self.all_vertices, gl.GL_STATIC_DRAW)
            gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, None)
            gl.glEnableVertexAttribArray(0)

            # VBO: tileIndex (integer attribute)
            self.vbo_tile_indices = gl.glGenBuffers(1)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_tile_indices)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, self.all_tile_indices.nbytes, self.all_tile_indices, gl.GL_STATIC_DRAW)
            gl.glVertexAttribIPointer(1, 1, gl.GL_UNSIGNED_INT, 0, None)
            gl.glEnableVertexAttribArray(1)

            # EBO: índices
            self.ebo_indices = gl.glGenBuffers(1)
            gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.ebo_indices)
            gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, self.all_indices.nbytes, self.all_indices, gl.GL_STATIC_DRAW)

            gl.glBindVertexArray(0)

            # === TEXTURA 1D DE CORES ===
            self.tile_color_texture = gl.glGenTextures(1)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_1D, self.tile_color_texture)

            gl.glTexParameteri(gl.GL_TEXTURE_1D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
            gl.glTexParameteri(gl.GL_TEXTURE_1D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
            gl.glTexParameteri(gl.GL_TEXTURE_1D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)

            if hasattr(self, "tile_color_texture_data") and self.tile_color_texture_data is not None:
                num_colors = int(self.tile_color_texture_data.shape[0])
                gl.glTexImage1D(
                    gl.GL_TEXTURE_1D,
                    0,
                    gl.GL_RGB32F,
                    num_colors,
                    0,
                    gl.GL_RGB,
                    gl.GL_FLOAT,
                    self.tile_color_texture_data,
                )
                print(f"✅ Textura de cores carregada ({num_colors} cores)")
            else:
                dummy_color = np.array([0.5, 0.5, 0.5], dtype=np.float32)
                gl.glTexImage1D(gl.GL_TEXTURE_1D, 0, gl.GL_RGB32F, 1, 0, gl.GL_RGB, gl.GL_FLOAT, dummy_color)
                print("⚠️ Textura de cores dummy carregada")

            # === SHADER DE HIGHLIGHT ===
            self._init_highlight_shader()

            # === SUB-RENDERERS (best-effort) ===

            # (1) Bandeiras (CivFlag)
            if hasattr(self, "civ_flag_renderer") and self.civ_flag_renderer is not None:
                try:
                    ok = self.civ_flag_renderer.init_gl()
                    if ok:
                        print("✅ CivFlag.init_gl concluído")
                    else:
                        print("⚠️ CivFlag.init_gl falhou (bandeiras desativadas por enquanto)")
                except Exception as e:
                    print(f"⚠️ Exceção ao inicializar CivFlag: {e}")

            # (2) Rotas (RouteOverlay) — se você adicionou self.route_renderer no __init__
            if hasattr(self, "route_renderer") and self.route_renderer is not None:
                try:
                    ok = self.route_renderer.init_gl()
                    if ok:
                        print("✅ RouteOverlay.init_gl concluído")
                    else:
                        print("⚠️ RouteOverlay.init_gl falhou (rotas desativadas por enquanto)")
                except Exception as e:
                    print(f"⚠️ Exceção ao inicializar RouteOverlay: {e}")

            # (3) Unidades Militares e Workers
            if hasattr(self, "tile_units_renderer") and self.tile_units_renderer is not None:
                try:
                    ok = self.tile_units_renderer.init_gl()
                    if ok: print("✅ TileUnitsRenderer.init_gl concluído")
                except Exception as e:
                    print(f"⚠️ Exceção ao inicializar TileUnitsRenderer: {e}")

            # === VERIFICAÇÃO DE ERROS OPENGL ===
            error = gl.glGetError()
            if error != gl.GL_NO_ERROR:
                print(f"⚠️ Erro OpenGL pós-inicialização: {error}")
            else:
                print("✅ Recursos OpenGL criados sem erros")

            # Atualização FINAL do estado
            self.initializado = True
            self.dados_atualizados = False
            print("✅ PlanetRenderer.init_gl concluído com sucesso")
            return True

        except Exception as e:
            print(f"💥 ERRO CRÍTICO durante init_gl: {e}")
            import traceback
            traceback.print_exc()
            self.cleanup_gl()
            self.initializado = False
            # Mantém dados_atualizados=True para tentar novamente depois
            self.dados_atualizados = True
            return False

    def _init_highlight_shader(self):
        """Inicializa o shader para highlight de tiles."""
        try:
            vertex_shader = self.compile_shader(
                self.highlight_vertex_shader_source,
                gl.GL_VERTEX_SHADER
            )
            fragment_shader = self.compile_shader(
                self.highlight_fragment_shader_source,
                gl.GL_FRAGMENT_SHADER
            )

            if vertex_shader == 0 or fragment_shader == 0:
                print("⚠️ [PlanetRenderer] Falha ao compilar shaders de highlight")
                return

            self.highlight_shader_program = gl.glCreateProgram()
            gl.glAttachShader(self.highlight_shader_program, vertex_shader)
            gl.glAttachShader(self.highlight_shader_program, fragment_shader)
            gl.glLinkProgram(self.highlight_shader_program)

            success = gl.glGetProgramiv(self.highlight_shader_program, gl.GL_LINK_STATUS)
            if not success:
                info_log = gl.glGetProgramInfoLog(self.highlight_shader_program)
                print(f"❌ [PlanetRenderer] Erro ao linkar shader de highlight: {info_log}")
                gl.glDeleteProgram(self.highlight_shader_program)
                self.highlight_shader_program = 0
                return

            gl.glDeleteShader(vertex_shader)
            gl.glDeleteShader(fragment_shader)

            self.highlight_uniform_locations = {
                'uView': gl.glGetUniformLocation(self.highlight_shader_program, "uView"),
                'uProjection': gl.glGetUniformLocation(self.highlight_shader_program, "uProjection"),
                'uModel': gl.glGetUniformLocation(self.highlight_shader_program, "uModel"),
                'uHighlightColor': gl.glGetUniformLocation(self.highlight_shader_program, "uHighlightColor"),
            }

            self.highlight_initialized = True
            print("✅ [PlanetRenderer] Shader de highlight inicializado")

        except Exception as e:
            print(f"❌ [PlanetRenderer] Erro ao inicializar highlight: {e}")
            self.highlight_initialized = False

    def compile_shader(self, source, shader_type):
        """Compila um shader GLSL com verificação rigorosa."""
        shader = gl.glCreateShader(shader_type)
        if shader == 0:
            print(f"❌ ERRO: Não foi possível criar shader do tipo {shader_type}")
            return 0

        gl.glShaderSource(shader, source)
        gl.glCompileShader(shader)

        success = gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS)
        if not success:
            info_log = gl.glGetShaderInfoLog(shader).decode()
            print(f"❌ ERRO ao compilar Shader ({shader_type}):\n{info_log}")
            gl.glDeleteShader(shader)
            return 0

        return shader

    def render(
            self,
            view_matrix,
            projection_matrix,
            camera_position=None,
            camera_up=None,
            hover_highlight_tile=None,
    ):
        """
        Renderização do planeta com política consistente de matrizes:
        - Camera retorna numpy matrizes SEM transposição
        - Renderer envia para OpenGL com .T (row-major -> column-major) usando GL_FALSE

        Pipeline de renderização:
            1. Planeta (tiles coloridos)
            2. Highlight de tile (hover)
            3. Overlay de rotas (RouteOverlayRenderer)
            4. Bandeiras das civilizações (CivFlag)
        """
        # Verificação de inicialização
        if not self.initializado:
            if self.dados_atualizados:
                self.init_gl()
            if not self.initializado:
                return

        # === 1. RENDERIZAÇÃO DO PLANETA ===
        gl.glUseProgram(self.shader_program)
        gl.glBindVertexArray(self.vao)

        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_1D, self.tile_color_texture)

        model_matrix = glm.mat4(1.0)

        gl.glUniformMatrix4fv(
            self.uniform_locations["uView"], 1, gl.GL_FALSE, view_matrix.T,
        )
        gl.glUniformMatrix4fv(
            self.uniform_locations["uProjection"], 1, gl.GL_FALSE, projection_matrix.T,
        )
        gl.glUniformMatrix4fv(
            self.uniform_locations["uModel"], 1, gl.GL_FALSE, glm.value_ptr(model_matrix),
        )

        gl.glUniform1i(self.uniform_locations["uNumTiles"], len(self.tile_coords_to_index))
        gl.glUniform1i(self.uniform_locations["uTileColorTexture"], 0)

        gl.glDrawElements(gl.GL_TRIANGLES, self.index_count, gl.GL_UNSIGNED_INT, None)

        gl.glBindVertexArray(0)
        gl.glUseProgram(0)

        # === 2. HIGHLIGHT DE TILE ===
        if hover_highlight_tile is not None:
            self._render_tile_highlight(
                hover_highlight_tile,
                view_matrix,
                projection_matrix,
                color=(1.0, 0.843, 0.0, 0.5),
            )

        # === 3. ROUTE OVERLAY ===
        if hasattr(self, "route_renderer") and self.route_renderer is not None:
            if hasattr(self, "centros_3d_tiles") and self.centros_3d_tiles:
                # Recalcula pontos + sobe VBO quando state.dirty=True
                self.route_renderer.update_if_dirty(
                    self.centros_3d_tiles,
                    lift=0.04,
                    steps_per_segment=8,
                    flip_x=False,  # consistente com seu mundo espelhado
                )

                # Desenha a linha (se vertex_count >= 2)
                self.route_renderer.render(
                    view_matrix,
                    projection_matrix,
                    color=(0.1, 0.9, 1.0, 1.0),
                    width=3.0,
                    depth_test=True,
                )

        # === 4. BANDEIRAS DAS CIVILIZAÇÕES ===
        if self.civ_flag_renderer.instances and self.civ_flag_renderer.initialized:
            self.civ_flag_renderer.render(view_matrix, projection_matrix)

        # === 5. UNIDADES MILITARES E TRABALHADORES ===
        if hasattr(self, "tile_units_renderer") and getattr(self.tile_units_renderer, "initialized", False):
            # Fallback de segurança: se a câmera não for passada, assume uma posição padrão
            cam_pos = camera_position if camera_position is not None else [0.0, 0.0, 5.0]

            self.tile_units_renderer.render(view_matrix, projection_matrix, cam_pos)

    def _render_tile_highlight(self, tile_coords, view_matrix, projection_matrix,
                               color=(1.0, 0.843, 0.0, 0.5)):
        """
        Renderiza um highlight visual em um tile específico.
        Usa cache para evitar recriar VAO/VBO a cada frame.
        """
        if not self.highlight_initialized or self.highlight_shader_program == 0:
            return

        if tile_coords not in self.tile_coords_to_index:
            return

        cache = self._highlight_cache

        # Verificar se precisa atualizar o cache
        if cache['tile_coords'] != tile_coords:
            # Limpar cache antigo
            if cache['vao'] is not None:
                gl.glDeleteVertexArrays(1, [cache['vao']])
                cache['vao'] = None
            if cache['vbo'] is not None:
                gl.glDeleteBuffers(1, [cache['vbo']])
                cache['vbo'] = None

            # Criar nova geometria
            tile_index = self.tile_coords_to_index[tile_coords]

            # Encontrar vértices deste tile
            vertex_indices = []
            for i, ti in enumerate(self.all_tile_indices):
                if ti == tile_index:
                    vertex_indices.append(i)

            if len(vertex_indices) < 3:
                cache['tile_coords'] = None
                cache['vertex_count'] = 0
                return

            # Extrair vértices
            tile_vertices = []
            for vi in vertex_indices:
                base = vi * 3
                if base + 2 < len(self.all_vertices):
                    tile_vertices.extend([
                        self.all_vertices[base],
                        self.all_vertices[base + 1],
                        self.all_vertices[base + 2]
                    ])

            if len(tile_vertices) < 9:
                cache['tile_coords'] = None
                cache['vertex_count'] = 0
                return

            tile_vertices_np = np.array(tile_vertices, dtype=np.float32)

            # Criar VAO/VBO
            cache['vao'] = gl.glGenVertexArrays(1)
            cache['vbo'] = gl.glGenBuffers(1)

            gl.glBindVertexArray(cache['vao'])
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, cache['vbo'])
            gl.glBufferData(gl.GL_ARRAY_BUFFER, tile_vertices_np.nbytes,
                            tile_vertices_np, gl.GL_STATIC_DRAW)

            gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, None)
            gl.glEnableVertexAttribArray(0)

            gl.glBindVertexArray(0)

            cache['tile_coords'] = tile_coords
            cache['vertex_count'] = len(tile_vertices_np) // 3

        # Renderizar usando cache
        if cache['vao'] is None or cache['vertex_count'] < 3:
            return

        # Configurar estado OpenGL para transparência
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glDepthMask(gl.GL_FALSE)
        gl.glDisable(gl.GL_CULL_FACE)

        gl.glUseProgram(self.highlight_shader_program)
        gl.glBindVertexArray(cache['vao'])

        model_matrix = glm.mat4(1.0)
        model_matrix = glm.scale(model_matrix, glm.vec3(-1.0, 1.0, 1.0))

        gl.glUniformMatrix4fv(self.highlight_uniform_locations['uView'],
                              1, gl.GL_FALSE, view_matrix.T)
        gl.glUniformMatrix4fv(self.highlight_uniform_locations['uProjection'],
                              1, gl.GL_FALSE, projection_matrix.T)
        gl.glUniformMatrix4fv(self.highlight_uniform_locations['uModel'],
                              1, gl.GL_FALSE, glm.value_ptr(model_matrix))
        gl.glUniform4f(self.highlight_uniform_locations['uHighlightColor'],
                       color[0], color[1], color[2], color[3])

        gl.glDrawArrays(gl.GL_TRIANGLE_FAN, 0, cache['vertex_count'])

        # Restaurar estado OpenGL
        gl.glBindVertexArray(0)
        gl.glDepthMask(gl.GL_TRUE)
        gl.glEnable(gl.GL_CULL_FACE)
        gl.glDisable(gl.GL_BLEND)

    def get_tile_at_pixel(self, x, y, widget_width, widget_height):
        """Interface para o sistema de picking"""
        if (hasattr(self, 'picking_system') and
                self.picking_system is not None and
                self.picking_system.initialized):
            return self.picking_system.get_tile_at_pixel(x, y, widget_width, widget_height)
        else:
            print("⚠️ [PlanetRenderer] PickingSystem não disponível")
        return None

    def get_tile_info(self, coords):
        """Interface para obter informações do tile"""
        if hasattr(self, 'picking_system') and self.picking_system is not None:
            return self.picking_system.get_tile_info(coords)
        return None

    def cleanup_gl(self):
        """Limpa os recursos OpenGL (VAO, VBOs, EBO, Shaders, Texturas, Highlight)."""
        # Recursos principais
        if self.vao:
            gl.glDeleteVertexArrays(1, [self.vao])
            self.vao = None
        if self.vbo_vertices:
            gl.glDeleteBuffers(1, [self.vbo_vertices])
            self.vbo_vertices = None
        if self.vbo_tile_indices:
            gl.glDeleteBuffers(1, [self.vbo_tile_indices])
            self.vbo_tile_indices = None
        if self.ebo_indices:
            gl.glDeleteBuffers(1, [self.ebo_indices])
            self.ebo_indices = None
        if hasattr(self, 'tile_color_texture') and self.tile_color_texture:
            gl.glDeleteTextures(1, [self.tile_color_texture])
            self.tile_color_texture = None
        if self.shader_program:
            gl.glDeleteProgram(self.shader_program)
            self.shader_program = 0

        # Recursos do highlight
        if self.highlight_shader_program:
            gl.glDeleteProgram(self.highlight_shader_program)
            self.highlight_shader_program = 0

        # Cache do highlight
        cache = self._highlight_cache
        if cache['vao'] is not None:
            gl.glDeleteVertexArrays(1, [cache['vao']])
        if cache['vbo'] is not None:
            gl.glDeleteBuffers(1, [cache['vbo']])
        self._highlight_cache = {
            'tile_coords': None,
            'vao': None,
            'vbo': None,
            'vertex_count': 0
        }
        self.highlight_initialized = False

        # Sub-renderers
        if hasattr(self, 'picking_system') and self.picking_system:
            self.picking_system.cleanup()
            self.picking_system = None

        if hasattr(self, 'civ_icon_renderer'):
            #self.civ_icon_renderer.cleanup()
            pass

        # Tile Units Renderer (unificado)
        if hasattr(self, 'tile_units_renderer'):
            #self.tile_units_renderer.cleanup()
            pass

        self.initializado = False
        print("🧹 [PlanetRenderer] Recursos limpos")

    def set_route_path(self, path_tiles) -> None:
        if hasattr(self, "route_renderer") and self.route_renderer is not None:
            self.route_renderer.state.set_path(path_tiles)
