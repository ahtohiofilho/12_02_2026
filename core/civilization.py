# core/civilization.py
import random
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .planet import Planet


@dataclass
class Province:
    owner: 'Civilization'
    tile_coords: tuple
    is_capital: bool = False
    name: str = "Província"


@dataclass
class Civilization:
    planeta: 'Planet'
    id: int
    name: str
    color: tuple[int, int, int]
    capital_coords: tuple
    provinces: list[Province] = field(default_factory=list)

    # Campos para bandeira
    flag_colors: tuple = field(init=False)
    flag_type: int = field(init=False)
    flag_generated: bool = field(init=False, default=False)

    def __post_init__(self):
        self._create_capital_province()
        self._generate_flag()

    def _create_capital_province(self):
        if self.capital_coords in self.planeta.provinces_by_tile:
            print(f"⚠️ AVISO: Tentando criar capital em {self.capital_coords}, que já possui uma província.")
            return

        capital_province = Province(
            owner=self,
            tile_coords=self.capital_coords,
            is_capital=True,
            name=f"Capital de {self.name}"
        )
        self.provinces.append(capital_province)
        self.planeta.provinces_by_tile[self.capital_coords] = capital_province

    def _generate_flag(self):
        """Gera a bandeira usando o sistema compartilhado"""
        try:
            from services.flag_service import bandeira

            # Garantir que o planeta tenha ID
            if not hasattr(self.planeta, 'id') or not self.planeta.id:
                self.planeta.id = str(uuid.uuid4())

            # Gerar número aleatório para o padrão da bandeira
            flag_type = random.randint(0, 82)
            colors = bandeira(
                self.name,
                flag_type,
                criar_arquivo=True,
                id_mundo=self.planeta.id
            )

            self.flag_colors = colors
            self.flag_type = flag_type
            self.flag_generated = True
        except ImportError:
            # Fallback se o módulo não estiver disponível
            self.flag_colors = self.color
            self.flag_type = random.randint(0, 82)
            self.flag_generated = False
            print("⚠️ Módulo de bandeiras não disponível. Usando fallback")
        except Exception as e:
            print(f"❌ Erro ao gerar bandeira: {e}")
            self.flag_colors = self.color
            self.flag_type = random.randint(0, 82)
            self.flag_generated = False
