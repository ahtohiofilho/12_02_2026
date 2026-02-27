# shared/naming/languages/zh.py
from __future__ import annotations

from ..types import NamingContext
from ..utils.rng import rng_from_seed, choice, wchoice
from ..utils.text import clean_spaces, title_words, to_ascii
from ..datasets.zh import NOUNS, ADJ, DE_BASE

def _compact_spaces(s: str) -> str:
    # clean_spaces já ajuda; isso é só pra garantir
    return clean_spaces(s)

class ChineseGenerator:
    culture = "Chinese"

    def province(self, ctx: NamingContext | None = None) -> str:
        ctx = ctx or NamingContext()
        rng = rng_from_seed(ctx.seed)

        pattern = wchoice(rng, ["ADJ_NOUN", "DE_LINK"], [75, 25])

        if pattern == "ADJ_NOUN":
            name = f"{choice(rng, ADJ)} {choice(rng, NOUNS)}"
        else:
            name = f"{choice(rng, DE_BASE)} de {choice(rng, NOUNS)}"

        name = _compact_spaces(name)

        if getattr(ctx, "ascii_only", False):
            name = to_ascii(name)

        return title_words(name) if getattr(ctx, "capitalizar", False) else name
