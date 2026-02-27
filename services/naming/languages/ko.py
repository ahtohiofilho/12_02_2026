# shared/naming/languages/ko.py
from __future__ import annotations

from ..types import NamingContext
from ..utils.rng import rng_from_seed, choice, wchoice
from ..utils.text import clean_spaces, title_words, to_ascii
from ..datasets.ko import NOUNS, ADJ, UI_BASE

def _norm(s: str) -> str:
    return clean_spaces(s)

class KoreanGenerator:
    culture = "Korean"

    def province(self, ctx: NamingContext | None = None) -> str:
        ctx = ctx or NamingContext()
        rng = rng_from_seed(ctx.seed)

        pattern = wchoice(rng, ["ADJ_NOUN", "UI_LINK"], [75, 25])

        if pattern == "ADJ_NOUN":
            name = f"{choice(rng, ADJ)} {choice(rng, NOUNS)}"
        else:
            name = f"{choice(rng, UI_BASE)} ui {choice(rng, NOUNS)}"

        name = _norm(name)

        if getattr(ctx, "ascii_only", False):
            name = to_ascii(name)

        return title_words(name) if getattr(ctx, "capitalizar", False) else name
