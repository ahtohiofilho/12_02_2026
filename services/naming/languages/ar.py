# shared/naming/languages/ar.py
from __future__ import annotations

from ..types import NamingContext
from ..utils.rng import rng_from_seed, choice, wchoice
from ..utils.text import clean_spaces, title_words, to_ascii
from ..datasets.ar import NOUNS, ADJ, IDAFA_BASE, TOPONYMS, BIOME_HINTS

def _al(word: str) -> str:
    # Layer 1: simple article, no sun-letter assimilation
    return f"al-{word}"

def _norm_key(s: str) -> str:
    # normaliza para comparar repetição (ignorando case e pontuação simples)
    return (
        s.strip()
         .lower()
         .replace("-", " ")
         .replace("'", "")
    )

def _avoid_same(a: str, b: str) -> bool:
    return _norm_key(a) == _norm_key(b)

def _weighted_pool(base: list[str], hints: list[str] | None) -> list[str]:
    # estratégia simples: adiciona hints duplicados para "pesar"
    if not hints:
        return list(base)
    return list(base) + list(hints) + list(hints)

class ArabicGenerator:
    culture = "Arabic"

    def province(self, ctx: NamingContext | None = None) -> str:
        ctx = ctx or NamingContext()
        rng = rng_from_seed(ctx.seed)
        biome = getattr(ctx, "biome", None)

        hints = BIOME_HINTS.get(biome) if biome else None

        # Pools ponderados
        noun_pool = _weighted_pool(NOUNS, hints)
        adj_pool = _weighted_pool(ADJ, hints)
        idafa_pool = _weighted_pool(IDAFA_BASE, hints)
        topo_pool = _weighted_pool(TOPONYMS, hints)

        pattern = wchoice(
            rng,
            [
                "NOUN_ADJ",        # Wadi Qadim
                "NOUN_AL_ADJ",     # Wadi al-Qadim
                "NOUN_IDAFA",      # Wadi al-Rih
                "NOUN_TOPONYM",    # Jabal Nur
                "TOPONYM_NOUN",    # Nur Jabal (raro)
            ],
            [40, 18, 24, 14, 4],
        )

        # picks iniciais
        noun = choice(rng, noun_pool)
        adj = choice(rng, adj_pool)
        base = choice(rng, idafa_pool)
        topo = choice(rng, topo_pool)

        # Anti-repetição básica: repesca algumas vezes se colidir
        # (mantém simples e determinístico por seed)
        for _ in range(6):
            # Evita "noun noun" (ou equivalentes) e "X al-X"
            if _avoid_same(noun, adj):
                adj = choice(rng, adj_pool)
                continue
            if _avoid_same(noun, base):
                base = choice(rng, idafa_pool)
                continue
            if _avoid_same(topo, noun):
                topo = choice(rng, topo_pool)
                continue
            if _avoid_same(topo, base):
                base = choice(rng, idafa_pool)
                continue
            break

        if pattern == "NOUN_ADJ":
            name = f"{noun} {adj}"
        elif pattern == "NOUN_AL_ADJ":
            # evita "X al-X" especificamente aqui também
            if _avoid_same(noun, adj):
                adj = choice(rng, adj_pool)
            name = f"{noun} {_al(adj)}"
        elif pattern == "NOUN_IDAFA":
            if _avoid_same(noun, base):
                base = choice(rng, idafa_pool)
            name = f"{noun} {_al(base)}"
        elif pattern == "NOUN_TOPONYM":
            if _avoid_same(noun, topo):
                topo = choice(rng, topo_pool)
            name = f"{noun} {topo}"
        else:  # TOPONYM_NOUN
            if _avoid_same(topo, noun):
                noun = choice(rng, noun_pool)
            name = f"{topo} {noun}"

        name = clean_spaces(name)

        if getattr(ctx, "ascii_only", False):
            name = to_ascii(name)

        return title_words(name) if getattr(ctx, "capitalizar", False) else name
