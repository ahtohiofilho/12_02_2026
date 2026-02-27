# shared/naming/languages/ru.py
from __future__ import annotations

from ..types import NamingContext
from ..utils.rng import rng_from_seed, choice, wchoice
from ..utils.text import clean_spaces, title_words
from ..datasets.ru import NOUNS_M, NOUNS_F, NOUNS_N, ADJ_M, ADJ_F, ADJ_N

_RU_TO_LAT: dict[str, str] = {
    "а": "a",  "б": "b",   "в": "v",   "г": "g",   "д": "d",   "е": "e",   "ё": "yo",
    "ж": "zh", "з": "z",   "и": "i",   "й": "y",   "к": "k",   "л": "l",   "м": "m",
    "н": "n",  "о": "o",   "п": "p",   "р": "r",   "с": "s",   "т": "t",   "у": "u",
    "ф": "f",  "х": "kh",  "ц": "ts",  "ч": "ch",  "ш": "sh",  "щ": "shch","ъ": "",
    "ы": "y",  "ь": "",    "э": "e",   "ю": "yu",  "я": "ya",

    "А": "A",  "Б": "B",   "В": "V",   "Г": "G",   "Д": "D",   "Е": "E",   "Ё": "Yo",
    "Ж": "Zh", "З": "Z",   "И": "I",   "Й": "Y",   "К": "K",   "Л": "L",   "М": "M",
    "Н": "N",  "О": "O",   "П": "P",   "Р": "R",   "С": "S",   "Т": "T",   "У": "U",
    "Ф": "F",  "Х": "Kh",  "Ц": "Ts",  "Ч": "Ch",  "Ш": "Sh",  "Щ": "Shch","Ъ": "",
    "Ы": "Y",  "Ь": "",    "Э": "E",   "Ю": "Yu",  "Я": "Ya",
}


def _translit_ru(s: str) -> str:
    """Transliteração simples RU->LAT (tabela direta, sem regras contextuais)."""
    return "".join(_RU_TO_LAT.get(ch, ch) for ch in s)


class RussianGenerator:
    culture = "Russian"

    def province(self, ctx: NamingContext | None = None) -> str:
        ctx = ctx or NamingContext()
        rng = rng_from_seed(ctx.seed)

        # NOM.SG sempre, com concordância de gênero
        gender = wchoice(rng, ["M", "F", "N"], [40, 40, 20])

        if gender == "M":
            noun = choice(rng, NOUNS_M)
            adj = choice(rng, ADJ_M)
        elif gender == "F":
            noun = choice(rng, NOUNS_F)
            adj = choice(rng, ADJ_F)
        else:
            noun = choice(rng, NOUNS_N)
            adj = choice(rng, ADJ_N)

        name_cyr = clean_spaces(f"{adj} {noun}")
        name = _translit_ru(name_cyr)

        # Importante: no russo romanizado, não queremos forçar conectores globais (ex.: "les") a minúsculo.
        if getattr(ctx, "capitalizar", False):
            return title_words(name, keep_lower=set())
        return name
