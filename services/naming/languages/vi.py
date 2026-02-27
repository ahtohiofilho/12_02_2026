# shared/naming/languages/vi.py
from __future__ import annotations

from ..types import NamingContext
from ..utils.rng import rng_from_seed, choice, wchoice
from ..utils.text import clean_spaces, title_words, to_ascii
from ..datasets.vi import NOUNS, ADJ, TOPONYMS


class VietnameseGenerator:
    culture = "Vietnamese"

    def province(self, ctx: NamingContext | None = None) -> str:
        ctx = ctx or NamingContext()
        rng = rng_from_seed(ctx.seed)

        pattern = wchoice(
            rng,
            [
                "NOUN_ADJ",          # Núi Xanh
                "NOUN_TOPONYM",      # Sông An Lạc
                "TOPONYM_NOUN",      # An Lạc Sơn (variante)
                "NOUN_ADJ_TOPONYM",  # Núi Xanh Long Sơn
                "ADJ_NOUN",          # Xanh Núi (raro, mas dá um “sabor” diferente)
            ],
            [40, 35, 7, 15, 3],
        )

        if pattern == "NOUN_ADJ":
            name = f"{choice(rng, NOUNS)} {choice(rng, ADJ)}"

        elif pattern == "NOUN_TOPONYM":
            name = f"{choice(rng, NOUNS)} {choice(rng, TOPONYMS)}"

        elif pattern == "TOPONYM_NOUN":
            name = f"{choice(rng, TOPONYMS)} {choice(rng, NOUNS)}"

        elif pattern == "NOUN_ADJ_TOPONYM":
            name = f"{choice(rng, NOUNS)} {choice(rng, ADJ)} {choice(rng, TOPONYMS)}"

        else:  # ADJ_NOUN (raro)
            name = f"{choice(rng, ADJ)} {choice(rng, NOUNS)}"

        name = clean_spaces(name)

        if getattr(ctx, "ascii_only", False):
            name = to_ascii(name)

        return title_words(name) if getattr(ctx, "capitalizar", False) else name
