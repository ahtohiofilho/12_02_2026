# shared/naming/languages/fr.py
from __future__ import annotations

from ..types import NamingContext
from ..utils.rng import rng_from_seed, choice, wchoice
from ..utils.text import clean_spaces, title_words
from ..datasets.fr import (
    NOUNS_M_SG, NOUNS_F_SG, NOUNS_M_PL, NOUNS_F_PL,
    ADJ_M_SG, ADJ_F_SG, ADJ_M_PL, ADJ_F_PL,
    ADJ_BAGS_M_SG, ADJ_BAGS_F_SG, ADJ_BAGS_M_PL, ADJ_BAGS_F_PL,
)
from ..utils.text import to_ascii_strict, to_western_friendly


# Opcional: ajuste mínimo “Beau -> Bel” quando vier antes de palavra iniciando com vogal/h.
# (Super simples; não tenta resolver todos os casos do francês.)
_VOWELISH_RE = __import__("re").compile(r"^[AEIOUYÀÂÄÆÉÈÊËÎÏÔÖŒÙÛÜŸH]", flags=0)

def _maybe_bel(adj: str, noun: str) -> str:
    if adj != "Beau":
        return adj
    # Title case vai acontecer depois; aqui ainda está com maiúscula inicial.
    if _VOWELISH_RE.match(noun):
        return "Bel"
    return adj


class FrenchGenerator:
    culture = "French"

    def province(self, ctx: NamingContext | None = None) -> str:
        ctx = ctx or NamingContext()
        rng = rng_from_seed(ctx.seed)

        number = wchoice(rng, ["SG", "PL"], [90, 10])
        gender = wchoice(rng, ["M", "F"], [50, 50])

        if number == "SG" and gender == "M":
            noun = choice(rng, NOUNS_M_SG)
            adj_post = choice(rng, ADJ_M_SG)
            adj_bags = choice(rng, ADJ_BAGS_M_SG)
        elif number == "SG" and gender == "F":
            noun = choice(rng, NOUNS_F_SG)
            adj_post = choice(rng, ADJ_F_SG)
            adj_bags = choice(rng, ADJ_BAGS_F_SG)
        elif number == "PL" and gender == "M":
            noun = choice(rng, NOUNS_M_PL) if NOUNS_M_PL else choice(rng, NOUNS_M_SG)
            adj_post = choice(rng, ADJ_M_PL)
            adj_bags = choice(rng, ADJ_BAGS_M_PL)
        else:
            noun = choice(rng, NOUNS_F_PL) if NOUNS_F_PL else choice(rng, NOUNS_F_SG)
            adj_post = choice(rng, ADJ_F_PL)
            adj_bags = choice(rng, ADJ_BAGS_F_PL)

        # Probabilidade simples de usar BAGS preposto
        use_preposed = (rng.random() < 0.35)

        if use_preposed:
            adj = _maybe_bel(adj_bags, noun)
            name = clean_spaces(f"{adj} {noun}")
        else:
            name = clean_spaces(f"{noun} {adj_post}")

        sanitizer = getattr(ctx, "sanitizer", "western")
        if sanitizer == "ascii":
            name = to_ascii_strict(name)
        elif sanitizer == "western":
            name = to_western_friendly(name)
        else:
            pass  # "unicode": não mexe

        return title_words(name) if ctx.capitalizar else name
