# services/naming/utils/rng.py
from __future__ import annotations
import random
from typing import Sequence, TypeVar

T = TypeVar("T")

def rng_from_seed(seed: int | None) -> random.Random:
    return random.Random() if seed is None else random.Random(seed)

def choice(rng: random.Random, items: Sequence[T]) -> T:
    return rng.choice(items)

def wchoice(rng: random.Random, items: Sequence[T], weights: Sequence[float]) -> T:
    return rng.choices(items, weights=weights, k=1)[0]
