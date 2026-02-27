# services/naming/api.py
from __future__ import annotations

from .registry import get_generator
from .types import NamingContext

def generate_province_name(culture: str, ctx: NamingContext | None = None) -> str:
    gen = get_generator(culture)
    return gen.province(ctx=ctx)
