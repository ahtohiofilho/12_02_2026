# shared/naming/languages/en.py
from __future__ import annotations

from ..types import NamingContext
from ..utils.rng import rng_from_seed, choice, wchoice
from ..utils.text import clean_spaces, title_words, to_ascii
from ..datasets.en import (
    ADJ_COMMON, ADJ_FANTASY,
    NOUN_GEO, NOUN_CIVIL, NOUN_ABSTRACT,
    ADMIN, NOUN_POSSESSOR, BIOME_HINTS, OF
)
from ..utils.text import to_ascii_strict, to_western_friendly

def _pick_adj(rng):
    # 70% comum, 30% fantasia
    pool = wchoice(rng, ["common", "fantasy"], [70, 30])
    return choice(rng, ADJ_COMMON if pool == "common" else ADJ_FANTASY)

def _pick_head_noun(rng, biome: str | None):
    # base: geo+civil
    pool = list(NOUN_GEO) + list(NOUN_CIVIL)

    # reforça por bioma (se existir)
    if biome and biome in BIOME_HINTS:
        hints = BIOME_HINTS[biome]
        # adiciona 2x para pesar
        pool += hints + hints

    return choice(rng, pool)

def _pick_feature_noun(rng, biome: str | None):
    # para “of the X”: abstrato + geo/civil
    pool = list(NOUN_ABSTRACT) + list(NOUN_GEO) + list(NOUN_CIVIL)
    if biome and biome in BIOME_HINTS:
        hints = BIOME_HINTS[biome]
        pool += hints  # peso leve
    return choice(rng, pool)

def _avoid_same(a: str, b: str) -> bool:
    return a.strip().lower() == b.strip().lower()

class EnglishGenerator:
    culture = "English"

    def province(self, ctx: NamingContext | None = None) -> str:
        ctx = ctx or NamingContext()
        rng = rng_from_seed(ctx.seed)
        biome = ctx.biome

        pattern = wchoice(
            rng,
            ["ADJ HEAD",
             "ADJ ADJ HEAD",
             "HEAD OFTHE FEATURE",
             "POSSESSOR'S HEAD",
             "ADJ HEAD ADMIN",
             "HEAD ADMIN"],
            [40, 12, 18, 10, 12, 8]
        )

        head = _pick_head_noun(rng, biome)
        adj1 = _pick_adj(rng)
        adj2 = _pick_adj(rng)
        feature = _pick_feature_noun(rng, biome)
        possessor = choice(rng, NOUN_POSSESSOR)
        admin = choice(rng, ADMIN)

        # evita "Beacon Beacon", "Shadow Shadow" etc.
        if _avoid_same(adj1, head):
            head = _pick_head_noun(rng, biome)
        if _avoid_same(adj2, adj1):
            adj2 = _pick_adj(rng)
        if _avoid_same(feature, head):
            feature = _pick_feature_noun(rng, biome)

        if pattern == "ADJ HEAD":
            name = f"{adj1} {head}"
        elif pattern == "ADJ ADJ HEAD":
            name = f"{adj1} {adj2} {head}"
        elif pattern == "HEAD OFTHE FEATURE":
            # exemplo: "Valley of the Echo"
            name = f"{head} {OF} {feature}"
        elif pattern == "POSSESSOR'S HEAD":
            # exemplo: "Raven's Hollow"
            name = f"{possessor}'s {head}"
        elif pattern == "ADJ HEAD ADMIN":
            # exemplo: "Silent Ridge County"
            name = f"{adj1} {head} {admin}"
        else:  # "HEAD ADMIN"
            # exemplo: "Harbor Province"
            name = f"{head} {admin}"

        name = clean_spaces(name)

        if getattr(ctx, "sanitizer", "western") == "ascii":
            name = to_ascii_strict(name)
        elif getattr(ctx, "sanitizer", "western") == "western":
            name = to_western_friendly(name)
        else:
            pass  # "unicode": não mexe

        return title_words(name) if ctx.capitalizar else name
