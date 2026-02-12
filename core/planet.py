import networkx as nx
import numpy as np

# Importa as funções de trabalho pesado dos nossos módulos internos
from .generation._polygons import dicionario_poligonos
from .generation._geography import definir_geografia


class Planet:
    """
    Representa um único objeto de planeta. A geração da estrutura complexa
    é orquestrada aqui, chamando módulos de geração dedicados.
    """

    def __init__(self, n, starting_biome="Meadow"):
        """
        Construtor do Planeta. Orquestra a geração procedural.

        Args:
            n (int): O "fator" para o poliedro de Goldberg (n, 0).
            starting_biome (str): O bioma preferencial para iniciar civilizações.
        """
        print(f"Instanciando novo objeto Planeta com n={n}...")

        self.n = n
        self.starting_biome = starting_biome

        # --- Etapa 1: Geração Geométrica ---
        # Chama a função do módulo _polygons para gerar a geometria base.
        # Ela retorna um dicionário de polígonos (coordenadas 2D -> vértices 3D)
        # e um dicionário com os centros 3D de cada polígono.
        print(" -> Etapa 1: Gerando geometria dos polígonos...")
        polygons_map, centers_map = dicionario_poligonos(fator=self.n)

        # Armazena os resultados como atributos do objeto
        self.polygons_map = polygons_map
        self.centers_map = centers_map

        # Para a renderização, precisamos de uma lista única de todos os vértices.
        # Vamos extraí-la do dicionário de polígonos.
        all_vertices_set = set()
        for vertices_array in self.polygons_map.values():
            for vertex_tuple in vertices_array:
                # Arredondar para evitar duplicatas por imprecisão de float
                rounded_vertex = tuple(round(coord, 8) for coord in vertex_tuple)
                all_vertices_set.add(rounded_vertex)

        self.all_vertices = list(all_vertices_set)
        print(f" -> Geometria concluída: {len(self.polygons_map)} polígonos, {len(self.all_vertices)} vértices únicos.")

        # --- Etapa 2: Geração Geográfica e Lógica ---
        # Chama a função do módulo _geography para construir o grafo
        # e preenchê-lo com dados de bioma, placas, etc.
        print(" -> Etapa 2: Construindo grafo e definindo geografia...")
        graph, capitals = definir_geografia(
            poligonos=self.polygons_map,
            fator=self.n,
            bioma=self.starting_biome
        )

        # Armazena os resultados finais
        self.graph = graph
        self.capitals = capitals
        print(f" -> Geografia concluída. Grafo com {self.graph.number_of_nodes()} nós.")
        print(f" -> {len(self.capitals)} capitais iniciais selecionadas.")

        print("\nObjeto Planeta criado e pronto para uso.")

    def get_polygon_data(self, polygon_2d_coords):
        """ Retorna os dados de um polígono específico do grafo. """
        if self.graph.has_node(polygon_2d_coords):
            return self.graph.nodes[polygon_2d_coords]
        return None

