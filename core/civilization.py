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

    # Economia (estoque + fluxo por turno)
    treasury: float = 0.0          # caixa acumulado (começa em 0)
    last_output: float = 0.0       # (opcional) output do último turno, útil p/ UI/debug


@dataclass
class Civilization:
    planeta: 'Planet'
    id: int
    name: str
    color: tuple[int, int, int]
    capital_coords: tuple

    # NOVO: diferencia civ “player” (participa da guerra inicial / pode ter UI/IA etc.)
    is_player: bool = True

    provinces: list[Province] = field(default_factory=list)

    workers_purchased: int = 0

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
        try:
            from services.flag_service import bandeira

            if not hasattr(self.planeta, 'id') or not self.planeta.id:
                self.planeta.id = str(uuid.uuid4())

            # RNG local: mesmo planeta + mesmo civ id → mesma bandeira sempre
            rng = random.Random(hash((self.planeta.id, self.id)))
            flag_type = rng.randint(0, 82)

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
            rng = random.Random(hash((self.planeta.id, self.id)))
            self.flag_colors = self.color
            self.flag_type = rng.randint(0, 82)
            self.flag_generated = False
            print("⚠️ Módulo de bandeiras não disponível. Usando fallback")
        except Exception as e:
            print(f"❌ Erro ao gerar bandeira: {e}")
            rng = random.Random(hash((self.planeta.id, self.id)))
            self.flag_colors = self.color
            self.flag_type = rng.randint(0, 82)
            self.flag_generated = False
