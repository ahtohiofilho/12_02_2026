# core/planet.py

from __future__ import annotations
import random
import uuid
import networkx as nx
from typing import Optional

from config import CIV_CORES
from core.diplomacy import DiplomacyMatrix
from core.economy.adapters.planet_adapter import PlanetEconomyAdapter
from core.economy.market import MarketSystem
from core.economy.production import process_production_queue
from core.economy.province_repo import ProvinceEconomyRepository
from core.production.repo import ProductionQueueRepository
from core.stacks import StackRepository
from core.turn_engine import TurnEngine
from core.workforce.repo import WorkforceRepository
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

        # --- Etapa 3: Criação das Civilizações (Lógica Corrigida) ---
        print(" -> Etapa 3: Preparando para criar civilizações...")

        # === PASSO 1: INICIALIZAR O MAPA VAZIO ===
        # O mapa DEVE existir ANTES da criação das civilizações, pois elas o consultam.
        self.provinces_by_tile: dict[tuple[int, int], 'Province'] = {}
        print("[Planet] Mapa de províncias por tile inicializado (vazio).")

        # Agora, crie as civilizações. O construtor delas pode acessar o mapa vazio sem erro.
        self.civilizations: list[Civilization] = []
        self._create_initial_civilizations()
        print(f" -> Civilizações concluídas. {len(self.civilizations)} nações foram fundadas.")

        # === PASSO 2: POPULAR O MAPA EXISTENTE ===
        # Agora que as províncias foram criadas dentro das civilizações, popule o mapa.
        for civ in self.civilizations:
            for prov in civ.provinces:
                self.provinces_by_tile[prov.tile_coords] = prov
        print(f"[Planet] Mapa de províncias por tile populado com {len(self.provinces_by_tile)} entradas.")

        # --- Etapa 4: Runtime Systems (modular / plugável) ---
        self.diplomacy = DiplomacyMatrix()
        self.stacks = StackRepository()
        self.econ_repo = ProvinceEconomyRepository()
        self.economy = MarketSystem(world=PlanetEconomyAdapter(self, self.econ_repo))
        self.production_queues = ProductionQueueRepository()
        self.workforce_repo = WorkforceRepository()

        self._bootstrap_economy()

        if spawn_initial_units:
            self._spawn_initial_stacks()

        self.turn_engine = TurnEngine(
            stacks=self.stacks,
            diplomacy=self.diplomacy,
        )
        print("\nObjeto Planeta criado e pronto para uso.")

    def process_production(self) -> list[dict]:
        """
        Processa a fila de produção para todas as províncias que têm uma.
        Esta função deve ser chamada a cada turno.
        """
        reports = []

        def add_unit_to_stack_fn(unit_key: str, tile: tuple[int, int]):
            """Cria uma unidade militar no mapa a partir da produção."""
            province = self.get_province(tile) # Usando o método corrigido
            if not province or not province.owner:
                print(f"⚠️ Impossível produzir unidade em {tile}: província ou dono não encontrados.")
                return

            owner_id = province.owner.id
            target_stack = None
            for s in self.stacks.stacks_in_tile(tile):
                if s.owner_id == owner_id:
                    target_stack = s
                    break

            if target_stack is None:
                target_stack = self.stacks.create_stack(owner_id=owner_id, tile=tile)

            self.stacks.add_unit_to_stack(target_stack.uid, unit_key)
            print(f"🏭 Unidade '{unit_key}' produzida em {tile} para civ {owner_id}")

        tiles_com_fila = list(self.production_queues._by_tile.keys())
        for tile in tiles_com_fila:
            prov_queue = self.production_queues.ensure(tile)
            econ_state = self.econ_repo.get(tile)
            workforce_state = self.workforce_repo.get(tile)

            if not prov_queue.items or not econ_state or not workforce_state:
                continue

            def remove_first_item_from_queue():
                prov_queue.items.pop(0)

            report = process_production_queue(
                econ=econ_state,
                queue_items=prov_queue.items,
                remove_first_fn=remove_first_item_from_queue,
                food_pref=workforce_state.food_pref,
                add_unit_fn=add_unit_to_stack_fn
            )

            if report.get("produced"):
                reports.append(report)

        return reports

    @property
    def player_civ(self) -> Optional[Civilization]:
        """
        Propriedade de atalho para retornar a civilização do jogador.
        Por convenção, é sempre a primeira da lista.
        """
        return self.civilizations[0] if self.civilizations else None

    def _bootstrap_economy(self) -> None:
        """
        Cria estados econômicos iniciais para as províncias existentes.
        """
        from config.economy import WORKERS_CAPITAL_INICIAL
        from core.economy.production import init_province_economy

        for tile, province in self.provinces_by_tile.items():
            node_data = self.graph.nodes.get(tile, {})
            biome = node_data.get("bioma", "Meadow")
            fertility = node_data.get("fertilidade", 3.0)
            plate = node_data.get("placa", "Unknown")
            workers = WORKERS_CAPITAL_INICIAL if province.is_capital else 0

            state = init_province_economy(
                tile=tile,
                biome=biome,
                fertility=fertility,
                tectonic_plate=plate,
                workers=workers,
            )
            self.econ_repo.upsert(state)

    def _create_initial_civilizations(self) -> None:
        if not self.capitals:
            print("⚠️  AVISO: Nenhuma capital disponível para criar civilizações.")
            return

        rng = random.Random(self.geography_seed + 1)
        civ_names = list(CIV_CORES.keys())
        rng.shuffle(civ_names)

        for i, capital_coords in enumerate(self.capitals):
            if i >= len(civ_names):
                print(f"⚠️ AVISO: Mais capitais ({len(self.capitals)}) do que nomes. Algumas não serão criadas.")
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
        return self.graph.nodes.get(polygon_2d_coords)

    def get_province(self, tile: tuple[int, int]) -> Optional['Province']:
        """Retorna o objeto Province no tile especificado, ou None se não houver."""
        return self.provinces_by_tile.get(tile)

