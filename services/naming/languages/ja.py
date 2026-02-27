# shared/naming/languages/ja.py
from __future__ import annotations

from ..types import NamingContext
from ..utils.rng import rng_from_seed, choice, wchoice
from ..utils.text import clean_spaces, title_words, to_ascii
from ..datasets.ja import NOUNS, ADJ_I, NO_NOUN

class JapaneseGenerator:
    culture = "Japanese"

    def province(self, ctx: NamingContext | None = None) -> str:
        ctx = ctx or NamingContext()
        rng = rng_from_seed(ctx.seed)

        pattern = wchoice(rng, ["ADJ_NOUN", "NO_LINK"], [75, 25])

        if pattern == "ADJ_NOUN":
            name = f"{choice(rng, ADJ_I)} {choice(rng, NOUNS)}"
        else:
            name = f"{choice(rng, NO_NOUN)} no {choice(rng, NOUNS)}"

        name = clean_spaces(name)

        if getattr(ctx, "ascii_only", False):
            name = to_ascii(name)

        return title_words(name) if getattr(ctx, "capitalizar", False) else name
