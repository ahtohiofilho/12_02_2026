# core/economy/trade.py
"""
Sistema de comércio - Rodadas Sincronizadas (Water-Filling Discreto).

Portado para a arquitetura nova:
- Entrada: lista de ProvinceView (tile, workers, food_type/ore_type, food_output/ore_output)
- Entrada: matriz_custos[origem_tile][destino_tile] = custo_monetario_por_unidade (já escalado)
- Saída: core.economy.models.ResultadoComercio (estrutura única do projeto)

Algoritmo (mesma lógica do projeto antigo):
- Para cada commodity (tipo), produtores escolhem por rodadas o melhor mercado com base em
  LUCRO MARGINAL de depositar um lote Δ.
- Decisão síncrona: todos decidem com snapshot do mercado; depois commit em lote.

Candidatos por produtor:
- Grupo B: fração mais próxima por custo (default: todos, mas você pode reduzir)
- Grupo A: mercados "grandes" (workers >= 150% da média)
- Se Grupo A estiver vazio, usa apenas Grupo B.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from core.economy.models import ResultadoComercio, Tile, ProvinceView
from core.economy.price import PriceCalculator


class TradeCalculatorError(Exception):
    """Exceção para erros no cálculo de comércio."""
    pass


@dataclass(slots=True)
class TradeCalculator:
    """
    Calculador de comércio por commodity (alimento e minério),
    implementando "rodadas sincronizadas" (decide/commit).

    Observação importante (reprodutibilidade):
    - Este módulo não usa random.
    - Para reprodutibilidade forte, iteramos tipos em ordem sorted().
    """

    # demanda per-capita por commodity (constante por categoria)
    COEF_DEMANDA_ALIMENTO: float = 4.0
    COEF_DEMANDA_MINERIO: float = 1.0

    EPSILON: float = 1e-9
    DEBUG: bool = False

    # candidatos
    FATOR_MERCADO_GRANDE: float = 1.5  # >= 150% da média
    FRACAO_MAIS_PROXIMOS: float = 3.0 / 3.0  # 1.0 = todos; reduza se ficar pesado

    # solver
    MAX_RODADAS_PADRAO: int = 200_000
    ALVO_RODADAS_POR_TIPO: int = 2500  # usado para delta automático

    # --- init ---

    def __init__(self, provincias: Iterable[ProvinceView], matriz_custos: Dict[Tile, Dict[Tile, float]]):
        provincias_list = list(provincias)
        if not provincias_list:
            raise TradeCalculatorError("Lista de províncias vazia")

        if matriz_custos is None:
            raise TradeCalculatorError("matriz_custos é obrigatória")

        # ids / index
        self.provincias_dict: dict[Tile, ProvinceView] = {p.tile: p for p in provincias_list}
        self.ids: list[Tile] = list(self.provincias_dict.keys())

        self.matriz_custos = matriz_custos
        self._validar_matriz_custos()

        # tipos por categoria
        self.tipos_alimento: set[str] = self._coletar_tipos_food()
        self.tipos_minerio: set[str] = self._coletar_tipos_ore()

        # demandas separadas por commodity
        self.demandas_alimento_por_tipo: Dict[str, Dict[Tile, float]] = {}
        self.demandas_minerio_por_tipo: Dict[str, Dict[Tile, float]] = {}

        for tipo in self.tipos_alimento:
            self.demandas_alimento_por_tipo[tipo] = {}
            for coord, prov in self.provincias_dict.items():
                trab = max(1, int(getattr(prov, "workers", 1) or 1))
                self.demandas_alimento_por_tipo[tipo][coord] = float(trab) * self.COEF_DEMANDA_ALIMENTO

        for tipo in self.tipos_minerio:
            self.demandas_minerio_por_tipo[tipo] = {}
            for coord, prov in self.provincias_dict.items():
                trab = max(1, int(getattr(prov, "workers", 1) or 1))
                self.demandas_minerio_por_tipo[tipo][coord] = float(trab) * self.COEF_DEMANDA_MINERIO

        # cache: mercados ordenados por custo (por origem)
        self._mercados_por_custo: Dict[Tile, List[Tile]] = {}
        for p in self.ids:
            ordenados = sorted(self.ids, key=lambda m: self._get_custo(p, m))
            self._mercados_por_custo[p] = ordenados

        # mercados "grandes"
        self._mercados_grandes: set[Tile] = self._calcular_mercados_grandes()

    # --- validação / helpers ---

    def _validar_matriz_custos(self) -> None:
        for origem in self.ids:
            if origem not in self.matriz_custos:
                raise TradeCalculatorError(f"Origem {origem} faltando na matriz_custos")

            for destino in self.ids:
                if destino not in self.matriz_custos[origem]:
                    raise TradeCalculatorError(f"Rota {origem}→{destino} faltando na matriz_custos")

                custo = self.matriz_custos[origem][destino]
                if custo is None or (isinstance(custo, float) and math.isnan(custo)) or custo < 0:
                    raise TradeCalculatorError(f"Custo inválido {origem}→{destino}: {custo}")

                if origem == destino and custo != 0:
                    raise TradeCalculatorError(f"Custo local deve ser 0 (origem==destino). Achou {custo} em {origem}")

    def _coletar_tipos_food(self) -> set[str]:
        tipos: set[str] = set()
        for prov in self.provincias_dict.values():
            t = getattr(prov, "food_type", None)
            if t:
                tipos.add(str(t))
        return tipos

    def _coletar_tipos_ore(self) -> set[str]:
        tipos: set[str] = set()
        for prov in self.provincias_dict.values():
            t = getattr(prov, "ore_type", None)
            if t:
                tipos.add(str(t))
        return tipos

    def _get_custo(self, origem: Tile, destino: Tile) -> float:
        if origem == destino:
            return 0.0
        return float(self.matriz_custos[origem][destino])

    def _calcular_preco(self, oferta: float, demanda: float) -> float:
        return PriceCalculator.calcular_preco(oferta, demanda)

    # --- mercados grandes / candidatos ---

    def _calcular_mercados_grandes(self) -> set[Tile]:
        """
        Grupo A: mercados com workers >= 150% da média.
        """
        ws: list[float] = []
        for m in self.ids:
            prov = self.provincias_dict[m]
            w = max(0, int(getattr(prov, "workers", 0) or 0))
            ws.append(float(w))

        if not ws:
            return set()

        media = sum(ws) / len(ws)
        limiar = self.FATOR_MERCADO_GRANDE * media

        grandes = {m for m in self.ids if max(0, int(getattr(self.provincias_dict[m], "workers", 0) or 0)) >= limiar}

        if self.DEBUG:
            print(f"   [Candidatos] mercados grandes: {len(grandes)} (limiar={limiar:.2f}, media={media:.2f})")

        return grandes

    def _get_candidatos(self, produtor: Tile) -> List[Tile]:
        """
        Grupo B: fração mais próxima por custo.
        Grupo A: mercados grandes.
        Se não houver mercados grandes, retorna apenas Grupo B.
        """
        M = len(self.ids)
        n_close = max(1, math.ceil(M * float(self.FRACAO_MAIS_PROXIMOS)))

        proximos = self._mercados_por_custo[produtor][:n_close]
        if not self._mercados_grandes:
            return proximos

        # união preservando ordem
        cand = list(proximos)
        s = set(cand)
        for m in self._mercados_grandes:
            if m not in s:
                cand.append(m)
        return cand

    # --- delta automático ---

    def _delta_auto(self, oferta_total: float) -> float:
        if oferta_total <= 0:
            return 1.0
        return max(1.0, oferta_total / float(self.ALVO_RODADAS_POR_TIPO))

    # --- solver por rodadas sincronizadas ---

    def _water_fill_rodadas_sincronas(
        self,
        *,
        produtores: List[Tile],
        ofertas: Dict[Tile, float],
        demandas: Dict[Tile, float],
        delta: float,
        max_rodadas: int,
    ) -> tuple[Dict[Tile, Dict[Tile, float]], int, bool]:
        """
        Retorna:
          - fluxos[p][m] = qtd enviada do produtor p para o mercado m (shape completo ids x ids)
          - iteracoes (rodadas executadas)
          - convergiu
        """
        fluxos: Dict[Tile, Dict[Tile, float]] = {p: {m: 0.0 for m in self.ids} for p in self.ids}

        rem: Dict[Tile, float] = {p: float(ofertas.get(p, 0.0) or 0.0) for p in produtores}
        oferta_mercado: Dict[Tile, float] = {m: 0.0 for m in self.ids}

        for rodada in range(int(max_rodadas)):
            ativos = [p for p in produtores if rem[p] > self.EPSILON]
            if not ativos:
                return fluxos, rodada, True

            decisoes: Dict[Tile, Tuple[Tile | None, float]] = {}

            # decide (snapshot)
            for p in ativos:
                qtd = min(float(delta), rem[p])
                candidatos = self._get_candidatos(p)

                melhor_m: Tile | None = None
                melhor_lucro = -float("inf")

                for m in candidatos:
                    rec_marg = PriceCalculator.calcular_receita_marginal(
                        oferta_atual=float(oferta_mercado[m]),
                        demanda=float(demandas.get(m, 0.0) or 0.0),
                        quantidade_adicional=float(qtd),
                    )
                    custo = self._get_custo(p, m) * float(qtd)
                    lucro = float(rec_marg) - float(custo)

                    if lucro > melhor_lucro:
                        melhor_lucro = lucro
                        melhor_m = m

                # se não compensa, descarta (produção some)
                if melhor_lucro <= 0.0 or melhor_m is None:
                    decisoes[p] = (None, qtd)
                else:
                    decisoes[p] = (melhor_m, qtd)

            # commit síncrono
            for p, (m, qtd) in decisoes.items():
                if m is not None:
                    fluxos[p][m] += float(qtd)
                    oferta_mercado[m] += float(qtd)
                rem[p] -= float(qtd)

        return fluxos, int(max_rodadas), False

    # --- receitas (pool+rateio pro rata) ---

    def _calcular_receitas_pool_prorata(
        self,
        *,
        produtores: List[Tile],
        fluxos: Dict[Tile, Dict[Tile, float]],
        demandas: Dict[Tile, float],
    ) -> Dict[Tile, float]:
        receitas: Dict[Tile, float] = {coord: 0.0 for coord in self.ids}

        # Q_m
        Q: Dict[Tile, float] = {m: 0.0 for m in self.ids}
        for p in produtores:
            row = fluxos[p]
            for m, qtd in row.items():
                Q[m] += float(qtd or 0.0)

        # R_m
        R: Dict[Tile, float] = {}
        for m in self.ids:
            Dm = float(demandas.get(m, 0.0) or 0.0)
            R[m] = PriceCalculator.calcular_receita_total(Q[m], Dm)

        # rateio + custo
        for p in produtores:
            total = 0.0
            for m in self.ids:
                qtd = float(fluxos[p].get(m, 0.0) or 0.0)
                if qtd <= self.EPSILON:
                    continue

                pagamento = 0.0 if Q[m] <= self.EPSILON else (R[m] * (qtd / Q[m]))
                custo = self._get_custo(p, m) * qtd
                total += pagamento - custo

            receitas[p] = max(0.0, float(total))

        return receitas

    # --- equilíbrio por tipo ---

    def _resultado_vazio(self, *, demandas: Dict[Tile, float]) -> dict:
        return {
            "fluxos": {p: {m: 0.0 for m in self.ids} for p in self.ids},
            "precos": {m: self._calcular_preco(0.0, float(demandas.get(m, 0.0) or 0.0)) for m in self.ids},
            "receitas": {m: 0.0 for m in self.ids},
            "demandas": dict(demandas),
            "convergiu": True,
            "iteracoes": 0,
        }

    def _calcular_equilibrio_tipo_food(self, tipo: str) -> dict:
        demandas = self.demandas_alimento_por_tipo.get(tipo, {})

        ofertas: Dict[Tile, float] = {}
        produtores: List[Tile] = []
        for coord, prov in self.provincias_dict.items():
            if getattr(prov, "food_type", None) == tipo:
                prod = float(getattr(prov, "food_output", 0.0) or 0.0)
                ofertas[coord] = prod
                if prod > self.EPSILON:
                    produtores.append(coord)
            else:
                ofertas[coord] = 0.0

        oferta_total = sum(ofertas.values())
        if self.DEBUG:
            demanda_total = sum(demandas.values()) if demandas else 0.0
            print(f"   [Food:{tipo}] {len(produtores)} produtores, oferta={oferta_total:.1f}, demanda={demanda_total:.1f}")

        if not produtores:
            return self._resultado_vazio(demandas=demandas)

        delta = self._delta_auto(oferta_total)
        fluxos, iteracoes, convergiu = self._water_fill_rodadas_sincronas(
            produtores=produtores,
            ofertas=ofertas,
            demandas=demandas,
            delta=delta,
            max_rodadas=self.MAX_RODADAS_PADRAO,
        )

        oferta_mercado = {m: sum(fluxos[p][m] for p in self.ids) for m in self.ids}
        precos = {m: self._calcular_preco(oferta_mercado[m], float(demandas.get(m, 0.0) or 0.0)) for m in self.ids}
        receitas = self._calcular_receitas_pool_prorata(produtores=produtores, fluxos=fluxos, demandas=demandas)

        return {
            "fluxos": fluxos,
            "precos": precos,
            "receitas": receitas,
            "demandas": dict(demandas),
            "convergiu": convergiu,
            "iteracoes": iteracoes,
        }

    def _calcular_equilibrio_tipo_ore(self, tipo: str) -> dict:
        demandas = self.demandas_minerio_por_tipo.get(tipo, {})

        ofertas: Dict[Tile, float] = {}
        produtores: List[Tile] = []
        for coord, prov in self.provincias_dict.items():
            if getattr(prov, "ore_type", None) == tipo:
                prod = float(getattr(prov, "ore_output", 0.0) or 0.0)
                ofertas[coord] = prod
                if prod > self.EPSILON:
                    produtores.append(coord)
            else:
                ofertas[coord] = 0.0

        oferta_total = sum(ofertas.values())
        if self.DEBUG:
            demanda_total = sum(demandas.values()) if demandas else 0.0
            print(f"   [Ore:{tipo}] {len(produtores)} produtores, oferta={oferta_total:.1f}, demanda={demanda_total:.1f}")

        if not produtores:
            return self._resultado_vazio(demandas=demandas)

        delta = self._delta_auto(oferta_total)
        fluxos, iteracoes, convergiu = self._water_fill_rodadas_sincronas(
            produtores=produtores,
            ofertas=ofertas,
            demandas=demandas,
            delta=delta,
            max_rodadas=self.MAX_RODADAS_PADRAO,
        )

        oferta_mercado = {m: sum(fluxos[p][m] for p in self.ids) for m in self.ids}
        precos = {m: self._calcular_preco(oferta_mercado[m], float(demandas.get(m, 0.0) or 0.0)) for m in self.ids}
        receitas = self._calcular_receitas_pool_prorata(produtores=produtores, fluxos=fluxos, demandas=demandas)

        return {
            "fluxos": fluxos,
            "precos": precos,
            "receitas": receitas,
            "demandas": dict(demandas),
            "convergiu": convergiu,
            "iteracoes": iteracoes,
        }

    def _agregar_receitas(self, resultados: Dict[str, dict]) -> Dict[Tile, float]:
        totais: Dict[Tile, float] = {coord: 0.0 for coord in self.ids}
        for r in resultados.values():
            for coord, receita in r["receitas"].items():
                totais[coord] += float(receita or 0.0)
        return totais

    # --- interface pública ---

    def calcular_equilibrio_completo(self) -> ResultadoComercio:
        if self.DEBUG:
            print("\n🔄 [TradeCalculator] Rodadas sincronizadas (portado)")

        # Iterar tipos em ordem fixa -> reprodutibilidade estável.
        resultados_alimentos: Dict[str, dict] = {}
        resultados_minerios: Dict[str, dict] = {}

        for tipo in sorted(self.tipos_alimento):
            resultados_alimentos[tipo] = self._calcular_equilibrio_tipo_food(tipo)

        for tipo in sorted(self.tipos_minerio):
            resultados_minerios[tipo] = self._calcular_equilibrio_tipo_ore(tipo)

        # Consolidar no ResultadoComercio único do projeto
        return ResultadoComercio(
            precos_alimento={t: r["precos"] for t, r in resultados_alimentos.items()},
            precos_minerio={t: r["precos"] for t, r in resultados_minerios.items()},
            fluxos_alimento={t: r["fluxos"] for t, r in resultados_alimentos.items()},
            fluxos_minerio={t: r["fluxos"] for t, r in resultados_minerios.items()},
            demandas_alimento={t: r["demandas"] for t, r in resultados_alimentos.items()},
            demandas_minerio={t: r["demandas"] for t, r in resultados_minerios.items()},
            receitas_alimento=self._agregar_receitas(resultados_alimentos),
            receitas_minerio=self._agregar_receitas(resultados_minerios),
            convergiu=all(r.get("convergiu", False) for r in list(resultados_alimentos.values()) + list(resultados_minerios.values()))
            if (resultados_alimentos or resultados_minerios)
            else True,
            iteracoes=max(
                [r.get("iteracoes", 0) for r in list(resultados_alimentos.values()) + list(resultados_minerios.values())] or [0]
            ),
        )
