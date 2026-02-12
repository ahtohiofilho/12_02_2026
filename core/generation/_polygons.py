import math
import numpy
import glm


def dicionario_poligonos(fator):
    def icosaedro():

        def triangulo_original():

            def primeira_definicao_pontos():
                lista_pontos = []
                for x in range(fator ** 2):
                    if x % 2 == 0:
                        coord_x = x / 2 + 0.5
                        coord_y = math.sin(math.pi / 6)
                    else:
                        coord_x = x / 2 + 0.5
                        coord_y = math.sqrt(3) / 3
                    lista_pontos.append((round(coord_x, 15), round(coord_y, 15)))
                return lista_pontos

            def ponto_por_linha():
                lista_pontos = [0]
                ppf = fator * 2 - 1
                una = fator * 2 - 1
                while una != 1:
                    lista_pontos.append(ppf)
                    ppf += una - 2
                    una -= 2
                return lista_pontos

            def processar_coordenadas(coordenadas, indices):
                r = math.sqrt(3) / 3
                h = math.sqrt(0.75) * fator
                coords = []
                for i in range(len(indices)):
                    if i == len(indices) - 1:
                        segmento = [coordenadas[-1]]
                    else:
                        inicio, fim = indices[i], indices[i + 1]
                        segmento = coordenadas[inicio:fim]
                    for x in range(len(segmento)):
                        coefy = math.sin(math.pi / 6) * r
                        cx = (0.5 * i + 0.5 * x) + 0.5 - fator / 2
                        if x % 2 == 0:
                            cy = 0 + math.sqrt(0.75) * i + coefy - h / 2
                        else:
                            cy = r - coefy + math.sqrt(0.75) * i + coefy - h / 2
                        coords.append((cx, cy))
                return coords

            return processar_coordenadas(primeira_definicao_pontos(), ponto_por_linha())

        to = triangulo_original()

        def triangulos_equatoriais_em_pe():
            raio = fator / (2 * math.sin(math.pi / 5))
            apotema = fator / (2 * math.tan(math.pi / 5))
            theta = math.asin((raio - apotema) / fator)
            h = fator * math.sqrt(0.75)
            t1 = [(x, math.cos(theta) * y, math.sin(theta) * y) for x, y in to]
            t1 = [(x, y, z + apotema + math.sin(theta) * h / 2) for x, y, z in t1]
            return t1

        t1 = triangulos_equatoriais_em_pe()

        def rotacionar_em_torno_do_eixo_y(coordenadas, angulo_graus):
            angulo_radianos = math.radians(angulo_graus)
            cos_theta = math.cos(angulo_radianos)
            sin_theta = math.sin(angulo_radianos)
            coordenadas_rotacionadas = []
            for x, y, z in coordenadas:
                x_novo = cos_theta * x + sin_theta * z
                y_novo = y
                z_novo = -sin_theta * x + cos_theta * z
                coordenadas_rotacionadas.append((x_novo, y_novo, z_novo))
            return coordenadas_rotacionadas

        t2 = rotacionar_em_torno_do_eixo_y(t1, 72)
        t3 = rotacionar_em_torno_do_eixo_y(t1, 144)
        t4 = rotacionar_em_torno_do_eixo_y(t1, 216)
        t5 = rotacionar_em_torno_do_eixo_y(t1, 288)

        def triangulos_equatoriais_invertidos():
            raio = fator / (2 * math.sin(math.pi / 5))
            apotema = fator / (2 * math.tan(math.pi / 5))
            theta = math.asin((raio - apotema) / fator)
            h = fator * math.sqrt(0.75)
            t6 = [(x, -y) for x, y in to]
            t6 = [(x, math.cos(theta) * y, math.sin(theta) * -y) for x, y in t6]
            t6 = [(x, y, z + apotema + math.sin(theta) * h / 2) for x, y, z in t6]
            return t6

        tr = triangulos_equatoriais_invertidos()
        t6 = rotacionar_em_torno_do_eixo_y(tr, 36)
        t7 = rotacionar_em_torno_do_eixo_y(tr, 108)
        t8 = rotacionar_em_torno_do_eixo_y(tr, 180)
        t9 = rotacionar_em_torno_do_eixo_y(tr, 252)
        t10 = rotacionar_em_torno_do_eixo_y(tr, 324)

        def triangulos_polares_norte():
            alpha = math.acos(1 / (2 * math.tan(math.pi / 5) * math.sqrt(0.75)))
            apotema = fator / (2 * math.tan(math.pi / 5))
            h = fator * math.sqrt(0.75)
            deslocamento = apotema - math.cos(alpha) * h / 2
            raio = fator / (2 * math.sin(math.pi / 5))
            theta = math.asin((raio - apotema) / fator)
            deslocamento_vertical = (math.cos(theta) * h / 2) + (math.sin(alpha) * h / 2)
            tr = [(x, 0, -y) for x, y in to]
            tr = [(x, math.sin(alpha) * -z + deslocamento_vertical,
                   z * math.cos(alpha) + deslocamento) for x, y, z in tr]
            return tr

        tr = triangulos_polares_norte()

        t11 = rotacionar_em_torno_do_eixo_y(tr, 36)
        t12 = rotacionar_em_torno_do_eixo_y(tr, 108)
        t13 = rotacionar_em_torno_do_eixo_y(tr, 180)
        t14 = rotacionar_em_torno_do_eixo_y(tr, 252)
        t15 = rotacionar_em_torno_do_eixo_y(tr, 324)

        def triangulos_polares_sul():
            alpha = math.acos(1 / (2 * math.tan(math.pi / 5) * math.sqrt(0.75)))
            apotema = fator / (2 * math.tan(math.pi / 5))
            h = fator * math.sqrt(0.75)
            deslocamento = apotema - math.cos(alpha) * h / 2
            raio = fator / (2 * math.sin(math.pi / 5))
            theta = math.asin((raio - apotema) / fator)
            deslocamento_vertical = (math.cos(theta) * h / 2) + (math.sin(alpha) * h / 2)
            t16 = [(x, 0, -y) for x, y in to]
            t16 = [(x, math.sin(alpha) * z - deslocamento_vertical,
                    z * math.cos(alpha) + deslocamento) for x, y, z in t16]
            return t16

        t16 = triangulos_polares_sul()
        t17 = rotacionar_em_torno_do_eixo_y(t16, 72)
        t18 = rotacionar_em_torno_do_eixo_y(t16, 144)
        t19 = rotacionar_em_torno_do_eixo_y(t16, 216)
        t20 = rotacionar_em_torno_do_eixo_y(t16, 288)
        return [t1, t2, t3, t4, t5, t6, t7, t8, t9, t10, t11, t12, t13, t14, t15, t16, t17, t18, t19, t20]

    def esfera(pontos, raio):

        def projetar_ponto_na_esfera(ponto, raio):
            x, y, z = ponto
            magnitude = math.sqrt(x ** 2 + y ** 2 + z ** 2)
            return (
                raio * x / magnitude,
                raio * y / magnitude,
                raio * z / magnitude
            )

        return [[projetar_ponto_na_esfera(ponto, raio) for ponto in lista] for lista in pontos]

    esfera = esfera(icosaedro(), fator)

    def poligonos():
        poligonos = []

        def ponto_por_linha():
            lista_pontos = [0]
            ppf = fator * 2 - 1
            una = fator * 2 - 1
            while una != 1:
                lista_pontos.append(ppf)
                ppf += una - 2
                una -= 2
            return lista_pontos

        p = ponto_por_linha()

        def hexagonos_centrais():
            hexagonos = []
            for t in esfera:
                i = 0
                for x in range(fator - 2, 0, -1):
                    for y in range(x):
                        hexagonos.append(numpy.array([
                            t[p[y] + i * 2 + 1],
                            t[p[y] + i * 2 + 2],
                            t[p[y] + i * 2 + 3],
                            t[p[y + 1] + i * 2 + 2],
                            t[p[y + 1] + i * 2 + 1],
                            t[p[y + 1] + i * 2]
                        ]))
                    i += 1
            return hexagonos

        poligonos.append(hexagonos_centrais())

        def hexagonos_tropicais_sul():
            hexagonos = []
            for x in range(5):
                for y in range(fator - 1):
                    hexagonos.append(numpy.array([
                        esfera[x][y * 2],
                        esfera[x][y * 2 + 1],
                        esfera[x][y * 2 + 2],
                        esfera[x + 15][y * 2 + 2],
                        esfera[x + 15][y * 2 + 1],
                        esfera[x + 15][y * 2]
                    ]))
            return hexagonos

        poligonos.append(hexagonos_tropicais_sul())

        def hexagonos_tropicais_norte():
            hexagonos = []
            for x in range(5, 10, 1):
                for y in range(fator - 1):
                    hexagonos.append(numpy.array([
                        esfera[x][y * 2],
                        esfera[x][y * 2 + 1],
                        esfera[x][y * 2 + 2],
                        esfera[x + 5][y * 2 + 2],
                        esfera[x + 5][y * 2 + 1],
                        esfera[x + 5][y * 2]
                    ]))
            return hexagonos

        poligonos.append(hexagonos_tropicais_norte())

        def hexagonos_equatoriais_ascendentes():
            hexagonos = []
            for x in range(5):
                for y in range(fator - 1):
                    if x == 0:
                        hexagonos.append(numpy.array([
                            esfera[x][p[y]],
                            esfera[x][p[y] + 1],
                            esfera[x][p[y + 1]],
                            esfera[x + 9][p[fator - y - 1] - 1],
                            esfera[x + 9][p[fator - y - 1] - 2],
                            esfera[x + 9][p[fator - y - 1] + 2 * y]
                        ]))
                    else:
                        hexagonos.append(numpy.array([
                            esfera[x][p[y]],
                            esfera[x][p[y] + 1],
                            esfera[x][p[y + 1]],
                            esfera[x + 4][p[fator - y - 1] - 1],
                            esfera[x + 4][p[fator - y - 1] - 2],
                            esfera[x + 4][p[fator - y - 1] + 2 * y]
                        ]))
            return hexagonos

        poligonos.append(hexagonos_equatoriais_ascendentes())

        def hexagonos_equatoriais_descendentes():
            hexagonos = []
            for x in range(5):
                for y in range(fator - 1):
                    hexagonos.append(numpy.array([
                        esfera[x][p[fator - 1 - y] + 2 * y],
                        esfera[x][p[fator - 1 - y] - 2],
                        esfera[x][p[fator - 1 - y] - 1],
                        esfera[x + 5][p[y + 1]],
                        esfera[x + 5][p[y] + 1],
                        esfera[x + 5][p[y]]
                    ]))
            return hexagonos

        poligonos.append(hexagonos_equatoriais_descendentes())

        def hexagonos_polares_norte():
            hexagonos = []
            for x in range(10, 15, 1):
                for y in range(fator - 1):
                    if x == 10:
                        hexagonos.append(numpy.array([
                            esfera[x][p[y]],
                            esfera[x][p[y] + 1],
                            esfera[x][p[y + 1]],
                            esfera[x + 4][p[y + 1] + (fator - y - 2) * 2],
                            esfera[x + 4][p[y + 1] - 2],
                            esfera[x + 4][p[y + 1] - 1]
                        ]))
                    else:
                        hexagonos.append(numpy.array([
                            esfera[x][p[y]],
                            esfera[x][p[y] + 1],
                            esfera[x][p[y + 1]],
                            esfera[x - 1][p[y + 1] + (fator - y - 2) * 2],
                            esfera[x - 1][p[y + 1] - 2],
                            esfera[x - 1][p[y + 1] - 1]
                        ]))
            return hexagonos

        poligonos.append(hexagonos_polares_norte())

        def hexagonos_polares_sul(): # Internodulares polares norte (ou sul)
            hexagonos = []
            for x in range(15, 20):
                for y in range(fator - 1):
                    if x == 15:
                        hexagonos.append(numpy.array([
                            esfera[x][p[y]],
                            esfera[x][p[y] + 1],
                            esfera[x][p[y + 1]],
                            esfera[x + 4][p[y + 1] + (fator - y - 2) * 2],
                            esfera[x + 4][p[y + 1] - 2],
                            esfera[x + 4][p[y + 1] - 1]
                        ]))
                    else:
                        hexagonos.append(numpy.array([
                            esfera[x][p[y]],
                            esfera[x][p[y] + 1],
                            esfera[x][p[y + 1]],
                            esfera[x - 1][p[y + 1] + (fator - y - 2) * 2],
                            esfera[x - 1][p[y + 1] - 2],
                            esfera[x - 1][p[y + 1] - 1]
                        ]))
            return hexagonos

        poligonos.append(hexagonos_polares_sul())

        def pentagonos():

            pentagonos = []

            def pentagonos_tropicais_sul():
                pentagonos = []
                for x in range(5):
                    if x == 0:
                        pentagonos.append(numpy.array([
                            esfera[0][0],
                            esfera[9][p[fator - 1]],
                            esfera[4][p[1] - 1],
                            esfera[19][p[1] - 1],
                            esfera[15][0]
                        ]))
                    else:
                        pentagonos.append(numpy.array([
                            esfera[x][0],
                            esfera[x + 4][p[fator - 1]],
                            esfera[x - 1][p[1] - 1],
                            esfera[x + 14][p[1] - 1],
                            esfera[x + 15][0]
                        ]))
                return pentagonos

            pentagonos.extend(pentagonos_tropicais_sul())

            def pentagonos_tropicais_norte():
                pentagonos = []
                for x in range(5):
                    if x == 0:
                        pentagonos.append(numpy.array([
                            esfera[0][p[fator - 1]],
                            esfera[5][0],
                            esfera[10][0],
                            esfera[14][p[1] - 1],
                            esfera[9][p[1] - 1]
                        ]))
                    else:
                        pentagonos.append(numpy.array([
                            esfera[x][p[fator - 1]],
                            esfera[x + 5][0],
                            esfera[x + 10][0],
                            esfera[x + 9][p[1] - 1],
                            esfera[x + 4][p[1] - 1]
                        ]))
                return pentagonos

            pentagonos.extend(pentagonos_tropicais_norte())

            def pentagono_polo_norte():
                polo_norte = numpy.array([
                    esfera[10][p[fator - 1]],
                    esfera[11][p[fator - 1]],
                    esfera[12][p[fator - 1]],
                    esfera[13][p[fator - 1]],
                    esfera[14][p[fator - 1]]
                ])
                return polo_norte

            pentagonos.append(pentagono_polo_norte())

            def pentagono_polo_sul():
                polo_sul = numpy.array([
                    esfera[15][p[fator - 1]],
                    esfera[16][p[fator - 1]],
                    esfera[17][p[fator - 1]],
                    esfera[18][p[fator - 1]],
                    esfera[19][p[fator - 1]]
                ])
                return polo_sul

            pentagonos.append(pentagono_polo_sul())

            return pentagonos

        poligonos.append(pentagonos())

        return poligonos

    poligonos = poligonos()

    def dic_pol():
        coord_vert = {}
        h = 0
        for x in range(5): # hexágonos equatoriais centrais
            for i, z in enumerate(range(fator - 2, 0, -1)):
                n = fator * 2 - 1
                for a in range(z):
                    coord_vert[(n - a, fator * x + i + 1)] = poligonos[0][h]
                    h += 1

        for x in range(5): # hexágonos equatoriais centrais invertidos
            for i, z in enumerate(range(fator - 2, 0, -1)):
                n = fator + 1
                for a in range(z):
                    coord_vert[(n + a, fator * x + 2 + i + a)] = numpy.flipud(poligonos[0][h])
                    h += 1

        for x in range(5): # hexágonos polares centrais norte
            for i, z in enumerate(range(fator - 2, 0, -1)):
                n = fator - 1
                for a in range(z):
                    coord_vert[(n - a, fator * x + 1 - x * (a + 1) + i)] = poligonos[0][h]
                    h += 1

        for x in range(5): # hexágonos polares centrais sul
            b = fator * x + 1 - x
            for i, z in enumerate(range(fator - 2, 0, -1)):
                n = fator * 2 + 1
                for a in range(z):
                    coord_vert[(n + a, b + i - a * x)] = numpy.flipud(poligonos[0][h])
                    h += 1
        h = 0
        for x in range(5): # hexágonos tropicais sul
            for z in range(fator - 1):
                coord_vert[(fator * 2, fator * x + z + 1)] = numpy.flipud(poligonos[1][h])
                h += 1
        h = 0
        for x in range(5): # hexágonos tropicais norte
            for z in range(fator - 1):
                coord_vert[(fator, fator * x + z + 1)] = poligonos[2][h]
                h += 1
        h = 0
        for x in range(5): # internodular equatorial descendente
            for z in range(fator - 1):
                coord_vert[(fator * 2 - z - 1, fator * x)] = poligonos[3][h]
                h += 1
        h = 0
        for x in range(5): # internodular equatorial ascendente
            for z in range(fator - 1):
                coord_vert[(fator + z + 1, fator * x + z + 1)] = poligonos[4][h]
                h += 1
        h = 0
        for x in range(5): # internodular polar norte
            for z in range(fator - 1):
                coord_vert[(fator - z - 1, (fator - z - 1) * x)] = poligonos[5][h]
                h += 1
        h = 0
        for x in range(5): # internodular polar sul
            for i, z in enumerate(range(fator - 1, 0, -1)):
                coord_vert[(fator * 2 + i + 1, z * x)] = numpy.flipud(poligonos[6][h])
                h += 1
        h = 0
        for x in range(5): # pentágonos tropicais sul
            coord_vert[(fator * 2, fator * x)] = poligonos[7][h]
            h += 1
        for x in range(5):  # pentágonos tropicais norte
            coord_vert[(fator, fator * x)] = poligonos[7][h]
            h += 1
        coord_vert[(0, 0)] = poligonos[7][h] # polo norte
        h += 1
        coord_vert[(fator * 3, 0)] = numpy.flipud(poligonos[7][h]) # polo sul

        return coord_vert

    coord_vert = dic_pol() # Chamando a função interna para obter o dicionário final

    # Cálculo dos Centros 3D
    centros_3d_tiles = {}
    for coords, vertices_np in coord_vert.items(): # Itera sobre o dicionário gerado por dic_pol
        if hasattr(vertices_np, 'size') and vertices_np.size > 0:
            # Calcula o centro médio dos vértices 3D do polígono
            # O 'vertices_np' é um array numpy com shape (N, 3), onde N é o número de vértices
            # Podemos usar as funções do numpy para calcular a média dos eixos X, Y, Z
            centro_3d_np = numpy.mean(vertices_np, axis=0) # Média ao longo do eixo das coordenadas (3)
            # Converte o resultado do numpy para um vec3 do glm para consistência com o resto do projeto
            centro_3d = glm.vec3(centro_3d_np[0], centro_3d_np[1], centro_3d_np[2])
            centros_3d_tiles[coords] = centro_3d
        else:
            print(f"[polygons.py] Aviso: Tile {coords} tem vértices inválidos ou vazios. Centro não calculado.")
            centros_3d_tiles[coords] = None # Ou poderia omitir esta chave

    # Retorna ambos os dicionários
    return coord_vert, centros_3d_tiles