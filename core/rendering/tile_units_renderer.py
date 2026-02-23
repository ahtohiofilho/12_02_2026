# core/rendering/tile_units_renderer.py
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

        self.vertex_shader_source = """
        #version 330 core
        layout (location = 0) in vec3 aPos;
        layout (location = 1) in vec2 aTexCoords;

        out vec2 TexCoords;

        uniform mat4 uModel;
        uniform mat4 uView;
        uniform mat4 uProjection;

        void main() {
            // Inverte o Y da imagem
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

            // A MÁGICA FINAL AQUI:
            // Em vez de multiplicar pelo tamanho do planeta, adicionamos um offset fixo milimétrico.
            // 0.03 geralmente é perfeito para ficar acima do chão e da bandeira da civilização.
            // Se ainda "piscar" com a bandeira, aumente para 0.05. Se achar alto, baixe para 0.01.
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

            // Descarta os pixels transparentes para que o PNG não desenhe 
            // um quadrado preto invisível que tampa as unidades de trás.
            if (texColor.a < 0.1) {
                discard;
            }

            FragColor = texColor;
        }
        """

    def set_data(self, planet, centers_3d_tiles):
        print("\n--- [UnitsRenderer] Atualizando dados das unidades ---")
        self.instances.clear()

        if not planet:
            print("❌ Planeta é None!")
            return

        if not hasattr(planet, 'stacks'):
            print("❌ Planeta não possui o atributo 'stacks'!")
            return

        tiles_com_unidades = list(planet.stacks.stack_uids_by_tile.keys())
        print(f"🔍 Tiles que possuem stacks (pilhas): {tiles_com_unidades}")

        for tile, stack_uids in planet.stacks.stack_uids_by_tile.items():
            if not stack_uids:
                continue

            center = centers_3d_tiles.get(tile)
            if center is None:
                print(f"⚠️ Tile {tile} não tem centro 3D calculado.")
                continue

            stack_uid = list(stack_uids)[0]
            stack = planet.stacks.get_stack(stack_uid)

            if not stack or stack.is_empty():
                print(f"⚠️ Stack {stack_uid} no tile {tile} está vazia ou não existe.")
                continue

            first_unit = stack.units[0]
            unit_key = getattr(first_unit, 'unit_key', 'DESCONHECIDO')
            print(f"✅ Encontrada unidade '{unit_key}' no tile {tile}")

            stats = get_unit_stats(unit_key)
            if not stats:
                print(f"❌ Erro: Status não encontrados para a unidade '{unit_key}'.")
                continue

            sprite_key = getattr(stats, 'sprite_key', unit_key)
            print(f"   -> Preparando para desenhar o sprite: {sprite_key}.png")

            if sprite_key not in self.textures_cache:
                print(f"   -> Imagem nova! Tentando carregar do HD...")
                self.textures_cache[sprite_key] = self._load_texture(sprite_key)

            self.instances.append({
                "center": center,
                "sprite_key": sprite_key,
                "is_civilian": getattr(stats, 'is_non_combat', False)
            })

        print(f"--- [UnitsRenderer] Total de instâncias prontas para desenhar: {len(self.instances)} ---")

    def init_gl(self):
        if getattr(self, "initialized", False):
            return True

        # Compila shaders
        vs = self._compile_shader(self.vertex_shader_source, gl.GL_VERTEX_SHADER)
        fs = self._compile_shader(self.fragment_shader_source, gl.GL_FRAGMENT_SHADER)

        self.shader_program = gl.glCreateProgram()
        gl.glAttachShader(self.shader_program, vs)
        gl.glAttachShader(self.shader_program, fs)
        gl.glLinkProgram(self.shader_program)

        gl.glDeleteShader(vs)
        gl.glDeleteShader(fs)

        # Mapeando TODOS os uniforms para o dicionário que o 'render' precisa
        gl.glUseProgram(self.shader_program)
        self.uniform_locations = {
            "uModel": gl.glGetUniformLocation(self.shader_program, "uModel"),
            "uView": gl.glGetUniformLocation(self.shader_program, "uView"),
            "uProjection": gl.glGetUniformLocation(self.shader_program, "uProjection"),
            "uTexture": gl.glGetUniformLocation(self.shader_program, "uTexture"),
            # Variáveis extras (retornarão -1 se não existirem no seu shader, o que é seguro)
            "uCameraPos": gl.glGetUniformLocation(self.shader_program, "uCameraPos"),
            "uCenter": gl.glGetUniformLocation(self.shader_program, "uCenter"),
            "uSize": gl.glGetUniformLocation(self.shader_program, "uSize")
        }
        gl.glUseProgram(0)

        # Geometria do Quad (1x1) - AGORA COM 6 VÉRTICES (2 Triângulos)
        half_s = 0.5
        vertices = np.array([
            # Primeiro triângulo
            # x, y, z,          u, v
            -half_s, -half_s, 0.0, 0.0, 0.0,  # inferior esquerdo
            half_s, -half_s, 0.0, 1.0, 0.0,  # inferior direito
            half_s, half_s, 0.0, 1.0, 1.0,  # superior direito
            # Segundo triângulo
            half_s, half_s, 0.0, 1.0, 1.0,  # superior direito
            -half_s, half_s, 0.0, 0.0, 1.0,  # superior esquerdo
            -half_s, -half_s, 0.0, 0.0, 0.0  # inferior esquerdo
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

    def render(self, view_matrix, projection_matrix, camera_position):
        if not getattr(self, "initialized", False) or not self.instances:
            return

        gl.glUseProgram(self.shader_program)
        gl.glBindVertexArray(self.vao)

        # TRUQUE 1: Ativar a transparência (Alpha) do PNG
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

        # TRUQUE 2: Desabilitar o Teste de Profundidade temporariamente.
        # Isso faz com que a unidade seja desenhada "por cima" de tudo,
        # mesmo que ela estivesse escondida dentro do planeta!
        gl.glDisable(gl.GL_DEPTH_TEST)

        # Envia as matrizes de Câmera e Projeção (se existirem no shader)
        if self.uniform_locations["uView"] != -1:
            gl.glUniformMatrix4fv(self.uniform_locations["uView"], 1, gl.GL_FALSE, view_matrix.T)

        if self.uniform_locations["uProjection"] != -1:
            gl.glUniformMatrix4fv(self.uniform_locations["uProjection"], 1, gl.GL_FALSE, projection_matrix.T)

        # Enviar a posição da câmera para o Billboarding (se existir no shader)
        if self.uniform_locations["uCameraPos"] != -1:
            gl.glUniform3f(
                self.uniform_locations["uCameraPos"],
                float(camera_position[0]),
                float(camera_position[1]),
                float(camera_position[2])
            )

        import numpy as np  # Garantindo que o numpy está disponível para a matriz uModel

        for inst in self.instances:
            sprite_key = inst["sprite_key"]
            texture_id = self.textures_cache.get(sprite_key)
            if not texture_id:
                continue

            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture_id)
            if self.uniform_locations["uTexture"] != -1:
                gl.glUniform1i(self.uniform_locations["uTexture"], 0)

            # --- TRUQUE 3: Elevar e Posicionar a unidade ---
            c = inst["center"]

            # Multiplicamos a posição por 1.05 para ela flutuar 5% acima do chão (evita z-fighting)
            cx, cy, cz = float(c[0]) * 1.05, float(c[1]) * 1.05, float(c[2]) * 1.05
            scale = 0.2  # Tamanho da unidade na tela

            # 1) Estratégia A: Se o seu shader usar variáveis uCenter e uSize separadas
            if self.uniform_locations["uCenter"] != -1:
                gl.glUniform3f(self.uniform_locations["uCenter"], cx, cy, cz)
            if self.uniform_locations["uSize"] != -1:
                gl.glUniform1f(self.uniform_locations["uSize"], scale)

            # 2) Estratégia B: Se o seu shader usar uma uModel clássica (Matriz de Translação + Escala)
            if self.uniform_locations["uModel"] != -1:
                model_matrix = np.array([
                    [scale, 0.0, 0.0, 0.0],
                    [0.0, scale, 0.0, 0.0],
                    [0.0, 0.0, scale, 0.0],
                    [cx, cy, cz, 1.0]
                ], dtype=np.float32)
                gl.glUniformMatrix4fv(self.uniform_locations["uModel"], 1, gl.GL_FALSE, model_matrix)

            # Desenha o quadrado do Sprite (6 vértices / 2 triângulos)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 6)

        # Limpeza e restauração do estado original do OpenGL
        gl.glBindVertexArray(0)
        gl.glUseProgram(0)

        # Reativar o teste de profundidade para não estragar o resto do cenário!
        gl.glEnable(gl.GL_DEPTH_TEST)

    def _load_texture(self, sprite_key):
        """Carrega a imagem de assets/units/<sprite_key>.png"""
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
        """Compila um shader OpenGL e verifica se houve erros."""
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
