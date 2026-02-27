# services/province_naming_service.py
from __future__ import annotations

import hashlib
from typing import Optional

from services.naming import generate_province_name, NamingContext
from services.naming.unique import unique_name

Tile = tuple[int, int]

def _stable_int_seed(*parts: object, mod: int = 2**32) -> int:
    s = "|".join(str(p) for p in parts).encode("utf-8")
    digest = hashlib.sha256(s).digest()
    n = int.from_bytes(digest[:8], "big", signed=False)
    return int(n % mod)

def generate_unique_province_name(
    *,
    planet,
    civ,
    tile: Tile,
    is_capital: bool,
    sanitizer: str = "western",
) -> str:
    """
    Gera um nome único para província.
    - Determinístico por (planet.id, civ.id, tile, is_capital)
    - Usa biome como hint (se disponível)
    - Unicidade por planeta via planet.used_province_names (cria se não existir)
    """
    planet_id = getattr(planet, "id", "default")
    civ_id = int(getattr(civ, "id", 0))
    culture = str(getattr(civ, "culture", "English") or "English")

    # biome hint
    biome: Optional[str] = None
    try:
        g = getattr(planet, "graph", None)
        if g is not None and tile in g:
            biome = g.nodes[tile].get("bioma")
    except Exception:
        biome = None

    used: set[str] = getattr(planet, "used_province_names", None)
    if used is None:
        used = set()
        setattr(planet, "used_province_names", used)

    ctx0 = NamingContext(
        seed=_stable_int_seed(planet_id, civ_id, tile, "capital" if is_capital else "province"),
        sanitizer=sanitizer,
        capitalizar=True,
        kind="province",
        biome=biome,
    )

    def make(ctx: NamingContext) -> str:
        return generate_province_name(culture, ctx=ctx)

    return unique_name(
        used=used,
        make=make,
        ctx=ctx0,
        normalize_key=lambda s: s.strip().lower(),
    )
