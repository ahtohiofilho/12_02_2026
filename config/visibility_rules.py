# config/visibility_rules.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VisibilityRules:
    """
    Regras globais do Fog of War.

    IMPORTANTE:
    - A visão de STACK é dinâmica por unidade: max(UnitStats.vision_range) na stack.
      Portanto, não existe mais um 'stack_range' fixo como regra principal.
    - default_stack_range existe apenas como fallback/compat (ex.: unidade sem stats).
    """
    province_range: int = 0          # província/capital revela só o próprio tile (por padrão)
    default_stack_range: int = 0     # fallback se não for possível ler vision_range das unidades


DEFAULT_VISIBILITY_RULES = VisibilityRules()
