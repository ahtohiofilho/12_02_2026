# core/combat_v2/target_selection.py
from __future__ import annotations

import random
from typing import TypeVar

T = TypeVar("T")
EPS = 1e-12


def weighted_choice(rng: random.Random, items: list[T], weights: list[float]) -> T | None:
    if not items:
        return None
    if len(items) != len(weights):
        raise ValueError("items e weights devem ter o mesmo tamanho")

    total = 0.0
    for w in weights:
        if w > 0:
            total += float(w)

    if total <= EPS:
        return None

    r = rng.random() * total
    acc = 0.0
    for it, w in zip(items, weights):
        w = float(w)
        if w <= 0:
            continue
        acc += w
        if acc >= r:
            return it

    return items[-1]
