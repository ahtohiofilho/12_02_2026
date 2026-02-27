# services/naming/utils/sanitize.py
from __future__ import annotations

from .text import to_ascii_strict, to_western_friendly

def apply_sanitizer(name: str, sanitizer: str) -> str:
    sanitizer = (sanitizer or "western").lower()
    if sanitizer == "ascii":
        return to_ascii_strict(name)
    if sanitizer == "western":
        return to_western_friendly(name)
    return name  # "unicode"
