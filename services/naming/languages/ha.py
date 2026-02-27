from __future__ import annotations

from ..types import NamingContext
from ..utils.rng import rng_from_seed, choice, wchoice
from ..utils.text import clean_spaces, title_words, to_ascii
from ..datasets.ha import NOUNS, ADJ, TOPONYMS


class HausaGenerator:
    culture = "Hausa"

    def province(self, ctx: NamingContext | None = None) -> str:
        ctx = ctx or NamingContext()
        rng = rng_from_seed(ctx.seed)

        pattern = wchoice(
            rng,
            [
                "NOUN_ADJ",          # Dutse Babba
                "NOUN_TOPONYM",      # Kogi Nasara
                "TOPONYM_NOUN",      # Nasara Kogi (raro)
                "NOUN_ADJ_TOPONYM",  # Daji Duhu Albarka
                "ADJ_NOUN",          # Babba Dutse (raro)
            ],
            [45, 35, 6, 10, 4],
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
