# shared/naming/languages/id.py
from __future__ import annotations

from ..types import NamingContext
from ..utils.rng import rng_from_seed, choice, wchoice
from ..utils.text import clean_spaces, title_words, to_ascii
from ..datasets.id import NOUNS, ADJ, TOPONYMS


class IndonesianGenerator:
    culture = "Indonesian"

    def province(self, ctx: NamingContext | None = None) -> str:
        ctx = ctx or NamingContext()
        rng = rng_from_seed(ctx.seed)

        pattern = wchoice(
            rng,
            [
                "NOUN_ADJ",          # Gunung Hijau
                "ADJ_NOUN",          # Hijau Gunung (raro)
                "NOUN_TOPONYM",      # Sungai Sinar
                "TOPONYM_NOUN",      # Sinar Sungai (raro)
                "NOUN_ADJ_TOPONYM",  # Hutan Gelap Rimba Jaya
            ],
            [45, 4, 35, 6, 10],
        )

        if pattern == "NOUN_ADJ":
            name = f"{choice(rng, NOUNS)} {choice(rng, ADJ)}"
        elif pattern == "ADJ_NOUN":
            name = f"{choice(rng, ADJ)} {choice(rng, NOUNS)}"
        elif pattern == "NOUN_TOPONYM":
            name = f"{choice(rng, NOUNS)} {choice(rng, TOPONYMS)}"
        elif pattern == "TOPONYM_NOUN":
            name = f"{choice(rng, TOPONYMS)} {choice(rng, NOUNS)}"
        else:  # NOUN_ADJ_TOPONYM
            name = f"{choice(rng, NOUNS)} {choice(rng, ADJ)} {choice(rng, TOPONYMS)}"

        name = clean_spaces(name)

        if getattr(ctx, "ascii_only", False):
            name = to_ascii(name)

        return title_words(name) if getattr(ctx, "capitalizar", False) else name
