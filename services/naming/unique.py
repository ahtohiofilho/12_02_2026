# services/naming/unique.py
from __future__ import annotations

from collections.abc import Callable
from .types import NamingContext

def unique_name(
    used: set[str],
    make: Callable[[NamingContext], str],
    ctx: NamingContext,
    max_attempts: int = 2000,
    normalize_key: Callable[[str], str] | None = None,
) -> str:
    normalize_key = normalize_key or (lambda s: s)

    base_seed = ctx.seed
    for i in range(max_attempts):
        seed_i = None if base_seed is None else (int(base_seed) + i * 1009)

        candidate = make(NamingContext(
            seed=seed_i,
            sanitizer=ctx.sanitizer,
            capitalizar=ctx.capitalizar,
            kind=ctx.kind,
            biome=ctx.biome,
        ))

        key = normalize_key(candidate)
        if key not in used:
            used.add(key)
            return candidate

    raise RuntimeError(f"Falha ao gerar nome único após {max_attempts} tentativas.")
