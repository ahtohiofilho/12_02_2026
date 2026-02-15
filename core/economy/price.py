# core/economy/price.py
from __future__ import annotations
import math


class PriceCalculator:
    @staticmethod
    def calcular_preco(oferta: float, demanda: float) -> float:
        if demanda <= 0:
            return 0.0
        if oferta <= 0:
            return 100.0
        x = oferta / demanda
        return 1.0 / math.sqrt(x)

    @staticmethod
    def calcular_receita_total(oferta: float, demanda: float) -> float:
        if oferta <= 0 or demanda <= 0:
            return 0.0
        return math.sqrt(oferta * demanda)

    @staticmethod
    def calcular_receita_marginal(oferta_atual: float, demanda: float, quantidade_adicional: float = 1.0) -> float:
        if demanda <= 0 or oferta_atual < 0:
            return 0.0
        if oferta_atual == 0:
            return math.sqrt(min(quantidade_adicional, demanda))
        receita_antes = math.sqrt(oferta_atual * demanda)
        receita_depois = math.sqrt((oferta_atual + quantidade_adicional) * demanda)
        return receita_depois - receita_antes
