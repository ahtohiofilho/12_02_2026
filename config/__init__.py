# config/__init__.py

# Expõe as constantes e funções dos submódulos para fácil importação

from .civilization import CULTURAS, CIV_CORES
from .gameplay import (
    PRODUTIVIDADE_BASE,
    MAPA_BIOMA_ALIMENTO,
    LETRAS_GREGAS,
    ALLOWED_BIOMES_PER_CATEGORY
)
from .rendering import CORES_BIOMAS, TONS_DE_PELE, TONS_DE_CABELO
"""
from .units import (
    BASE_UNIT_COST,
    UNIT_SPRITES,
    get_sprite_rect,
    get_all_unit_types,
    get_units_by_category
)
"""