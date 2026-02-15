# core/planet.py

from __future__ import annotations
import random
import uuid
import networkx as nx

from config import CIV_CORES
from core.diplomacy import DiplomacyMatrix
from core.economy.adapters.planet_adapter import PlanetEconomyAdapter
from core.economy.market import MarketSystem
from core.economy.province_repo import ProvinceEconomyRepository
from core.stacks import StackRepository
from core.turn_engine import TurnEngine
from .civilization import Civilization, Province
from .generation._geography import definir_geografia, seed_from_planet_id
from .generation._polygons import dicionario_poligonos


class Planet:
    """
    Representa um único objeto de planeta. A geração da estrutura complexa
    é orquestrada aqui, chamando módulos de geração dedicados.
    """

    def __init__(
        self,
        fator: int,
        starting_biome: str = "Meadow",
        *,
        spawn_initial_units: bool = False,
    ):
        print(f"Instanciando novo objeto Planeta com n={fator}...")
        self.id = str(uuid.uuid4())
        self.fator = int(fator)
        self.starting_biome = starting_biome
        self.geography_seed: int = seed_from_planet_id(self.id)

        # --- Etapa 1: Geração Geométrica ---
        print(" -> Etapa 1: Gerando geometria dos polígonos...")
        polygons_map, centers_map = dicionario_poligonos(fator=self.fator)
        self.polygons_map = polygons_map
        self.centers_map = centers_map
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
            fator=self.fator,
            bioma=self.starting_biome,
            seed=self.geography_seed,
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

        # --- Etapa 4: Runtime Systems (modular / plugável) ---
        self.diplomacy = DiplomacyMatrix()
        self.stacks = StackRepository()
        self.econ_repo = ProvinceEconomyRepository()
        self.economy = MarketSystem(world=PlanetEconomyAdapter(self, self.econ_repo))
        self._bootstrap_economy()
        if spawn_initial_units:
            self._spawn_initial_stacks()
        self.turn_engine = TurnEngine(
            stacks=self.stacks,
            diplomacy=self.diplomacy,
        )
        print("\nObjeto Planeta criado e pronto para uso.")

    @property
    def player_civ(self) -> Civilization | None:
        """
        Propriedade de atalho para retornar a civilização do jogador.
        Por convenção, é sempre a primeira da lista 'self.civilizations'.
        Retorna None se a lista estiver vazia.
        """
        if self.civilizations:
            return self.civilizations[0]
        return None

    def _bootstrap_economy(self) -> None:
        """
        Cria estados econômicos iniciais para as províncias existentes.
        """
        for tile in self.provinces_by_tile.keys():
            s = self.econ_repo.ensure(tile)
            s.workers = 100
            s.food_type = "Grain"
            s.food_output = 50.0
            s.ore_type = "Iron"
            s.ore_output = 10.0

    def _create_initial_civilizations(self) -> None:
        if not self.capitals:
            print("⚠️  AVISO: Nenhuma capital disponível para criar civilizações.")
            return

        rng = random.Random(self.geography_seed + 1)
        civ_names = list(CIV_CORES.keys())
        rng.shuffle(civ_names)

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
        """
        for civ in self.civilizations:
            s = self.stacks.create_stack(owner_id=civ.id, tile=civ.capital_coords)
            self.stacks.add_unit_to_stack(s.uid, "infantry")

    def get_polygon_data(self, polygon_2d_coords):
        """Retorna os dados de um polígono específico do grafo."""
        if self.graph.has_node(polygon_2d_coords):
            return self.graph.nodes[polygon_2d_coords]
        return None
