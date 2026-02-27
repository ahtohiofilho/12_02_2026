# shared/naming/languages/pt.py
from __future__ import annotations

from ..types import NamingContext
from ..utils.rng import rng_from_seed, choice, wchoice
from ..utils.text import clean_spaces, title_words, to_ascii
from ..datasets.pt import (
    NOUNS_M_SG, NOUNS_F_SG, NOUNS_M_PL, NOUNS_F_PL,
    ADJ_M_SG, ADJ_F_SG, ADJ_M_PL, ADJ_F_PL
)
from ..utils.text import to_ascii_strict, to_western_friendly

class PortugueseGenerator:
    culture = "Portuguese"

    def province(self, ctx: NamingContext | None = None) -> str:
        ctx = ctx or NamingContext()
        rng = rng_from_seed(ctx.seed)

        # 90% singular, 10% plural (ajuste como quiser)
        number = wchoice(rng, ["SG", "PL"], [90, 10])
        gender = wchoice(rng, ["M", "F"], [50, 50])

        if number == "SG" and gender == "M":
            noun = choice(rng, NOUNS_M_SG)
            adj = choice(rng, ADJ_M_SG)
        elif number == "SG" and gender == "F":
            noun = choice(rng, NOUNS_F_SG)
            adj = choice(rng, ADJ_F_SG)
        elif number == "PL" and gender == "M":
            noun = choice(rng, NOUNS_M_PL) if NOUNS_M_PL else choice(rng, NOUNS_M_SG)
            adj = choice(rng, ADJ_M_PL)
        else:  # "PL" and "F"
            noun = choice(rng, NOUNS_F_PL) if NOUNS_F_PL else choice(rng, NOUNS_F_SG)
            adj = choice(rng, ADJ_F_PL)

        name = clean_spaces(f"{noun} {adj}")

        if getattr(ctx, "sanitizer", "western") == "ascii":
            name = to_ascii_strict(name)
        elif getattr(ctx, "sanitizer", "western") == "western":
            name = to_western_friendly(name)
        else:
            pass  # "unicode": não mexe

        return title_words(name) if ctx.capitalizar else name
