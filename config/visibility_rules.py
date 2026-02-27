# config/visibility_rules.py
from dataclasses import dataclass

@dataclass(frozen=True)
class VisibilityRules:
    province_range: int = 0   # província/capital revela só o próprio tile
    stack_range: int = 2      # stacks/unidades revelam em volta

DEFAULT_VISIBILITY_RULES = VisibilityRules()
