# shared/naming/languages/fa.py
from __future__ import annotations

from ..types import NamingContext
from ..utils.rng import rng_from_seed, choice
from ..utils.text import clean_spaces, title_words, to_ascii
from ..datasets.fa import NOUNS, ADJ

_VOWELS = set("aeiou")


def _ezafe(noun: str) -> str:
    """
    Ezāfe romanizado:
    - Em geral: "-e"
    - Após vogal (ou finais muito comuns em -eh): "-ye"
    Regra simples e estável para gerador procedural.
    """
    n = noun.lower().strip()
    if not n:
        return "e"
    if n.endswith(("eh", "e", "a", "o", "u", "i")):
        return "ye"
    # inclui "y" como consoante aqui (ex.: "Kuy-e ...")
    return "e"


class PersianGenerator:
    culture = "Persian"

    def province(self, ctx: NamingContext | None = None) -> str:
        ctx = ctx or NamingContext()
        rng = rng_from_seed(ctx.seed)

        noun = choice(rng, NOUNS)
        adj = choice(rng, ADJ)

        ez = _ezafe(noun)
        name = clean_spaces(f"{noun}-{ez} {adj}")

        if getattr(ctx, "ascii_only", False):
            name = to_ascii(name)

        # Mantém o conector do ezāfe minúsculo em Title Case.
        if getattr(ctx, "capitalizar", False):
            return title_words(name, keep_lower={"e", "ye"})
        return name
