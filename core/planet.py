# core/planet.py
from __future__ import annotations

import random
import uuid
from typing import Any, Optional

import networkx as nx

from config import CIV_CORES
from config.civilization import CULTURAS

from core.commands.manager import CommandManager
from core.commands.models import CommandType  # ✅ NOVO: usado no callback attack_orders_for_tile
from core.diplomacy import DiplomacyMatrix, Relation

from core.economy.adapters.planet_adapter import PlanetEconomyAdapter
from core.economy.market_realistic import MarketSystemRealistic
from core.economy.production import apply_province_income, process_production_queue
from core.economy.province_repo import ProvinceEconomyRepository

from core.generation._geography import seed_from_planet_id, definir_geografia
from core.production.repo import ProductionQueueRepository

from core.stacks import StackRepository
from core.turn_engine import TurnEngine

from core.visibility import VisibilityManager
from core.workforce.repo import WorkforceRepository

from .civilization import Civilization, Province
from .generation._polygons import dicionario_poligonos



Tile = tuple[int, int]


class Planet:
    """
    Representa um único objeto de planeta. A geração da estrutura complexa
    é orquestrada aqui, chamando módulos de geração dedicados.

    Consolida:
      - economia global com custos dirigidos por vendedor (FoW + diplomacia + bloqueio militar)
      - rastreio de bloqueio militar por tile com atraso >= 1 turno (presente agora e no turno anterior)
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

        # Nomes de província usados no planeta (para unicidade)
        self.used_province_names: set[str] = set()

        # ============================================================
        # Versões (cache / invalidação)
        # ============================================================
        self.economy_version: int = 0
        self.diplomacy_version: int = 0
        self.visibility_version_sum: int = 0

        # ============================================================
        # Trade blocking (militar) — estado por turno
        # ============================================================
        Tile = tuple[int, int]
        self.trade_block_prev: dict[Tile, dict[str, set[int]]] = {}
        self.trade_block_now: dict[Tile, dict[str, set[int]]] = {}
        self.trade_blocked_tiles_by_civ: dict[int, set[Tile]] = {}
        self.trade_block_version: int = 0

        # ============================================================
        # Visibilidade por rotas comerciais ativas
        # ============================================================
        self.trade_route_tiles_by_civ: dict[int, set[Tile]] = {}
        self.trade_route_visibility_version: int = 0

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
        self.capitals_players: list[Tile] = list(capitals_players or [])
        self.capitals_neutrals: list[Tile] = list(capitals_neutrals or [])
        self.capitals: list[Tile] = self.capitals_players + self.capitals_neutrals

        print(f" -> Geografia concluída. Grafo com {self.graph.number_of_nodes()} nós.")
        print(
            f" -> Capitais: {len(self.capitals_players)} players + "
            f"{len(self.capitals_neutrals)} neutras = {len(self.capitals)} total."
        )

        # --- Etapa 3: Criação das Civilizações ---
        print(" -> Etapa 3: Preparando para criar civilizações...")

        self.provinces_by_tile: dict[Tile, Province] = {}
        print("[Planet] Mapa de províncias por tile inicializado (vazio).")

        self.civilizations: list[Civilization] = []
        self._create_initial_civilizations()
        print(f" -> Civilizações concluídas. {len(self.civilizations)} nações foram fundadas.")

        for civ in self.civilizations:
            for prov in civ.provinces:
                self.provinces_by_tile[prov.tile_coords] = prov
        print(f"[Planet] Mapa de províncias por tile populado com {len(self.provinces_by_tile)} entradas.")

        # --- Etapa 4: Runtime Systems ---
        self.diplomacy = DiplomacyMatrix()
        self._init_starting_diplomacy()

        self.stacks = StackRepository()
        self.econ_repo = ProvinceEconomyRepository()

        self.economy = MarketSystemRealistic(
            planet=self,
            world=PlanetEconomyAdapter(self, self.econ_repo),
        )

        self.production_queues = ProductionQueueRepository()
        self.workforce_repo = WorkforceRepository()

        self._bootstrap_economy()

        if spawn_initial_units:
            self._spawn_initial_stacks()

        # ============================================================
        # TurnEngine + CommandManager (ordem ajustada + combate remoto)
        # ============================================================
        # Como CommandManager precisa de turn_engine no construtor, criamos TurnEngine primeiro,
        # mas sem o callback de ataque (ainda não existe command_manager).
        self.turn_engine = TurnEngine(
            stacks=self.stacks,
            diplomacy=self.diplomacy,
            biome_at=lambda t: (self.graph.nodes.get(t, {}).get("bioma") or "Meadow"),
            graph_provider=lambda: self.graph,  # ✅ habilita distâncias p/ combate remoto
            attack_orders_for_tile=None,  # será ligado logo após criar o CommandManager
        )

        self.command_manager = CommandManager(
            graph=self.graph,
            stacks=self.stacks,
            turn_engine=self.turn_engine,
            planet=self,
        )

        # Agora liga o callback (sem “pull”): só retorna stacks com ATTACK_TILE explícito para aquele tile
        def _attack_orders_for_tile(tile: Tile) -> list[dict[str, Any]]:
            out: list[dict[str, Any]] = []
            tile = (int(tile[0]), int(tile[1]))

            for cmd in self.command_manager.all_pending():
                if cmd.command_type != CommandType.ATTACK_TILE:
                    continue
                tt = cmd.target_tile() if hasattr(cmd, "target_tile") else cmd.extra.get("target_tile")
                if not tt:
                    continue
                tt = (int(tt[0]), int(tt[1]))
                if tt != tile:
                    continue

                out.append(
                    {
                        "stack_uid": cmd.stack_uid,
                        "owner_civ_id": int(cmd.owner_civ_id),
                        "evasion_mode": (
                            cmd.evasion_mode() if hasattr(cmd, "evasion_mode") else cmd.extra.get("evasion_mode",
                                                                                                  "COMMITTED")),
                        "target_layer": cmd.extra.get("target_layer"),
                    }
                )
            return out

        self.turn_engine.attack_orders_for_tile = _attack_orders_for_tile

        # --- Visibilidade / bloqueio / pós-init ---
        self.visibility = VisibilityManager(self)
        self.visibility.update_all_civs()

        self.update_military_block_state()

        try:
            self.trade_route_tiles_by_civ = {int(c.id): set() for c in self.civilizations}
        except Exception:
            self.trade_route_tiles_by_civ = {}

        print("\nObjeto Planeta criado e pronto para uso.")

    def recompute_trade_route_visibility(self, *, min_quantity: float = 1e-6) -> None:
        """
        Recalcula tiles que devem ficar VISÍVEIS na UI por causa de rotas comerciais ativas.

        Regra (anti-leak):
          - Só conta rotas em que a província de origem OU destino pertence à civ.
          - Usa caminhos do MarketSystemRealistic (origem->destino) já calculados no turno.
          - Se não houver caminho, ignora.
        """
        tiles_by_civ: dict[int, set[Tile]] = {int(c.id): set() for c in self.civilizations}

        results = self.economy.calcular_equilibrio()  # usa cache se já calculado neste turno
        if not results:
            self.trade_route_tiles_by_civ = tiles_by_civ
            self.trade_route_visibility_version += 1
            return

        # helper: registra caminho para civs relevantes
        def add_path_for(civ_ids: set[int], path: list[Tile] | None):
            if not path:
                return
            # normaliza para tuple
            norm = []
            for t in path:
                if isinstance(t, list):
                    norm.append((int(t[0]), int(t[1])))
                else:
                    norm.append((int(t[0]), int(t[1])))
            for cid in civ_ids:
                tiles_by_civ[int(cid)].update(norm)

        flux_sources = (results.fluxos_alimento or {}, results.fluxos_minerio or {})
        for fluxes in flux_sources:
            for _resource_name, flux_dict in fluxes.items():
                for seller_tile, buyer_dict in flux_dict.items():
                    for buyer_tile, qty in buyer_dict.items():
                        if float(qty or 0.0) <= float(min_quantity):
                            continue

                        prov_s = self.get_province(seller_tile)
                        prov_b = self.get_province(buyer_tile)
                        if not prov_s or not prov_s.owner or not prov_b or not prov_b.owner:
                            continue

                        seller_civ = int(prov_s.owner.id)
                        buyer_civ = int(prov_b.owner.id)

                        # Só revela para participantes da rota
                        civs = {seller_civ, buyer_civ}

                        path = self.economy.get_caminho_rota(seller_tile, buyer_tile)
                        add_path_for(civs, path)

        if tiles_by_civ != getattr(self, "trade_route_tiles_by_civ", None):
            self.trade_route_tiles_by_civ = tiles_by_civ
            self.trade_route_visibility_version += 1

    # ============================================================
    # Economia: produção / renda
    # ============================================================

    def process_production(self) -> list[dict]:
        reports: list[dict] = []

        # ============================================================
        # 1) PRODUÇÃO DA FILA (gasta o saldo acumulado do turno que passou)
        # ============================================================
        def add_unit_to_stack_fn(unit_key: str, tile: Tile):
            province = self.get_province(tile)
            if not province or not province.owner:
                print(f"⚠️ Impossível produzir unidade em {tile}: província ou dono não encontrados.")
                return

            owner_id = province.owner.id

            # Unidades militares vão para stack mista (não-worker)
            target_stack = None
            for s in self.stacks.stacks_in_tile(tile):
                if s.owner_id == owner_id and not all(u.unit_key == "worker" for u in s.units):
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

            # ── DETACH_WORKER: resolve antes do processamento monetário ──
            from core.production.queue import QueueItemType
            from core.workforce.facade import ProvinceWorkforceFacade

            i = 0
            while i < len(prov_queue.items):
                item = prov_queue.items[i]
                if item.item_type != QueueItemType.DETACH_WORKER:
                    i += 1
                    continue

                # Remove da fila independentemente do resultado
                prov_queue.items.pop(i)

                province = self.get_province(tile)
                if province is None:
                    print(f"⚠️ [process_production] DETACH_WORKER descartado em {tile}: província não existe.")
                    continue

                facade = ProvinceWorkforceFacade(planet=self, province=province)
                ok = facade.detach_worker()

                if ok:
                    reports.append({"tile": tile, "produced": "worker_detached"})
                    print(f"✅ [process_production] Worker destacado em {tile}.")
                    # mudanças econômicas/produção -> invalida economia global
                    self.economy_version += 1
                else:
                    print(f"⚠️ [process_production] DETACH_WORKER cancelado em {tile}: workers insuficientes.")
                # não incrementa i: o pop já avançou

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
                # produção pode alterar workers/output -> invalida
                self.economy_version += 1

        # ============================================================
        # 2) RECEITA DO TURNO (gera a grana que será gasta no PRÓXIMO turno)
        # ============================================================
        try:
            resultado = self.economy.calcular_equilibrio(forcar_recalculo=True)
            _income_reports = apply_province_income(self.econ_repo, resultado)
            # receita altera treasury (mas não necessariamente oferta/demanda no seu modelo),
            # então não incrementamos economy_version aqui por padrão.
        except Exception as e:
            print(f"⚠️ [Planet.process_production] Falha ao aplicar receita do turno: {e}")

        return reports

    # ============================================================
    # Trade blocking (militar) + passability por vendedor
    # ============================================================

    def update_military_block_state(self) -> None:
        """
        Atualiza bloqueio militar por tile com atraso >= 1 turno e por domínio:

        - Unidades NAVAL (militares) bloqueiam tiles aquáticos (Coast/Sea/Ocean)
        - Unidades LAND  (militares) bloqueiam tiles não aquáticos
        - Unidades AIR não bloqueiam
        - Unidades CIVILIAN não bloqueiam
        - Só bloqueia inimigos se a stack militar estiver presente agora E no turno anterior
        """
        from config.unit_stats import get_unit_stats, UnitCategory

        AQUATIC = {"Coast", "Sea", "Ocean"}

        # Snapshot atual: tile -> {"land": set(civs), "naval": set(civs)}
        now: dict[Tile, dict[str, set[int]]] = {}

        for tile, uids in self.stacks.stack_uids_by_tile.items():
            biome = self.graph.nodes.get(tile, {}).get("bioma", "")
            is_aquatic = biome in AQUATIC

            for uid in uids:
                stack = self.stacks.get_stack(uid)
                if not stack or stack.is_empty():
                    continue

                # Detecta se essa stack bloqueia (e em qual domínio, de acordo com o tile)
                blocks_land = False
                blocks_naval = False

                for u in stack.units:
                    st = get_unit_stats(u.unit_key)
                    if not st or st.is_non_combat:
                        continue

                    if st.category == UnitCategory.LAND and not is_aquatic:
                        blocks_land = True
                    elif st.category == UnitCategory.NAVAL and is_aquatic:
                        blocks_naval = True
                    # AIR não bloqueia

                if not (blocks_land or blocks_naval):
                    continue

                entry = now.setdefault(tile, {"land": set(), "naval": set()})
                if blocks_land:
                    entry["land"].add(int(stack.owner_id))
                if blocks_naval:
                    entry["naval"].add(int(stack.owner_id))

        prev = self.trade_block_now
        self.trade_block_prev = prev
        self.trade_block_now = now

        # Recalcula tiles bloqueados por civ (consulta rápida)
        blocked_by_civ: dict[int, set[Tile]] = {int(c.id): set() for c in self.civilizations}

        for tile, pres_now in now.items():
            pres_prev = prev.get(tile, {"land": set(), "naval": set()})

            # civs estacionadas >= 1 turno, por domínio
            stationed = set(pres_now.get("land", set())) & set(pres_prev.get("land", set()))
            stationed |= set(pres_now.get("naval", set())) & set(pres_prev.get("naval", set()))

            if not stationed:
                continue

            for controller_id in stationed:
                for civ in self.civilizations:
                    a = int(civ.id)
                    if a == controller_id:
                        continue
                    if self.diplomacy.relation(a, controller_id) == Relation.ENEMY:
                        blocked_by_civ[a].add(tile)

        if blocked_by_civ != self.trade_blocked_tiles_by_civ:
            self.trade_blocked_tiles_by_civ = blocked_by_civ
            self.trade_block_version += 1

    def trade_passable_tiles_for_seller(self, seller_civ_id: int) -> set[Tile]:
        """
        Tiles passáveis para comércio (como VENDEDOR):
          explored do vendedor
          + tiles das próprias províncias (permanente)
          - tiles de províncias inimigas
          - tiles bloqueados por militar inimigo (>= 1 turno) (tile-level)
        """
        seller_civ_id = int(seller_civ_id)

        # explored
        explored = set(self.visibility.get_state(seller_civ_id).explored)

        # garante: próprias províncias sempre são conhecidas e passáveis (exceto bloqueio militar)
        for tile, prov in self.provinces_by_tile.items():
            if prov.owner and int(prov.owner.id) == seller_civ_id:
                explored.add(tile)

        passable = set(explored)

        # remove províncias inimigas (tile do mercado inimigo não pode ser usado)
        for tile, prov in self.provinces_by_tile.items():
            if not prov.owner:
                continue
            owner_id = int(prov.owner.id)
            if owner_id == seller_civ_id:
                continue
            if self.diplomacy.relation(seller_civ_id, owner_id) == Relation.ENEMY:
                passable.discard(tile)

        # remove tiles bloqueados por militar inimigo (>= 1 turno)
        blocked = self.trade_blocked_tiles_by_civ.get(seller_civ_id)
        if blocked:
            passable -= set(blocked)

        return passable

    # ============================================================
    # Utilidades / bootstrap
    # ============================================================

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

        # economia inicial pronta => versão
        self.economy_version += 1

    def _create_initial_civilizations(self) -> None:
        """
        Cria civilizações na ordem:
          1) players (capitals_players)  -> is_player=True
          2) neutras (capitals_neutrals) -> is_player=False

        Mantém id=0 como "player humano" por convenção (primeiro player).

        Cultura:
          - 24 culturas em config.civilization.CULTURAS
          - determinístico por planeta: embaralha a lista com seed do planeta
        """
        if not self.capitals_players and not self.capitals_neutrals:
            print("⚠️  AVISO: Nenhuma capital disponível para criar civilizações.")
            return

        rng = random.Random(self.geography_seed + 1)

        civ_names = list(CIV_CORES.keys())
        rng.shuffle(civ_names)

        cultures = list(CULTURAS) if CULTURAS else ["English"]
        rng.shuffle(cultures)

        def culture_for_index(i: int) -> str:
            if not cultures:
                return "English"
            return cultures[i % len(cultures)]

        idx = 0

        # players primeiro
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
                    culture=culture_for_index(idx),
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
                    culture=culture_for_index(idx),
                )
            )
            idx += 1

    def _init_starting_diplomacy(self) -> None:
        """
        Política inicial:
          - Players começam em guerra entre si (ENEMY)
          - Neutras ficam NEUTRAL com todo mundo
        """
        players = [c for c in self.civilizations if getattr(c, "is_player", True)]

        wars_declared = 0
        for i in range(len(players)):
            for j in range(i + 1, len(players)):
                self.diplomacy.set_relation(players[i].id, players[j].id, Relation.ENEMY)
                wars_declared += 1

        if wars_declared:
            self.diplomacy_version += 1
            print(f"⚔️ [Planet] {wars_declared} guerras declaradas entre players.")

    def _spawn_initial_stacks(self) -> None:
        # OBS: seu unit_key correto parece ser "light_infantry" (não "infantry") em config.unit_stats.
        # Mantive "infantry" porque estava no seu código original.
        for civ in self.civilizations:
            s = self.stacks.create_stack(owner_id=civ.id, tile=civ.capital_coords)
            self.stacks.add_unit_to_stack(s.uid, "light_infantry")

    def get_polygon_data(self, polygon_2d_coords):
        return self.graph.nodes.get(polygon_2d_coords)

    def get_province(self, tile: Tile) -> Optional[Province]:
        return self.provinces_by_tile.get(tile)
