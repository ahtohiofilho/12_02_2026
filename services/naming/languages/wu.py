from __future__ import annotations

from ._sinitic_romanized import SiniticRomanizedGenerator
from ..datasets import wu as dataset


class WuGenerator(SiniticRomanizedGenerator):
    def __init__(self):
        super().__init__(culture="Wu", dataset=dataset)
