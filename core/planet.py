# core/planet.py

from __future__ import annotations

import random

import networkx as nx

from config import CIV_CORES
from core.diplomacy import DiplomacyMatrix
from core.stacks import StackRepository

from .civilization import Civilization, Province
from .generation._geography import definir_geografia
from .generation._polygons import dicionario_poligonos


class Planet:
    """
    Representa um único objeto de planeta. A geração da estrutura complexa
    é orquestrada aqui, chamando módulos de geração dedicados.

    Observação (arquitetura modular):
    - Planet guarda o "mundo" (mapa/grafo, civs, províncias).
    - Sistemas runtime plugáveis ficam como dependências: self.diplomacy, self.stacks.
      (as regras e o combate não ficam no Planet)
    """

    def __init__(self, n: int, starting_biome: str = "Meadow", *, spawn_initial_units: bool = False):
        """
        Construtor do Planeta. Orquestra a geração procedural.

        Args:
            n (int): O "fator" para o poliedro de Goldberg (n, 0).
            starting_biome (str): O bioma preferencial para iniciar civilizações.
            spawn_initial_units (bool): Se True, cria 1 stack + 1 unidade na capital de cada civ.
        """
        print(f"Instanciando novo objeto Planeta com n={n}...")

        self.n = int(n)
        self.starting_biome = starting_biome

        # --- Etapa 1: Geração Geométrica ---
        print(" -> Etapa 1: Gerando geometria dos polígonos...")
        polygons_map, centers_map = dicionario_poligonos(fator=self.n)

        self.polygons_map = polygons_map
        self.centers_map = centers_map

        # Para a renderização, precisamos de uma lista única de todos os vértices.
        all_vertices_set: set[tuple[float, float, float]] = set()
        for vertices_array in self.polygons_map.values():
            for vertex_tuple in vertices_array:
                rounded_vertex = tuple(round(float(coord), 8) for coord in vertex_tuple)
                all_vertices_set.add(rounded_vertex)

        self.all_vertices = list(all_vertices_set)
        print(
            f" -> Geometria concluída: {len(self.polygons_map)} polígonos, "
            f"{len(self.all_vertices)} vértices únicos."
        )

        # --- Etapa 2: Geração Geográfica e Lógica ---
        print(" -> Etapa 2: Construindo grafo e definindo geografia...")
        graph, capitals = definir_geografia(
            poligonos=self.polygons_map,
            fator=self.n,
            bioma=self.starting_biome,
        )

        self.graph: nx.DiGraph = graph
        self.capitals: list[tuple[int, int]] = capitals
        print(f" -> Geografia concluída. Grafo com {self.graph.number_of_nodes()} nós.")
        print(f" -> {len(self.capitals)} capitais iniciais selecionadas.")

        # --- Etapa 3: Criação das Civilizações / Províncias ---
        print(" -> Etapa 3: Criando civilizações iniciais...")
        self.civilizations: list[Civilization] = []
        self.provinces_by_tile: dict[tuple[int, int], Province] = {}
        self._create_initial_civilizations()
        print(f" -> Civilizações concluídas. {len(self.civilizations)} nações foram fundadas.")

        # --- Runtime Systems (modular / plugável) ---
        # Diplomacia e Stacks são storage; regras e combate vivem fora.
        self.diplomacy = DiplomacyMatrix()
        self.stacks = StackRepository()

        if spawn_initial_units:
            self._spawn_initial_stacks()

        print("\nObjeto Planeta criado e pronto para uso.")

    def _create_initial_civilizations(self) -> None:
        """
        Usa a lista de capitais para instanciar as Civilizações, usando os nomes
        e cores do dicionário CIV_CORES.
        """
        if not self.capitals:
            print("⚠️  AVISO: Nenhuma capital disponível para criar civilizações.")
            return

        civ_names = list(CIV_CORES.keys())
        random.shuffle(civ_names)

        for i, capital_coords in enumerate(self.capitals):
            if i >= len(civ_names):
                print(
                    f"⚠️ AVISO: Mais capitais ({len(self.capitals)}) do que nomes de civilização "
                    f"({len(civ_names)}). Algumas não serão criadas."
                )
                break

            civ_name = civ_names[i]
            civ_color = CIV_CORES[civ_name]

            new_civ = Civilization(
                planeta=self,
                id=i,
                name=civ_name,
                color=civ_color,
                capital_coords=capital_coords,
            )
            self.civilizations.append(new_civ)

    def _spawn_initial_stacks(self) -> None:
        """
        (Opcional) Cria 1 stack com 1 unidade "infantry" na capital de cada civ.
        Isso fica aqui só como conveniência de bootstrap.
        """
        for civ in self.civilizations:
            s = self.stacks.create_stack(owner_id=civ.id, tile=civ.capital_coords)
            self.stacks.add_unit_to_stack(s.uid, "infantry")

    def get_polygon_data(self, polygon_2d_coords):
        """Retorna os dados de um polígono específico do grafo."""
        if self.graph.has_node(polygon_2d_coords):
            return self.graph.nodes[polygon_2d_coords]
        return None
