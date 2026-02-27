from __future__ import annotations

from ._sinitic_romanized import SiniticRomanizedGenerator
from ..datasets import min as dataset


class MinGenerator(SiniticRomanizedGenerator):
    def __init__(self):
        super().__init__(culture="Min", dataset=dataset)
