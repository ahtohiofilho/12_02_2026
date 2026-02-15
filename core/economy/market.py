# core/economy/market.py
# (ajuste pequeno e explícito: "sem lógica de portos")
from __future__ import annotations

from typing import Optional
import networkx as nx

from core.economy.models import EconomyWorldView, ResultadoComercio, Tile
from core.economy.trade import TradeCalculator

CUSTO_IMPOSSIVEL = 1e12


class MarketSystem:
    """
    Mercado global SEM portos explícitos.

    Interpretação:
    - A conectividade terra-mar (e vice-versa) já está embutida no grafo do planeta via arestas,
      incluindo qualquer penalidade (PENALIDADE_TRANSICAO) e o weight 'cust_mob'.
    - Logo, "porto" é implícito: se existe aresta entre tiles marítimos e terrestres, o comércio pode fluir.
    """

    def __init__(self, world: EconomyWorldView):
        self.world = world
        self.resultado_cache: Optional[ResultadoComercio] = None

        self.rotas_caminhos: dict[Tile, dict[Tile, list[Tile] | None]] = {}
        self.fator_custo_transporte = 0.01  # custo_monetario_por_unidade = dist_dijkstra * fator

    def invalidar_cache(self) -> None:
        self.resultado_cache = None

    def calcular_equilibrio(self, *, forcar_recalculo: bool = False) -> ResultadoComercio:
        if self.resultado_cache is not None and not forcar_recalculo:
            return self.resultado_cache

        provincias = list(self.world.provinces())
        if not provincias:
            self.resultado_cache = ResultadoComercio()
            return self.resultado_cache

        matriz_custos = self._calcular_matriz_custos([p.tile for p in provincias])

        calc = TradeCalculator(provincias=provincias, matriz_custos=matriz_custos)
        resultado = calc.calcular_equilibrio_completo()

        self.resultado_cache = resultado
        return resultado

    def _calcular_matriz_custos(self, tiles: list[Tile]) -> dict[Tile, dict[Tile, float]]:
        """
        Matriz de custos entre as províncias do mundo econômico, usando o grafo do planeta.
        Sem qualquer sistema adicional de "porto": só Dijkstra no weight 'cust_mob'.
        """
        G = self.world.trade_graph()

        matriz: dict[Tile, dict[Tile, float]] = {}
        self.rotas_caminhos = {}

        for origem in tiles:
            matriz[origem] = {}
            self.rotas_caminhos[origem] = {}

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

                d = dist.get(destino)
                if d is None:
                    matriz[origem][destino] = CUSTO_IMPOSSIVEL
                    self.rotas_caminhos[origem][destino] = None
                else:
                    # custo monetário por unidade (confirmado por você)
                    matriz[origem][destino] = float(d) * self.fator_custo_transporte
                    self.rotas_caminhos[origem][destino] = paths[destino]

        return matriz

    def get_caminho_rota(self, origem: Tile, destino: Tile) -> list[Tile] | None:
        return self.rotas_caminhos.get(origem, {}).get(destino)
