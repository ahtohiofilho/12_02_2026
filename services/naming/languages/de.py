# shared/naming/languages/de.py
from __future__ import annotations

from ..types import NamingContext
from ..utils.rng import rng_from_seed, choice, wchoice
from ..utils.text import clean_spaces, title_words
from ..datasets.de import ADJ, NOUNS_M, NOUNS_F, NOUNS_N
from ..utils.text import to_ascii_strict, to_western_friendly


def _decline_adj_strong(adj: str, gender: str) -> str:
    """
    Declinação forte do adjetivo em nominativo sem artigo.
    Usada para topônimos naturais (ex: Goldener Tempel, Alte Insel).

    - Masculino: -er (Goldener, Alter)
    - Feminino:  -e  (Alte, Neue)
    - Neutro:    -es (Altes, Neues)
    """
    if gender == "M":
        return f"{adj}er"
    elif gender == "F":
        return f"{adj}e"
    else:  # Neutro
        return f"{adj}es"


class GermanGenerator:
    culture = "German"

    def province(self, ctx: NamingContext | None = None) -> str:
        ctx = ctx or NamingContext()
        rng = rng_from_seed(ctx.seed)

        # Escolhe gênero (masculino/feminino/neutro)
        gender = wchoice(rng, ["M", "F", "N"], [40, 40, 20])

        # Seleciona substantivo conforme gênero
        if gender == "M":
            noun = choice(rng, NOUNS_M)
        elif gender == "F":
            noun = choice(rng, NOUNS_F)
        else:  # Neutro
            noun = choice(rng, NOUNS_N)

        # Seleciona e declina adjetivo (sem artigo = declinação forte)
        adj_base = choice(rng, ADJ)
        adj = _decline_adj_strong(adj_base, gender)

        # Ordem: Adjetivo + Substantivo (padrão natural para topônimos alemães)
        name = clean_spaces(f"{adj} {noun}")

        # Sanitização
        if getattr(ctx, "sanitizer", "western") == "ascii":
            name = to_ascii_strict(name)
        elif getattr(ctx, "sanitizer", "western") == "western":
            name = to_western_friendly(name)
        # "unicode": não altera

        # Title-case: substantivos alemães sempre começam com maiúscula
        return title_words(name) if ctx.capitalizar else name