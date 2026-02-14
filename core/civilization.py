# core/civilization.py

from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

# Isso evita erros de importação circular.
if TYPE_CHECKING:
    from .planet import Planet


@dataclass
class Province:
    """Representa um único tile possuído por uma civilização."""
    owner: 'Civilization'  # Agora armazena a referência direta ao objeto Civilization
    tile_coords: tuple
    is_capital: bool = False
    name: str = "Província"


@dataclass
class Civilization:
    """Representa uma nação ou império no planeta."""
    # Referências e Identidade
    planeta: 'Planet'
    id: int
    name: str
    color: tuple[int, int, int]

    # Território
    capital_coords: tuple
    provinces: list[Province] = field(default_factory=list)

    def __post_init__(self):
        """
        Este método é chamado automaticamente após o __init__ do dataclass.
        É o lugar perfeito para criar a província capital.
        """
        self._create_capital_province()

    def _create_capital_province(self):
        """Cria a província capital, a adiciona à lista e a registra no planeta."""
        if self.capital_coords in self.planeta.provinces_by_tile:
            print(f"⚠️ AVISO: Tentando criar capital em {self.capital_coords}, que já possui uma província.")
            return

        # 1. Cria o objeto Provincia
        capital_province = Province(
            owner=self,
            tile_coords=self.capital_coords,
            is_capital=True,
            name=f"Capital de {self.name}"
        )

        # 2. Adiciona a província à lista interna da civilização
        self.provinces.append(capital_province)

        # 3. Registra a província no dicionário global do planeta
        self.planeta.provinces_by_tile[self.capital_coords] = capital_province

        # print(f"   -> Capital '{capital_province.name}' criada em {self.capital_coords}")

