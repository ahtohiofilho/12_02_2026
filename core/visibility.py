# core/visibility.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

import networkx as nx

from config.unit_stats import get_unit_stats
from config.visibility_rules import VisibilityRules, DEFAULT_VISIBILITY_RULES

Tile = tuple[int, int]
SourceKind = Literal["province", "stack"]
Source = tuple[Tile, SourceKind, int]  # (tile, kind, vision_range)


@dataclass(slots=True)
class CivVisibilityState:
    explored: set[Tile] = field(default_factory=set)
    visible: set[Tile] = field(default_factory=set)


class VisibilityManager:
    """
    Fog of War / Visibilidade.

    Regras:
      - Províncias/capitais revelam por rules.province_range (default: só o tile).
      - Stacks revelam por unidade: max(UnitStats.vision_range) (default: 0 = só o tile).
      - IMPORTANTE: Unidades SEMPRE revelam o próprio tile onde estão.
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
    def _collect_vision_sources(self) -> dict[int, list[Source]]:
        """
        Retorna fontes por civ, tipadas:
          {civ_id: [((x,y), "province", range), ((x,y), "stack", range), ...]}

        Observações:
        - Para províncias: o range real é aplicado depois via rules.province_range.
        - Para stacks: range = max(UnitStats.vision_range) na stack.
        - vision_range=0 significa "só o próprio tile", não "invisível".
        """
        sources: dict[int, list[Source]] = {}

        # 1) Províncias
        provs = getattr(self.planet, "provinces_by_tile", None) or {}
        for tile, prov in provs.items():
            owner = getattr(prov, "owner", None)
            civ_id = getattr(owner, "id", None) if owner is not None else None
            if civ_id is None:
                continue
            sources.setdefault(int(civ_id), []).append((tile, "province", 0))

        # 2) Stacks
        stacks_repo = getattr(self.planet, "stacks", None)
        by_tile = getattr(stacks_repo, "stack_uids_by_tile", None) or {} if stacks_repo else {}

        if stacks_repo is not None:
            for tile, uids in by_tile.items():
                for uid in uids or ():
                    stack = stacks_repo.get_stack(uid)
                    if not stack or stack.is_empty():
                        continue

                    max_vision_range = 0
                    for unit in stack.units:
                        stats = get_unit_stats(unit.unit_key)
                        if stats:
                            max_vision_range = max(max_vision_range, int(stats.vision_range or 0))

                    sources.setdefault(int(stack.owner_id), []).append((tile, "stack", max_vision_range))

        return sources

    # ----------------------------
    # Update principal
    # ----------------------------
    def update_all_civs(
            self,
            *,
            rules: Optional[VisibilityRules] = None,
            vision_range: Optional[int] = None,  # compat opcional com chamadas antigas (override global)
    ) -> None:
        """
        Recalcula visibilidade de todas as civs.

        Regras:
          - Províncias: cutoff = rules.province_range
          - Stacks: cutoff = max(UnitStats.vision_range) na stack
            - Se `vision_range` for passado, ele sobrescreve (modo legado/debug).
        """
        if rules is None:
            rules = DEFAULT_VISIBILITY_RULES

        prov_r = max(0, int(rules.province_range))
        fallback_stack_r = max(0, int(getattr(rules, "default_stack_range", 0)))
        override_stack_r = None if vision_range is None else max(0, int(vision_range))

        graph = getattr(self.planet, "graph", None)
        if graph is None:
            print("⚠️ [FoW] planet.graph ausente; visibilidade não recalculada.")
            return

        # garante states e limpa visible do tick atual
        self.ensure_all_civs_initialized()
        for state in self.states.values():
            state.visible.clear()

        vision_sources = self._collect_vision_sources()
        if not vision_sources:
            # ainda assim, atualiza o digest pra não deixar valor antigo enganoso
            try:
                setattr(self.planet, "visibility_version_sum", 0)
            except Exception:
                pass
            return

        for civ_id, sources in vision_sources.items():
            state = self.get_state(civ_id)

            for source_tile, kind, src_range in sources:
                if source_tile not in graph:
                    continue

                if kind == "province":
                    cutoff = prov_r
                else:
                    cutoff = (
                        override_stack_r
                        if override_stack_r is not None
                        else max(int(src_range), fallback_stack_r)
                    )

                reachable = nx.single_source_shortest_path_length(
                    graph,
                    source_tile,
                    cutoff=cutoff,
                )

                for t in reachable.keys():
                    state.visible.add(t)
                    state.explored.add(t)

                # garantia: stack sempre vê o próprio tile
                if kind == "stack":
                    state.visible.add(source_tile)
                    state.explored.add(source_tile)

        # --- Digest simples para cache/invalidação (economia/rotas) ---
        # explored tende a crescer monotonicamente; a soma dos tamanhos é um proxy barato.
        try:
            total = 0
            for st in self.states.values():
                total += len(st.explored)
            setattr(self.planet, "visibility_version_sum", int(total))
        except Exception:
            pass
