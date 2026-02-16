# core/trade/facade.py
from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.planet import Planet
    from core.civilization import Province, Civilization


@dataclass(frozen=True)
class TradeRouteInfo:
    """DTO (Data Transfer Object) para a UI de comércio."""
    resource_name: str
    quantity: float
    partner_civ: Civilization
    is_sale: bool  # True para venda, False para recebimento
    path: list[tuple[int, int]] | None


class ProvinceTradeFacade:
    def __init__(self, *, planet: Planet, province: Province):
        self.planet = planet
        self.province = province
        self.tile = province.tile_coords
        self.owner = province.owner

    def get_trade_routes(self) -> list[TradeRouteInfo]:
        """
        Consulta o MarketSystem, analisa os fluxos de comércio e retorna uma
        lista simplificada de rotas para a UI.
        """
        if not self.owner:
            return []

        # Etapa 1: Obter os resultados do mercado (do cache ou recalculado)
        market_results = self.planet.economy.calcular_equilibrio()
        if not market_results:
            return []

        routes = []

        # Etapa 2: Unir todos os fluxos de todos os recursos em um só lugar
        # O formato de cada item será: (resource_name, seller_tile, buyer_tile, quantity)
        all_trades = []
        flux_sources = {
            "food": market_results.fluxos_alimento,
            "ore": market_results.fluxos_minerio
        }

        for category, resource_fluxes in flux_sources.items():
            for resource_name, flux_dict in resource_fluxes.items():
                for seller_tile, buyer_dict in flux_dict.items():
                    for buyer_tile, quantity in buyer_dict.items():
                        # Adiciona apenas se houver uma quantidade real de comércio
                        if quantity > 1e-9:
                            all_trades.append((resource_name, seller_tile, buyer_tile, quantity))

        # Etapa 3: Iterar por todos os comércios e filtrar os que envolvem esta província
        for resource_name, seller_tile, buyer_tile, quantity in all_trades:

            # Caso 1: A província atual é a VENDEDORA
            if seller_tile == self.tile:
                partner_province = self.planet.get_province(buyer_tile)
                if not partner_province or not partner_province.owner:
                    continue

                # Obter o caminho da rota usando o método do MarketSystem
                path = self.planet.economy.get_caminho_rota(seller_tile, buyer_tile)

                route = TradeRouteInfo(
                    resource_name=resource_name,
                    quantity=quantity,
                    partner_civ=partner_province.owner,
                    is_sale=True,
                    path=path
                )
                routes.append(route)

            # Caso 2: A província atual é a COMPRADORA
            elif buyer_tile == self.tile:
                partner_province = self.planet.get_province(seller_tile)
                if not partner_province or not partner_province.owner:
                    continue

                # Obter o caminho da rota usando o método do MarketSystem
                path = self.planet.economy.get_caminho_rota(seller_tile, buyer_tile)

                route = TradeRouteInfo(
                    resource_name=resource_name,
                    quantity=quantity,
                    partner_civ=partner_province.owner,
                    is_sale=False,
                    path=path
                )
                routes.append(route)

        return routes
