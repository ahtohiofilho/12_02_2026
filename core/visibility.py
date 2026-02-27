# core/visibility.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

import networkx as nx

from config.unit_stats import get_unit_stats

Tile = tuple[int, int]
SourceKind = Literal["province", "stack"]
Source = tuple[Tile, SourceKind, int]  # (tile, kind, range)


@dataclass(frozen=True, slots=True)
class VisibilityRules:
    """Regras centralizadas de visibilidade por tipo de fonte."""
    province_range: int = 0  # província/capital: apenas o tile


DEFAULT_VISIBILITY_RULES = VisibilityRules()


@dataclass(slots=True)
class CivVisibilityState:
    explored: set[Tile] = field(default_factory=set)
    visible: set[Tile] = field(default_factory=set)


class VisibilityManager:
    """
    Fog of War / Visibilidade.

    Regras:
      - Províncias/capitais revelam só o próprio tile (province_range=0).
      - Stacks revelam de acordo com o maior vision_range das unidades contidas.
    """

    def __init__(self, planet):
        self.planet = planet
        self.states: dict[int, CivVisibilityState] = {}

    # ----------------------------
    # Estado
    # ----------------------------
    def get_state(self, civ_id: int) -> CivVisibilityState:
        civ_id = int(civ_id)
        state = self.states.get(civ_id)
        if state is None:
            state = CivVisibilityState()
            self.states[civ_id] = state
        return state

    def ensure_all_civs_initialized(self) -> None:
        civs = getattr(self.planet, "civilizations", None) or []
        for civ in civs:
            civ_id = getattr(civ, "id", None)
            if civ_id is None:
                continue
            self.get_state(int(civ_id))

    # ----------------------------
    # Coleta de fontes
    # ----------------------------
    @staticmethod
    def _stack_vision_range(stack) -> int:
        """
        Retorna o maior vision_range entre todas as unidades da stack.
        Se nenhuma unidade tiver stats conhecidos, retorna 0.
        """
        best = 0
        for unit in getattr(stack, "units", []):
            unit_key = getattr(unit, "key", None) or getattr(unit, "unit_key", None)
            if unit_key is None:
                continue
            stats = get_unit_stats(unit_key)
            if stats is None:
                continue
            best = max(best, stats.vision_range)
        return best

    def _collect_vision_sources(self) -> dict[int, list[Source]]:
        """
        Retorna fontes por civ, tipadas:
          {civ_id: [((x,y), "province", range), ((x,y), "stack", range), ...]}
        """
        sources: dict[int, list[Source]] = {}

        # 1) Províncias — range sempre 0 (só o próprio tile)
        provs = getattr(self.planet, "provinces_by_tile", None) or {}
        for tile, prov in provs.items():
            owner = getattr(prov, "owner", None)
            civ_id = getattr(owner, "id", None) if owner is not None else None
            if civ_id is None:
                continue
            sources.setdefault(int(civ_id), []).append((tile, "province", 0))

        # 2) Stacks — range calculado pelas unidades contidas
        stacks_repo = getattr(self.planet, "stacks", None)
        by_tile = getattr(stacks_repo, "stack_uids_by_tile", None) or {} if stacks_repo else {}

        if stacks_repo is not None:
            for tile, uids in by_tile.items():
                for uid in uids or ():
                    stack = stacks_repo.get_stack(uid)
                    if not stack or stack.is_empty():
                        continue
                    vr = self._stack_vision_range(stack)
                    sources.setdefault(int(stack.owner_id), []).append((tile, "stack", vr))

        return sources

    # ----------------------------
    # Update principal
    # ----------------------------
    def update_all_civs(
        self,
        *,
        rules: Optional[VisibilityRules] = None,
        vision_range: Optional[int] = None,  # compat com chamadas antigas
    ) -> None:
        if rules is None:
            rules = DEFAULT_VISIBILITY_RULES

        prov_r = max(0, int(rules.province_range))

        graph = getattr(self.planet, "graph", None)
        if graph is None:
            print("⚠️ [FoW] planet.graph ausente; visibilidade não recalculada.")
            return

        self.ensure_all_civs_initialized()
        for state in self.states.values():
            state.visible.clear()

        vision_sources = self._collect_vision_sources()
        if not vision_sources:
            return

        for civ_id, sources in vision_sources.items():
            state = self.get_state(civ_id)

            for source_tile, kind, source_range in sources:
                if source_tile not in graph:
                    continue

                cutoff = prov_r if kind == "province" else source_range
                reachable = nx.single_source_shortest_path_length(
                    graph,
                    source_tile,
                    cutoff=cutoff,
                )

                for t in reachable.keys():
                    state.visible.add(t)
                    state.explored.add(t)
