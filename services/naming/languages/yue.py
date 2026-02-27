from __future__ import annotations

from ._sinitic_romanized import SiniticRomanizedGenerator
from ..datasets import yue as dataset


class YueGenerator(SiniticRomanizedGenerator):
    def __init__(self):
        super().__init__(culture="Yue", dataset=dataset)
