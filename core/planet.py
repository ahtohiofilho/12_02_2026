# core/planet.py

from __future__ import annotations
import random
import uuid
import networkx as nx
from typing import Optional

from config import CIV_CORES
from core.diplomacy import DiplomacyMatrix, Relation
from core.economy.adapters.planet_adapter import PlanetEconomyAdapter
from core.economy.market import MarketSystem
from core.economy.production import process_production_queue, apply_province_income
from core.economy.province_repo import ProvinceEconomyRepository
from core.production.repo import ProductionQueueRepository
from core.stacks import StackRepository
from core.turn_engine import TurnEngine
from core.workforce.repo import WorkforceRepository
from .civilization import Civilization, Province
from .generation._geography import definir_geografia, seed_from_planet_id
from .generation._polygons import dicionario_poligonos
from core.commands.manager import CommandManager


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

        graph, capitals_players, capitals_neutrals = definir_geografia(
            poligonos=self.polygons_map,
            fator=self.fator,
            bioma=self.starting_biome,
            seed=self.geography_seed,
        )

        self.graph: nx.DiGraph = graph
        self.capitals_players: list[tuple[int, int]] = list(capitals_players or [])
        self.capitals_neutrals: list[tuple[int, int]] = list(capitals_neutrals or [])
        self.capitals: list[tuple[int, int]] = self.capitals_players + self.capitals_neutrals

        print(f" -> Geografia concluída. Grafo com {self.graph.number_of_nodes()} nós.")
        print(
            f" -> Capitais: {len(self.capitals_players)} players + "
            f"{len(self.capitals_neutrals)} neutras = {len(self.capitals)} total."
        )

        # --- Etapa 3: Criação das Civilizações (Lógica Corrigida) ---
        print(" -> Etapa 3: Preparando para criar civilizações...")

        # O mapa DEVE existir ANTES da criação das civilizações, pois elas o consultam.
        self.provinces_by_tile: dict[tuple[int, int], 'Province'] = {}
        print("[Planet] Mapa de províncias por tile inicializado (vazio).")

        self.civilizations: list[Civilization] = []
        self._create_initial_civilizations()
        print(f" -> Civilizações concluídas. {len(self.civilizations)} nações foram fundadas.")

        # Popula o mapa de províncias por tile (redundante mas ok; o construtor já insere a capital)
        for civ in self.civilizations:
            for prov in civ.provinces:
                self.provinces_by_tile[prov.tile_coords] = prov
        print(f"[Planet] Mapa de províncias por tile populado com {len(self.provinces_by_tile)} entradas.")

        # --- Etapa 4: Runtime Systems (modular / plugável) ---
        self.diplomacy = DiplomacyMatrix()

        # NOVO: diplomacia inicial (players em guerra entre si; neutras neutras)
        self._init_starting_diplomacy()

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

        self.command_manager = CommandManager(
            graph=self.graph,
            stacks=self.stacks,
            turn_engine=self.turn_engine,
        )
        print("\nObjeto Planeta criado e pronto para uso.")

    def process_production(self) -> list[dict]:
        reports: list[dict] = []

        # ============================================================
        # 1) PRODUÇÃO DA FILA (gasta o saldo acumulado do turno que passou)
        # ============================================================
        def add_unit_to_stack_fn(unit_key: str, tile: tuple[int, int]):
            province = self.get_province(tile)
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
                add_unit_fn=add_unit_to_stack_fn,
            )

            if (report.get("completed_items", 0) or 0) > 0 or (report.get("paid_total", 0.0) or 0.0) > 0:
                reports.append(report)


        # ============================================================
        # 2) RECEITA DO TURNO (gera a grana que será gasta no PRÓXIMO turno)
        # ============================================================
        try:
            # calcula comércio/receitas do turno
            resultado = self.economy.calcular_equilibrio(forcar_recalculo=True)

            # aplica (commit) no treasury de cada ProvinceEconomyState
            # (requer: core.economy.production.apply_province_income)
            income_reports = apply_province_income(self.econ_repo, resultado)

            # opcional: anexar ao retorno (para debug/UI)
            # reports.extend({"income": r} for r in income_reports)
        except Exception as e:
            # não quebra o turno se economia falhar; só não deposita receita
            print(f"⚠️ [Planet.process_production] Falha ao aplicar receita do turno: {e}")


        return reports


    @property
    def player_civ(self) -> Optional[Civilization]:
        # Convenção: civilização 0 é do jogador humano
        return self.civilizations[0] if self.civilizations else None

    def _bootstrap_economy(self) -> None:
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
        """
        Cria civilizações na ordem:
          1) players (capitals_players)  -> is_player=True
          2) neutras (capitals_neutrals) -> is_player=False

        Mantém id=0 como "player humano" por convenção (primeiro player).
        """
        if not self.capitals_players and not self.capitals_neutrals:
            print("⚠️  AVISO: Nenhuma capital disponível para criar civilizações.")
            return

        rng = random.Random(self.geography_seed + 1)
        civ_names = list(CIV_CORES.keys())
        rng.shuffle(civ_names)

        # players primeiro
        idx = 0
        for capital_coords in self.capitals_players:
            if idx >= len(civ_names):
                print("⚠️ AVISO: Sem nomes suficientes para todas as civs (players).")
                break

            civ_name = civ_names[idx]
            civ_color = CIV_CORES[civ_name]
            self.civilizations.append(
                Civilization(
                    planeta=self,
                    id=idx,
                    name=civ_name,
                    color=civ_color,
                    capital_coords=capital_coords,
                    is_player=True,
                )
            )
            idx += 1

        # neutras depois
        for capital_coords in self.capitals_neutrals:
            if idx >= len(civ_names):
                print("⚠️ AVISO: Sem nomes suficientes para todas as civs (neutras).")
                break

            civ_name = civ_names[idx]
            civ_color = CIV_CORES[civ_name]
            self.civilizations.append(
                Civilization(
                    planeta=self,
                    id=idx,
                    name=civ_name,
                    color=civ_color,
                    capital_coords=capital_coords,
                    is_player=False,
                )
            )
            idx += 1

    def _init_starting_diplomacy(self) -> None:
        """
        Política inicial (como no antigo):
          - Players começam em guerra entre si (ENEMY)
          - Neutras ficam NEUTRAL com todo mundo
        """
        players = [c for c in self.civilizations if getattr(c, "is_player", True)]
        # Se você quiser: neutras aliadas entre si, etc., mude aqui.

        wars_declared = 0
        for i in range(len(players)):
            for j in range(i + 1, len(players)):
                self.diplomacy.set_relation(players[i].id, players[j].id, Relation.ENEMY)
                wars_declared += 1

        if wars_declared:
            print(f"⚔️ [Planet] {wars_declared} guerras declaradas entre players.")

    def _spawn_initial_stacks(self) -> None:
        for civ in self.civilizations:
            s = self.stacks.create_stack(owner_id=civ.id, tile=civ.capital_coords)
            self.stacks.add_unit_to_stack(s.uid, "infantry")

    def get_polygon_data(self, polygon_2d_coords):
        return self.graph.nodes.get(polygon_2d_coords)

    def get_province(self, tile: tuple[int, int]) -> Optional['Province']:
        return self.provinces_by_tile.get(tile)
