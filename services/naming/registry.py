# services/naming/registry.py
from __future__ import annotations

from .languages.en import EnglishGenerator
from .languages.pt import PortugueseGenerator
from .languages.es import SpanishGenerator
from .languages.fr import FrenchGenerator
from .languages.it import ItalianGenerator
from .languages.de import GermanGenerator
from .languages.ru import RussianGenerator
from .languages.tr import TurkishGenerator
from .languages.ar import ArabicGenerator
from .languages.fa import PersianGenerator
from .languages.ja import JapaneseGenerator
from .languages.zh import ChineseGenerator
from .languages.ko import KoreanGenerator
from .languages.vi import VietnameseGenerator
from .languages.id import IndonesianGenerator
from .languages.sw import SwahiliGenerator
from .languages.hi import HindiGenerator
from .languages.ha import HausaGenerator
from .languages.te import TeluguGenerator
from .languages.bn import BengaliGenerator
from .languages.mr import MarathiGenerator
from .languages.wu import WuGenerator
from .languages.yue import YueGenerator
from .languages.min import MinGenerator

_GENERATORS = {
    "English": EnglishGenerator(),
    "Portuguese": PortugueseGenerator(),
    "Spanish": SpanishGenerator(),
    "French": FrenchGenerator(),
    "Italian": ItalianGenerator(),
    "German": GermanGenerator(),
    "Russian": RussianGenerator(),
    "Turkish": TurkishGenerator(),
    "Arabic": ArabicGenerator(),
    "Persian": PersianGenerator(),
    "Japanese": JapaneseGenerator(),
    "Chinese": ChineseGenerator(),
    "Korean": KoreanGenerator(),
    "Vietnamese": VietnameseGenerator(),
    "Indonesian": IndonesianGenerator(),
    "Swahili": SwahiliGenerator(),
    "Hindi": HindiGenerator(),
    "Hausa": HausaGenerator(),
    "Telugu": TeluguGenerator(),
    "Bengali": BengaliGenerator(),
    "Marathi": MarathiGenerator(),
    "Wu": WuGenerator(),
    "Yue": YueGenerator(),
    "Min": MinGenerator(),
}

def get_generator(culture: str):
    return _GENERATORS.get(culture, _GENERATORS["English"])
