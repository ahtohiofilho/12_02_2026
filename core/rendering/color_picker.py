# core/rendering/color_picker.py
import numpy as np
import OpenGL.GL as gl
import glm


class TileColorPicker:
    def __init__(self, planet_renderer):
        self.planet_renderer = planet_renderer
        self.fbo = 0
        self.texture = 0
        self.rbo = 0
        self.shader_program = 0
        self.initialized = False

        self.width = 0
        self.height = 0

        # Dicionário reverso: ID (int) -> (x, y) Coordenadas do Tile
        self.id_to_coords = {}

        # IMPORTANTE: A localização (location) dos atributos DEVE ser
        # a mesma que você usa no VBO do seu PlanetRenderer!
        # Normalmente: 0 = Pos, 1 = Normal, 2 = UV, 3 = TileIndex
        # Aqui assumiremos que o TileIndex é um float na location 3 (ajuste se precisar)
        self.vertex_shader = """
        #version 330 core
        layout (location = 0) in vec3 aPos;
        layout (location = 1) in uint aTileIndex;

        uniform mat4 uModel;
        uniform mat4 uView;
        uniform mat4 uProjection;

        flat out uint vTileID;

        void main() {
            gl_Position = uProjection * uView * uModel * vec4(aPos, 1.0);

            // aTileIndex já é uint, então basta somar 1
            vTileID = aTileIndex + 1u; 
        }
        """

        self.fragment_shader = """
        #version 330 core
        flat in uint vTileID;
        out vec4 FragColor;

        void main() {
            // Converte o ID inteiro (ex: 1050) em cores RGB perfeitas
            uint r = (vTileID & 0x000000FFu);
            uint g = (vTileID & 0x0000FF00u) >> 8u;
            uint b = (vTileID & 0x00FF0000u) >> 16u;

            FragColor = vec4(float(r)/255.0, float(g)/255.0, float(b)/255.0, 1.0);
        }
        """

    def init_gl(self):
        # Compila os shaders
        vs = self._compile_shader(self.vertex_shader, gl.GL_VERTEX_SHADER)
        fs = self._compile_shader(self.fragment_shader, gl.GL_FRAGMENT_SHADER)

        self.shader_program = gl.glCreateProgram()
        gl.glAttachShader(self.shader_program, vs)
        gl.glAttachShader(self.shader_program, fs)
        gl.glLinkProgram(self.shader_program)

        self.uniforms = {
            'uModel': gl.glGetUniformLocation(self.shader_program, "uModel"),
            'uView': gl.glGetUniformLocation(self.shader_program, "uView"),
            'uProjection': gl.glGetUniformLocation(self.shader_program, "uProjection")
        }

        # Constrói o mapeamento rápido de IDs
        self._build_mapping()
        self.initialized = True
        print("✅ [ColorPicker] Inicializado com sucesso.")

    def _build_mapping(self):
        self.id_to_coords.clear()
        # Mapeia o tile_index exato que o PlanetRenderer construiu para a coordenada (x, y)
        for coords, tile_index in self.planet_renderer.tile_coords_to_index.items():
            encoded_id = int(tile_index) + 1
            self.id_to_coords[encoded_id] = coords

    def _resize_fbo(self, w, h):
        if w == self.width and h == self.height and self.fbo != 0:
            return

        if self.fbo != 0:
            gl.glDeleteFramebuffers(1, [self.fbo])
            gl.glDeleteTextures(1, [self.texture])
            gl.glDeleteRenderbuffers(1, [self.rbo])

        self.width = w
        self.height = h

        self.fbo = gl.glGenFramebuffers(1)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)

        self.texture = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture)
        # USANDO RGBA PADRÃO (Sem frescura de float32, evita bugs e lê exato 0-255)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, w, h, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)

        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, self.texture, 0)

        self.rbo = gl.glGenRenderbuffers(1)
        gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self.rbo)
        gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_DEPTH_COMPONENT24, w, h)
        gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_DEPTH_ATTACHMENT, gl.GL_RENDERBUFFER, self.rbo)

        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)

    def get_tile_at_pixel(self, x, y, screen_width, screen_height, camera):
        if not self.initialized or not self.planet_renderer.vao:
            return None

        self._resize_fbo(screen_width, screen_height)

        # 1. Desenha a cena no Framebuffer secreto
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
        gl.glViewport(0, 0, screen_width, screen_height)
        gl.glClearColor(0.0, 0.0, 0.0, 0.0)  # Fundo ID 0
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        gl.glEnable(gl.GL_DEPTH_TEST)

        gl.glUseProgram(self.shader_program)

        view_matrix = camera.get_view_matrix()
        proj_matrix = camera.get_projection_matrix()

        # Pega a model matrix direto do renderer
        if hasattr(self.planet_renderer, 'model_matrix'):
            model_matrix = self.planet_renderer.model_matrix
        else:
            model_matrix = np.eye(4, dtype=np.float32)

        gl.glUniformMatrix4fv(self.uniforms['uView'], 1, gl.GL_FALSE, view_matrix.T)
        gl.glUniformMatrix4fv(self.uniforms['uProjection'], 1, gl.GL_FALSE, proj_matrix.T)
        gl.glUniformMatrix4fv(self.uniforms['uModel'], 1, gl.GL_FALSE, model_matrix.T)

        # Desenha a malha do planeta
        gl.glBindVertexArray(self.planet_renderer.vao)
        gl.glDrawElements(gl.GL_TRIANGLES, self.planet_renderer.index_count, gl.GL_UNSIGNED_INT, None)
        gl.glBindVertexArray(0)

        # 2. Lê o pixel sob o mouse
        # No OpenGL, o eixo Y é invertido em relação a tela
        gl_y = screen_height - int(y) - 1
        gl_x = int(x)

        try:
            pixel = gl.glReadPixels(gl_x, gl_y, 1, 1, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
            # Decodifica RGBA para o ID
            r, g, b, a = pixel[0]
            tile_id = r + (g << 8) + (b << 16)
        except Exception as e:
            print(f"Erro ao ler pixel: {e}")
            tile_id = 0

        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)

        # 3. Retorna a coordenada se não clicou no fundo
        if tile_id == 0:
            return None

        return self.id_to_coords.get(tile_id, None)

    def _compile_shader(self, source, shader_type):
        shader = gl.glCreateShader(shader_type)
        gl.glShaderSource(shader, source)
        gl.glCompileShader(shader)
        if not gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS):
            print(gl.glGetShaderInfoLog(shader).decode('utf-8'))
            raise RuntimeError("Erro ao compilar Color Picking Shader")
        return shader
