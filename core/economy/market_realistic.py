# core/economy/market_realistic.py
from __future__ import annotations

from typing import Optional
import networkx as nx

from core.economy.models import EconomyWorldView, ResultadoComercio, Tile
from core.economy.trade import TradeCalculator
from core.diplomacy import Relation

CUSTO_IMPOSSIVEL = 1e12


class MarketSystemRealistic:
    """
    Mercado global com acesso dirigido por vendedor (origem).

    Para cada origem (província vendedora), o custo origem->destino é calculado no subgrafo
    "passável para comércio" do DONO da origem:
      - explored do vendedor
      - menos províncias inimigas
      - menos tiles bloqueados por stacks militares inimigas estacionadas >= 1 turno
        (com regra de domínio: naval bloqueia aquático; land bloqueia terrestre)
    """

    def __init__(self, *, planet, world: EconomyWorldView):
        self.planet = planet
        self.world = world

        self.resultado_cache: Optional[ResultadoComercio] = None

        # origem -> destino -> caminho (para UI/overlay)
        self.rotas_caminhos: dict[Tile, dict[Tile, list[Tile] | None]] = {}

        # custo monetário por unidade: dist_dijkstra * fator
        self.fator_custo_transporte = 0.01

        # cache simples de versões (opcional, mas barato e útil)
        self._last_econ_ver: int = -1
        self._last_dip_ver: int = -1
        self._last_block_ver: int = -1
        self._last_vis_ver_sum: int = -1

    def invalidar_cache(self) -> None:
        self.resultado_cache = None

    def _versions(self) -> tuple[int, int, int, int]:
        econ_ver = int(getattr(self.planet, "economy_version", 0))
        dip_ver = int(getattr(self.planet, "diplomacy_version", 0))
        block_ver = int(getattr(self.planet, "trade_block_version", 0))
        vis_ver_sum = int(getattr(self.planet, "visibility_version_sum", 0))
        return econ_ver, dip_ver, block_ver, vis_ver_sum

    def calcular_equilibrio(self, *, forcar_recalculo: bool = False) -> ResultadoComercio:
        if not forcar_recalculo and self.resultado_cache is not None:
            # se versões não mudaram, retorna cache
            econ_ver, dip_ver, block_ver, vis_ver_sum = self._versions()
            if (econ_ver, dip_ver, block_ver, vis_ver_sum) == (
                self._last_econ_ver, self._last_dip_ver, self._last_block_ver, self._last_vis_ver_sum
            ):
                return self.resultado_cache

        provincias = list(self.world.provinces())
        if not provincias:
            self.resultado_cache = ResultadoComercio()
            return self.resultado_cache

        tiles = [p.tile for p in provincias]
        matriz_custos = self._calcular_matriz_custos_dirigida(tiles)

        calc = TradeCalculator(provincias=provincias, matriz_custos=matriz_custos)
        resultado = calc.calcular_equilibrio_completo()

        self.resultado_cache = resultado
        self._last_econ_ver, self._last_dip_ver, self._last_block_ver, self._last_vis_ver_sum = self._versions()
        return resultado

    def _calcular_matriz_custos_dirigida(self, tiles: list[Tile]) -> dict[Tile, dict[Tile, float]]:
        G_world = self.world.trade_graph()
        self.rotas_caminhos = {}

        # owner por tile de província
        owners: dict[Tile, int] = {}
        for t in tiles:
            prov = self.planet.get_province(t)
            owners[t] = int(prov.owner.id) if prov and prov.owner else -1

        matriz: dict[Tile, dict[Tile, float]] = {}

        for origem in tiles:
            matriz[origem] = {}
            self.rotas_caminhos[origem] = {}

            seller_id = owners.get(origem, -1)
            if seller_id < 0:
                for destino in tiles:
                    if origem == destino:
                        matriz[origem][destino] = 0.0
                        self.rotas_caminhos[origem][destino] = [origem]
                    else:
                        matriz[origem][destino] = CUSTO_IMPOSSIVEL
                        self.rotas_caminhos[origem][destino] = None
                continue

            # subgrafo passável para comércio do vendedor
            passable = self.planet.trade_passable_tiles_for_seller(seller_id)

            # view do subgrafo (sem copy pra performance)
            G = G_world.subgraph(passable)

            if origem not in G:
                for destino in tiles:
                    matriz[origem][destino] = 0.0 if origem == destino else CUSTO_IMPOSSIVEL
                    self.rotas_caminhos[origem][destino] = [origem] if origem == destino else None
                continue

            try:
                dist = nx.single_source_dijkstra_path_length(G, origem, weight="cust_mob")
                paths = nx.single_source_dijkstra_path(G, origem, weight="cust_mob")
            except nx.NodeNotFound:
                dist, paths = {}, {}

            for destino in tiles:
                if origem == destino:
                    matriz[origem][destino] = 0.0
                    self.rotas_caminhos[origem][destino] = [origem]
                    continue

                # destino inimigo (província inimiga) => impossível
                prov_d = self.planet.get_province(destino)
                if prov_d and prov_d.owner:
                    rel = self.planet.diplomacy.relation(seller_id, int(prov_d.owner.id))
                    if rel == Relation.ENEMY:
                        matriz[origem][destino] = CUSTO_IMPOSSIVEL
                        self.rotas_caminhos[origem][destino] = None
                        continue

                d = dist.get(destino)
                if d is None:
                    matriz[origem][destino] = CUSTO_IMPOSSIVEL
                    self.rotas_caminhos[origem][destino] = None
                else:
                    matriz[origem][destino] = float(d) * self.fator_custo_transporte
                    self.rotas_caminhos[origem][destino] = list(paths[destino])

        return matriz

    def get_caminho_rota(self, origem: Tile, destino: Tile) -> list[Tile] | None:
        return self.rotas_caminhos.get(origem, {}).get(destino)
