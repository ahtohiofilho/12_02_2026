from __future__ import annotations

from ..types import NamingContext
from ..utils.rng import rng_from_seed, choice, wchoice
from ..utils.text import clean_spaces, title_words, to_ascii
from ..datasets.tr import (
    NOUNS,
    ADJ,
    LI_BASE,
    COLOR_PREFIX,
    TOPO_HEADS,
    BIOME_HINTS,
    COLONIZABLE_BIOMES,
)

_VOWELS = "aeıioöuü"


def _last_vowel(word: str) -> str | None:
    for ch in reversed(word.lower()):
        if ch in _VOWELS:
            return ch
    return None


def _suffix_li(base: str) -> str:
    v = _last_vowel(base) or "e"
    if v in ("e", "i"):
        suf = "li"
    elif v in ("a", "ı"):
        suf = "lı"
    elif v in ("o", "u"):
        suf = "lu"
    else:  # ö, ü
        suf = "lü"
    return f"{base}{suf}"


def _weighted_pool(base: list[str], hints: list[str] | None, factor: int = 2) -> list[str]:
    if not hints:
        return list(base)
    return list(base) + (list(hints) * factor)


def _pattern_weights(biome: str) -> tuple[list[str], list[float]]:
    patterns = ["ADJ_NOUN", "LI_NOUN", "COLOR_NOUN", "BASE_TOPO", "ADJ_TOPO", "ADJ_LI_NOUN"]
    weights: list[float] = [40, 18, 10, 16, 10, 6]

    boosts = (BIOME_HINTS.get(biome) or {}).get("patterns", {})
    if not boosts:
        return patterns, weights

    return patterns, [w * float(boosts.get(p, 1.0)) for p, w in zip(patterns, weights)]


def _romanize_turkish_min(s: str) -> str:
    """
    Romanização mínima “visual”: evita o dotless i (ı/İ), que costuma parecer bug em UI.
    Mantém os demais diacríticos turcos (ç, ş, ğ, ö, ü) porque você disse que tolera.
    """
    return s.replace("ı", "i").replace("İ", "I")


class TurkishGenerator:
    culture = "Turkish"

    def province(self, ctx: NamingContext | None = None) -> str:
        ctx = ctx or NamingContext()
        rng = rng_from_seed(ctx.seed)

        biome = getattr(ctx, "biome", None)
        if not biome:
            raise ValueError("TurkishGenerator.province requer ctx.biome.")

        if biome not in COLONIZABLE_BIOMES:
            raise ValueError(f"Bioma não colonizável para província: {biome}")

        hint = BIOME_HINTS.get(biome, {})

        noun_pool = _weighted_pool(NOUNS, hint.get("nouns"))
        adj_pool = _weighted_pool(ADJ, hint.get("adjs"))
        base_pool = _weighted_pool(LI_BASE, hint.get("bases"))
        head_pool = _weighted_pool(TOPO_HEADS, hint.get("heads"))

        patterns, weights = _pattern_weights(biome)
        pattern = wchoice(rng, patterns, weights)

        noun = choice(rng, noun_pool)
        adj = choice(rng, adj_pool)

        if pattern == "ADJ_NOUN":
            name = f"{adj} {noun}"

        elif pattern == "LI_NOUN":
            base = choice(rng, base_pool)
            name = f"{_suffix_li(base)} {noun}"

        elif pattern == "COLOR_NOUN":
            col = choice(rng, COLOR_PREFIX)
            name = f"{col} {noun}"

        elif pattern == "BASE_TOPO":
            base = choice(rng, base_pool)
            head = choice(rng, head_pool)
            name = f"{base} {head}"

        elif pattern == "ADJ_TOPO":
            head = choice(rng, head_pool)
            name = f"{adj} {head}"

        else:  # ADJ_LI_NOUN
            base = choice(rng, base_pool)
            name = f"{adj} {_suffix_li(base)} {noun}"

        name = clean_spaces(name)

        # Opção 2: sempre normalizar ı/İ no turco (mesmo sem ascii_only)
        name = _romanize_turkish_min(name)

        # Mantém seu comportamento antigo: se ascii_only=True, aplica a transliteração global também
        if getattr(ctx, "ascii_only", False):
            name = to_ascii(name)

        return title_words(name) if getattr(ctx, "capitalizar", False) else name
