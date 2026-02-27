# core/rendering/tile_units_renderer.py
import math
import numpy as np
import OpenGL.GL as gl
import glm
from PIL import Image
from pathlib import Path
from config.unit_stats import get_unit_stats


class TileUnitsRenderer:
    def __init__(self):
        self.instances = []  # Lista de dicionários com dados para renderizar
        self.textures_cache = {}  # Cache: sprite_key -> GL texture ID
        self.initialized = False

        self.shader_program = 0
        self.vao = None
        self.vbo = None

        # ID da civilização controlada (para distinguir unidades próprias vs inimigas)
        self._controlled_civ_id: int = 0

        self.vertex_shader_source = """
        #version 330 core
        layout (location = 0) in vec3 aPos;
        layout (location = 1) in vec2 aTexCoords;

        out vec2 TexCoords;

        uniform mat4 uModel;
        uniform mat4 uView;
        uniform mat4 uProjection;

        void main() {
            // Inverte o Y da imagem para não ficar de ponta-cabeça
            TexCoords = vec2(aTexCoords.x, 1.0 - aTexCoords.y);

            vec3 tileCenter = vec3(uModel[3][0], uModel[3][1], uModel[3][2]);
            float size = uModel[0][0];

            vec3 upVec = normalize(tileCenter);
            vec3 worldNorth = vec3(0.0, 1.0, 0.0);

            if (abs(dot(upVec, worldNorth)) > 0.99) {
                worldNorth = vec3(1.0, 0.0, 0.0);
            }

            vec3 rightVec = normalize(cross(worldNorth, upVec));
            vec3 forwardVec = normalize(cross(upVec, rightVec));

            // Elevação fixa milimétrica (0.03) para evitar Z-Fighting com o chão e a bandeira
            vec3 finalCenter = tileCenter + (upVec * 0.03); 

            vec3 vertexWorldPos = finalCenter 
                                + (rightVec * aPos.x * size) 
                                + (forwardVec * aPos.y * size);

            gl_Position = uProjection * uView * vec4(vertexWorldPos, 1.0);
        }
        """

        self.fragment_shader_source = """
        #version 330 core
        in vec2 TexCoords;
        out vec4 FragColor;

        uniform sampler2D uTexture;

        void main() {
            vec4 texColor = texture(uTexture, TexCoords);

            // Descarta os pixels transparentes
            if (texColor.a < 0.1) {
                discard;
            }

            FragColor = texColor;
        }
        """

    def set_data(self, planet, centers_3d_tiles):
        print("\n--- [UnitsRenderer] Atualizando dados das unidades ---")
        self.instances.clear()

        if not planet or not hasattr(planet, "stacks"):
            print("❌ Planeta é None ou não possui o atributo 'stacks'!")
            return

        # Tiles visíveis via Fog of War (para filtrar unidades inimigas)
        visible_tiles = getattr(self, "visible_tiles", None)

        tiles_com_unidades = list(planet.stacks.stack_uids_by_tile.keys())
        print(f"🔍 Tiles que possuem stacks (pilhas): {tiles_com_unidades}")

        for tile, stack_uids in planet.stacks.stack_uids_by_tile.items():
            if not stack_uids:
                continue

            center_3d = centers_3d_tiles.get(tile)
            if center_3d is None:
                continue

            # Processa todas as stacks no tile
            for stack_uid in stack_uids:
                stack = planet.stacks.get_stack(stack_uid)
                if not stack or stack.is_empty():
                    continue

                # Determina se esta stack é da civilização controlada
                is_own_stack = stack.owner_id == self._controlled_civ_id

                # REGRA DE VISIBILIDADE:
                # - Unidades PRÓPRIAS: sempre renderizadas (VisibilityManager garante visibilidade)
                # - Unidades INIMIGAS/NEUTRAS: só renderizadas se o tile estiver visível
                if not is_own_stack and visible_tiles is not None and tile not in visible_tiles:
                    continue  # Inimigo em tile não visível: não renderiza

                total_units = len(stack.units)
                center_vec = glm.vec3(center_3d[0], center_3d[1], center_3d[2])

                for i, unit in enumerate(stack.units):
                    unit_key = getattr(unit, "unit_key", "DESCONHECIDO")
                    print(f"✅ Encontrada unidade '{unit_key}' no tile {tile} (civ={stack.owner_id}, own={is_own_stack})")

                    stats = get_unit_stats(unit_key)
                    if not stats:
                        print(f"❌ Erro: Status não encontrados para a unidade '{unit_key}'.")
                        continue

                    sprite_key = getattr(stats, "sprite_key", unit_key)

                    # Calcula posição com spread se múltiplas unidades
                    if total_units > 1:
                        normal = glm.normalize(center_vec)

                        north = glm.vec3(0.0, 1.0, 0.0)
                        if abs(glm.dot(normal, north)) > 0.99:
                            north = glm.vec3(1.0, 0.0, 0.0)

                        right = glm.normalize(glm.cross(north, normal))
                        forward = glm.normalize(glm.cross(normal, right))

                        spread_radius = 0.3
                        angle = (i / total_units) * math.pi * 2.0

                        offset_pos = center_vec + (right * math.cos(angle) * spread_radius) + (
                                forward * math.sin(angle) * spread_radius
                        )

                        radius = glm.length(center_vec)
                        offset_pos = glm.normalize(offset_pos) * radius
                        final_center = (offset_pos.x, offset_pos.y, offset_pos.z)
                    else:
                        final_center = (center_vec.x, center_vec.y, center_vec.z)

                    self.instances.append({
                        "center": final_center,
                        "sprite_key": sprite_key,
                        "is_civilian": getattr(stats, "is_non_combat", False),
                        "is_own_unit": is_own_stack,  # Para possível destaque visual
                    })

        print(f"--- [UnitsRenderer] Total de instâncias prontas para desenhar: {len(self.instances)} ---")

    def init_gl(self):
        if getattr(self, "initialized", False):
            return True

        vs = self._compile_shader(self.vertex_shader_source, gl.GL_VERTEX_SHADER)
        fs = self._compile_shader(self.fragment_shader_source, gl.GL_FRAGMENT_SHADER)

        self.shader_program = gl.glCreateProgram()
        gl.glAttachShader(self.shader_program, vs)
        gl.glAttachShader(self.shader_program, fs)
        gl.glLinkProgram(self.shader_program)

        gl.glDeleteShader(vs)
        gl.glDeleteShader(fs)

        gl.glUseProgram(self.shader_program)
        self.uniform_locations = {
            "uModel": gl.glGetUniformLocation(self.shader_program, "uModel"),
            "uView": gl.glGetUniformLocation(self.shader_program, "uView"),
            "uProjection": gl.glGetUniformLocation(self.shader_program, "uProjection"),
            "uTexture": gl.glGetUniformLocation(self.shader_program, "uTexture")
        }
        gl.glUseProgram(0)

        # Geometria do Quad (1x1) - 6 Vértices
        half_s = 0.5
        vertices = np.array([
            -half_s, -half_s, 0.0, 0.0, 0.0,
            half_s, -half_s, 0.0, 1.0, 0.0,
            half_s, half_s, 0.0, 1.0, 1.0,
            half_s, half_s, 0.0, 1.0, 1.0,
            -half_s, half_s, 0.0, 0.0, 1.0,
            -half_s, -half_s, 0.0, 0.0, 0.0
        ], dtype=np.float32)

        self.vao = gl.glGenVertexArrays(1)
        self.vbo = gl.glGenBuffers(1)

        gl.glBindVertexArray(self.vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, vertices.nbytes, vertices, gl.GL_STATIC_DRAW)

        # Posições (Layout 0)
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 5 * 4, None)
        # UVs (Layout 1)
        gl.glEnableVertexAttribArray(1)
        gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, 5 * 4, gl.ctypes.c_void_p(12))

        gl.glBindVertexArray(0)

        self.initialized = True
        print("✅ TileUnitsRenderer.init_gl concluído")
        return True

    def render(self, view_matrix, projection_matrix, camera_position=None):
        if not getattr(self, "initialized", False) or not self.instances:
            return

        gl.glUseProgram(self.shader_program)
        gl.glBindVertexArray(self.vao)

        # Ativar a transparência (Alpha) do PNG
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

        if self.uniform_locations["uView"] != -1:
            gl.glUniformMatrix4fv(self.uniform_locations["uView"], 1, gl.GL_FALSE, view_matrix.T)

        if self.uniform_locations["uProjection"] != -1:
            gl.glUniformMatrix4fv(self.uniform_locations["uProjection"], 1, gl.GL_FALSE, projection_matrix.T)

        # 👇 TAMANHO DA UNIDADE: Altere aqui se quiser maior ou menor!
        scale = 1.0
        # 👆==========================================================👆

        for inst in self.instances:
            sprite_key = inst["sprite_key"]
            # Aqui temos 100% de garantia que o OpenGL está ativo e pronto!
            if sprite_key not in self.textures_cache:
                print(f"   -> [Render] Carregando textura na GPU: {sprite_key}.png")
                self.textures_cache[sprite_key] = self._load_texture(sprite_key)
            texture_id = self.textures_cache.get(sprite_key)
            if not texture_id:
                continue

            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture_id)
            if self.uniform_locations["uTexture"] != -1:
                gl.glUniform1i(self.uniform_locations["uTexture"], 0)

            c = inst["center"]
            # Extraindo a coordenada crua (o Shader faz a elevação!)
            cx, cy, cz = float(c[0]), float(c[1]), float(c[2])

            if self.uniform_locations["uModel"] != -1:
                model_matrix = np.array([
                    [scale, 0.0, 0.0, 0.0],
                    [0.0, scale, 0.0, 0.0],
                    [0.0, 0.0, scale, 0.0],
                    [cx, cy, cz, 1.0]
                ], dtype=np.float32)
                gl.glUniformMatrix4fv(self.uniform_locations["uModel"], 1, gl.GL_FALSE, model_matrix)

            # Desenha o quadrado do Sprite
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 6)

        gl.glBindVertexArray(0)
        gl.glUseProgram(0)

        # Desativa o BLEND para não interferir na renderização de outras coisas
        gl.glDisable(gl.GL_BLEND)

    def _load_texture(self, sprite_key):
        path = Path("assets") / "units" / f"{sprite_key}.png"
        if not path.exists():
            print(f"⚠️ [UnitsRenderer] Imagem não encontrada: {path}")
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
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, img.width, img.height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE,
                            img_data)
            return tex
        except Exception as e:
            print(f"❌ Erro ao carregar {path}: {e}")
            return 0

    def _compile_shader(self, source, shader_type):
        shader = gl.glCreateShader(shader_type)
        gl.glShaderSource(shader, source)
        gl.glCompileShader(shader)

        status = gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS)
        if not status:
            error_log = gl.glGetShaderInfoLog(shader)
            if isinstance(error_log, bytes):
                error_log = error_log.decode('utf-8')
            print(f"❌ Erro ao compilar shader: {error_log}")
            gl.glDeleteShader(shader)
            raise RuntimeError(f"Falha na compilação do Shader: {error_log}")

        return shader