# core/visibility.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

import networkx as nx

Tile = tuple[int, int]
SourceKind = Literal["province", "stack"]
Source = tuple[Tile, SourceKind]


@dataclass(frozen=True, slots=True)
class VisibilityRules:
    """
    Regras centralizadas de visibilidade por tipo de fonte.
    """
    province_range: int = 0  # província/capital: apenas o tile
    stack_range: int = 2     # stacks/unidades: raio ao redor


DEFAULT_VISIBILITY_RULES = VisibilityRules()


@dataclass(slots=True)
class CivVisibilityState:
    explored: set[Tile] = field(default_factory=set)
    visible: set[Tile] = field(default_factory=set)


class VisibilityManager:
    """
    Fog of War / Visibilidade.

    Regras:
      - Provincias/capitais revelam só o próprio tile (por padrão).
      - Stacks (unidades) revelam ao redor (por padrão).

    Debug:
      - Ative prints passando debug=True no construtor, ou setando manager.debug = True.
    """

    def __init__(self, planet, *, debug: bool = False):
        self.planet = planet
        self.states: dict[int, CivVisibilityState] = {}
        self.debug: bool = bool(debug)
        self._tick: int = 0

    # ----------------------------
    # Utils debug
    # ----------------------------
    def _p(self, msg: str) -> None:
        if self.debug:
            print(msg)

    @staticmethod
    def _safe_len(x: Any) -> int:
        try:
            return len(x)
        except Exception:
            return -1

    @staticmethod
    def _clamp_nonneg(n: int) -> int:
        try:
            n = int(n)
        except Exception:
            n = 0
        return 0 if n < 0 else n

    # ----------------------------
    # Estado
    # ----------------------------
    def get_state(self, civ_id: int) -> CivVisibilityState:
        civ_id = int(civ_id)
        s = self.states.get(civ_id)
        if s is None:
            s = CivVisibilityState()
            self.states[civ_id] = s
            self._p(f"[FoW] +state civ={civ_id} (created)")
        return s

    def ensure_all_civs_initialized(self) -> None:
        civs = getattr(self.planet, "civilizations", None) or []
        self._p(f"[FoW] planet.civilizations = {self._safe_len(civs)}")
        for civ in civs:
            try:
                self.get_state(int(getattr(civ, "id")))
            except Exception as e:
                self._p(f"[FoW] ⚠️ failed init state for civ={civ}: {e}")

    # ----------------------------
    # Coleta de fontes
    # ----------------------------
    def _collect_vision_sources(self) -> dict[int, list[Source]]:
        """
        Retorna fontes por civ, tipadas:
          {civ_id: [((x,y), "province"), ((x,y), "stack"), ...]}
        """
        sources: dict[int, list[Source]] = {}

        # 1) Províncias (capitais / cidades)
        provs = getattr(self.planet, "provinces_by_tile", None) or {}
        self._p(f"[FoW] provinces_by_tile = {self._safe_len(provs)}")

        added_from_prov = 0
        for tile, prov in provs.items():
            owner = getattr(prov, "owner", None)
            if owner is None:
                continue
            civ_id = getattr(owner, "id", None)
            if civ_id is None:
                continue

            sources.setdefault(int(civ_id), []).append((tile, "province"))
            added_from_prov += 1

        # 2) Stacks (unidades)
        stacks_repo = getattr(self.planet, "stacks", None)
        if stacks_repo is None:
            self._p("[FoW] stacks repo = None")
            by_tile = {}
        else:
            by_tile = getattr(stacks_repo, "stack_uids_by_tile", None) or {}

        self._p(f"[FoW] stack_uids_by_tile tiles = {self._safe_len(by_tile)}")

        added_from_stacks = 0
        nonempty_stacks = 0

        if stacks_repo is not None:
            for tile, uids in by_tile.items():
                for uid in uids or ():
                    stack = stacks_repo.get_stack(uid)
                    if not stack:
                        continue
                    if stack.is_empty():
                        continue
                    nonempty_stacks += 1
                    sources.setdefault(int(stack.owner_id), []).append((tile, "stack"))
                    added_from_stacks += 1

        self._p(
            f"[FoW] sources: +prov={added_from_prov}, +stacks={added_from_stacks}, "
            f"nonempty_stacks={nonempty_stacks}, civs_with_sources={len(sources)}"
        )

        # Amostra (pra ver se a capital entrou)
        if self.debug and sources:
            for civ_id in list(sources.keys())[:3]:
                sample = [t for (t, _k) in sources[civ_id][:5]]
                self._p(f"[FoW]   civ={civ_id} sources(sample)={sample}")

        return sources

    # ----------------------------
    # Update principal
    # ----------------------------
    def update_all_civs(
        self,
        *,
        rules: Optional[VisibilityRules] = None,
        vision_range: Optional[int] = None,  # compat opcional com chamadas antigas
    ) -> None:
        """
        Recalcula visibilidade de todas as civs.

        Preferido:
          update_all_civs(rules=VisibilityRules(...))  ou  update_all_civs()

        Compat:
          update_all_civs(vision_range=2)  -> aplica stack_range=2 e province_range=0
        """
        self._tick += 1

        if rules is None:
            if vision_range is None:
                rules = DEFAULT_VISIBILITY_RULES
            else:
                rules = VisibilityRules(
                    province_range=0,
                    stack_range=self._clamp_nonneg(vision_range),
                )

        prov_r = self._clamp_nonneg(rules.province_range)
        stack_r = self._clamp_nonneg(rules.stack_range)

        graph = getattr(self.planet, "graph", None)

        self._p(
            f"\n[FoW] === update_all_civs tick={self._tick} rules="
            f"(prov={prov_r}, stack={stack_r}) ===\n"
            f"[FoW] graph nodes={self._safe_len(getattr(graph, 'nodes', None) or [])} "
            f"edges={getattr(graph, 'number_of_edges', lambda: -1)() if graph else -1}"
        )

        # (A) garante states
        self.ensure_all_civs_initialized()
        self._p(f"[FoW] states currently = {len(self.states)} -> {sorted(self.states.keys())[:10]}")

        # (B) limpa visible
        for state in self.states.values():
            state.visible.clear()

        if graph is None:
            self._p("[FoW] ❌ graph is None -> abort")
            return

        # (C) fontes
        vision_sources = self._collect_vision_sources()
        if not vision_sources:
            self._p("[FoW] ⚠️ vision_sources vazio -> tudo ficará escuro (visible=0).")
            return

        # (D) expansão por civ
        total_visible_added = 0
        total_explored_added = 0

        for civ_id, sources in vision_sources.items():
            state = self.get_state(civ_id)

            before_v = len(state.visible)
            before_e = len(state.explored)

            expansions = 0

            for source_tile, kind in sources:
                if source_tile not in graph:
                    self._p(f"[FoW] ⚠️ source_tile {source_tile} not in graph (civ={civ_id})")
                    continue

                cutoff = prov_r if kind == "province" else stack_r

                reachable = nx.single_source_shortest_path_length(
                    graph,
                    source_tile,
                    cutoff=cutoff,
                )
                expansions += 1

                for t in reachable.keys():
                    state.visible.add(t)
                    state.explored.add(t)

            dv = len(state.visible) - before_v
            de = len(state.explored) - before_e
            total_visible_added += dv
            total_explored_added += de

            self._p(
                f"[FoW] civ={civ_id}: sources={len(sources)} expansions={expansions} "
                f"+visible={dv} (now {len(state.visible)}), +explored={de} (now {len(state.explored)})"
            )

        self._p(
            f"[FoW] totals: +visible={total_visible_added}, +explored={total_explored_added}\n"
            f"[FoW] === end tick={self._tick} ==="
        )
