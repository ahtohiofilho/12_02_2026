# shared/naming/languages/de.py
from __future__ import annotations

from ..types import NamingContext
from ..utils.rng import rng_from_seed, choice, wchoice
from ..utils.text import clean_spaces, title_words
from ..datasets.de import ADJ, NOUNS_M, NOUNS_F, NOUNS_N
from ..utils.text import to_ascii_strict, to_western_friendly

def _def_article(gender: str, number: str) -> str:
    if number == "PL":
        return "die"
    if gender == "M":
        return "der"
    if gender == "F":
        return "die"
    return "das"  # N

def _decline_adj_definite_nom(adj: str, number: str) -> str:
    """
    Declinação de adjetivo com ARTIGO DEFINIDO, caso NOMINATIVO.
    - SG (M/F/N): -e  -> der alt-e Fluss, die alt-e Insel, das alt-e Tal
    - PL: -en        -> die alt-en Flüsse (se você usar plural)
    """
    suffix = "en" if number == "PL" else "e"
    return f"{adj}{suffix}"

class GermanGenerator:
    culture = "German"

    def province(self, ctx: NamingContext | None = None) -> str:
        ctx = ctx or NamingContext()
        rng = rng_from_seed(ctx.seed)

        # plural opcional — recomendo baixo para não encostar em plural irregular de substantivo
        number = wchoice(rng, ["SG", "PL"], [100, 0])

        gender = wchoice(rng, ["M", "F", "N"], [40, 40, 20])

        if gender == "M":
            noun = choice(rng, NOUNS_M)
        elif gender == "F":
            noun = choice(rng, NOUNS_F)
        else:
            noun = choice(rng, NOUNS_N)

        adj = choice(rng, ADJ)

        article = _def_article(gender, number)
        adj_inflected = _decline_adj_definite_nom(adj, number)

        # Nota: noun não está pluralizado aqui (irregular). Mantemos number quase sempre SG.
        name = clean_spaces(f"{article} {adj_inflected} {noun}")

        if getattr(ctx, "sanitizer", "western") == "ascii":
            name = to_ascii_strict(name)
        elif getattr(ctx, "sanitizer", "western") == "western":
            name = to_western_friendly(name)
        else:
            pass  # "unicode": não mexe

        # Title-case em alemão: substantivos devem ficar com inicial maiúscula.
        # `title_words` vai capitalizar tudo; ok na camada 1.
        return title_words(name) if ctx.capitalizar else name
