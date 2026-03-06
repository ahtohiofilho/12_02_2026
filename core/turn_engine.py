# core/turn_engine.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable

import networkx as nx

from core.combat.apply import apply_kills
from core.combat.tile_battle import TileBattleReport, UnitRef
from core.diplomacy import DiplomacyMatrix, Relation
from core.stacks.repo import StackRepository

# v2: engine e runtime
from core.combat_v2 import TileCombatEngineV2
from core.combat_v2.api import UnitRuntime, normalize_evasion_mode

# v2: continua usando CombatResolver 1v1 existente
from core.combat.models import CombatContext
from core.combat.modifiers import AdvantageModifier
from core.combat.resolver import CombatResolver

from config.movement_costs import get_entry_cost


# ─── Resultado individual ─────────────────────────────────────────────

class MoveResultType(Enum):
    MOVED = auto()
    MOVED_AFTER_VICTORY = auto()
    HELD_AFTER_VICTORY = auto()
    DEFEATED = auto()
    BLOCKED = auto()
    INVALID = auto()


@dataclass(frozen=True, slots=True)
class MoveResult:
    result_type: MoveResultType
    reason: str
    stack_uid: str = ""
    dst_tile: tuple[int, int] = (0, 0)
    battle_report: TileBattleReport | None = None
    debug: dict[str, Any] = field(default_factory=dict)


# ─── Ordem pendente ───────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class MoveOrder:
    """Uma ordem submetida por uma civilização, ainda não processada."""
    stack_uid: str
    dst_tile: tuple[int, int]


# ─── Resultado do turno inteiro ───────────────────────────────────────

@dataclass(slots=True)
class TurnReport:
    """Resultado consolidado de todas as ordens de um turno."""
    turn_number: int
    results: list[MoveResult] = field(default_factory=list)
    battles: list[TileBattleReport] = field(default_factory=list)

    # v2: log completo interno do combate v2 (NÃO é para UI direta)
    combat_log_v2: list[dict] = field(default_factory=list)

    # ✅ snapshots pré-turno (preenchidos no Controller)
    pre_visible_by_civ: dict[int, set[tuple[int, int]]] = field(default_factory=dict)
    pre_owned_tiles_by_civ: dict[int, set[tuple[int, int]]] = field(default_factory=dict)

    @property
    def total_orders(self) -> int:
        return len(self.results)

    @property
    def total_battles(self) -> int:
        return len(self.battles)

    def results_for_civ(self, civ_id: int, stacks: StackRepository) -> list[MoveResult]:
        civ_id = int(civ_id)
        civ_stack_uids = stacks.stack_uids_by_owner.get(civ_id, set())
        return [r for r in self.results if r.stack_uid in civ_stack_uids]

    def combat_log_for_civ(self, civ_id: int) -> list[dict]:
        """
        Regras de visibilidade do log de batalha (anti-spoiler).

        Inclui:
          - tiles owned no começo do turno
          - tiles visíveis no começo do turno
          - tiles onde a própria civ atacou

        Redação:
          - origem do atacante inimigo vira direção aproximada se a origem não era visível/owned
        """
        civ_id = int(civ_id)
        pre_visible = set(self.pre_visible_by_civ.get(civ_id, set()) or ())
        pre_owned = set(self.pre_owned_tiles_by_civ.get(civ_id, set()) or ())

        def dir_from_to(src: tuple[int, int], dst: tuple[int, int]) -> str:
            dx = src[0] - dst[0]
            dy = src[1] - dst[1]
            sx = 0 if dx == 0 else (1 if dx > 0 else -1)
            sy = 0 if dy == 0 else (1 if dy > 0 else -1)
            mapping = {
                (0, 1): "N", (1, 1): "NE", (1, 0): "E", (1, -1): "SE",
                (0, -1): "S", (-1, -1): "SW", (-1, 0): "W", (-1, 1): "NW",
                (0, 0): "HERE",
            }
            return mapping.get((sx, sy), "UNK")

        def can_reveal_tile(t: tuple[int, int]) -> bool:
            return (t in pre_visible) or (t in pre_owned)

        out: list[dict] = []
        for e in self.combat_log_v2:
            defender_tile_raw = e.get("defender_tile")
            if not defender_tile_raw:
                continue
            defender_tile = tuple(defender_tile_raw)

            attacker_origins = e.get("attacker_origins") or []
            civ_attacked_here = any(int(a.get("attacker_civ_id", -1)) == civ_id for a in attacker_origins)

            include = (defender_tile in pre_visible) or (defender_tile in pre_owned) or civ_attacked_here
            if not include:
                continue

            redacted_origins: list[dict] = []
            for a in attacker_origins:
                a_civ = int(a.get("attacker_civ_id", -1))
                from_tile_raw = a.get("from_tile")
                from_tile = tuple(from_tile_raw) if from_tile_raw else None

                entry = {
                    "attacker_civ_id": a_civ,
                    "stack_uid": a.get("stack_uid", ""),
                }

                if from_tile is None:
                    redacted_origins.append(entry)
                    continue

                if a_civ == civ_id or can_reveal_tile(from_tile):
                    entry["from_tile"] = from_tile
                else:
                    entry["from_dir"] = dir_from_to(from_tile, defender_tile)

                redacted_origins.append(entry)

            safe = dict(e)
            safe["attacker_origins"] = redacted_origins
            out.append(safe)

        return out


# ─── Engine ───────────────────────────────────────────────────────────

class TurnEngine:
    """
    Motor de turnos com resolução simultânea.

    Consolidação (combate v2.1):
    - Mantém a fase de movimentos (MoveOrder) como está.
    - Adiciona suporte a combate remoto SEM “pull”:
        * o pool remoto deve vir de ordens explícitas ATTACK_TILE guardadas no CommandManager
          (não é o TurnEngine que “puxa” ninguém sozinho).
        * O TurnEngine recebe um callback attack_orders_for_tile(tile)->list[dict] opcional,
          que retorna somente stacks com ordem explícita de atacar aquele tile.
    - EVASIVE: quem está EVASIVE pode ser atacado, mas não pode atacar.
      (o filtro primário está no combat_v2.engine, mas aqui também evitamos incluir
       remotos sem necessidade quando evasion_mode for EVASIVE, se informado.)
    """

    def __init__(
        self,
        stacks: StackRepository,
        diplomacy: DiplomacyMatrix,
        *,
        biome_at: Callable[[tuple[int, int]], str] | None = None,
        duel_resolver: CombatResolver | None = None,
        # ✅ NOVO: fonte de ordens explícitas de ataque remoto (sem acoplamento ao CommandManager)
        attack_orders_for_tile: Callable[[tuple[int, int]], list[dict[str, Any]]] | None = None,
        # ✅ NOVO: provedor do grafo (para distância). Se None, combate remoto fica desabilitado.
        graph_provider: Callable[[], Any] | None = None,
    ):
        self.stacks = stacks
        self.diplomacy = diplomacy
        self.turn_number = 0

        if biome_at is None:
            raise ValueError("TurnEngine requer biome_at(tile)->str.")
        self.biome_at = biome_at

        self.attack_orders_for_tile = attack_orders_for_tile
        self.graph_provider = graph_provider

        if duel_resolver is None:
            duel_resolver = CombatResolver(modifiers=[AdvantageModifier()])

        self.combat_engine_v2 = TileCombatEngineV2(
            resolver=duel_resolver,
            diplomacy=self.diplomacy,
        )

        self._pending_orders: list[MoveOrder] = []

    # ─── Fase 1: Coleta de ordens ─────────────────────────────────

    def submit_order(self, stack_uid: str, dst_tile: tuple[int, int]) -> None:
        self._pending_orders.append(MoveOrder(stack_uid=stack_uid, dst_tile=dst_tile))

    def clear_orders(self) -> None:
        self._pending_orders.clear()

    @property
    def pending_count(self) -> int:
        return len(self._pending_orders)

    # ─── Fase 2: Resolução simultânea ─────────────────────────────

    def resolve_turn(self) -> TurnReport:
        self.turn_number += 1
        report = TurnReport(turn_number=self.turn_number)

        orders = list(self._pending_orders)
        self._pending_orders.clear()
        if not orders:
            return report

        # ── 1) Validar ordens ─────────────────────────────────────
        validated: list[tuple[MoveOrder, int]] = []
        for order in orders:
            invalid = self._validate_order(order)
            if invalid is not None:
                report.results.append(invalid)
                continue

            stack = self.stacks.get_stack(order.stack_uid)
            assert stack is not None
            validated.append((order, stack.owner_id))

        # ── 2) Snapshot: residentes por tile + origem das stacks ───
        tile_units_snapshot: dict[tuple[int, int], list[UnitRef]] = {}
        stack_origin_tile: dict[str, tuple[int, int]] = {}

        for tile, stack_uids in self.stacks.stack_uids_by_tile.items():
            tile = (int(tile[0]), int(tile[1]))

            units: list[UnitRef] = []
            for stack_uid in stack_uids:
                s = self.stacks.get_stack(stack_uid)
                if not s or s.is_empty():
                    continue

                if s.uid not in stack_origin_tile:
                    st = getattr(s, "tile", None)
                    stack_origin_tile[s.uid] = (int(st[0]), int(st[1])) if st is not None else tile

                for u in s.units:
                    units.append(
                        UnitRef(
                            unit_key=u.unit_key,
                            uid=u.uid,
                            owner_id=s.owner_id,
                            meta={"stack_uid": s.uid, "resident": True},
                        )
                    )

            if units:
                tile_units_snapshot[tile] = units

        for order, _civ_id in validated:
            if order.stack_uid in stack_origin_tile:
                continue
            s = self.stacks.get_stack(order.stack_uid)
            if s and (not s.is_empty()) and getattr(s, "tile", None) is not None:
                st = s.tile
                stack_origin_tile[order.stack_uid] = (int(st[0]), int(st[1]))

        # ── 3) Agrupar ordens por destino ──────────────────────────
        orders_by_dst: dict[tuple[int, int], list[tuple[MoveOrder, int]]] = {}
        for order, civ_id in validated:
            dst = (int(order.dst_tile[0]), int(order.dst_tile[1]))
            orders_by_dst.setdefault(dst, []).append((MoveOrder(order.stack_uid, dst), civ_id))

        # ── 4) Processar cada tile ─────────────────────────────────
        pending_moves: list[tuple[str, tuple[int, int]]] = []
        all_killed_uids: list[str] = []

        for dst_tile, tile_orders in orders_by_dst.items():
            tile_results, tile_moves, tile_killed, tile_logs = self._resolve_tile(
                dst_tile=dst_tile,
                tile_orders=tile_orders,
                tile_units_snapshot=tile_units_snapshot,
                stack_origin_tile=stack_origin_tile,
            )
            report.results.extend(tile_results)
            pending_moves.extend(tile_moves)
            all_killed_uids.extend(tile_killed)
            report.combat_log_v2.extend(tile_logs)

            for r in tile_results:
                if r.battle_report is not None:
                    report.battles.append(r.battle_report)

        # ── 5) Aplicar baixas ──────────────────────────────────────
        apply_kills(self.stacks, all_killed_uids)

        # ── 6) Aplicar movimentos ──────────────────────────────────
        for stack_uid, dst_tile in pending_moves:
            stack = self.stacks.get_stack(stack_uid)
            if stack and not stack.is_empty():
                self.stacks.move_stack_position_only(stack_uid, dst_tile)

        # ── 7) Limpeza ─────────────────────────────────────────────
        self._cleanup_all_empty_stacks()

        return report

    # ─── Resolução por tile ───────────────────────────────────────

    def _resolve_tile(
            self,
            *,
            dst_tile: tuple[int, int],
            tile_orders: list[tuple[MoveOrder, int]],
            tile_units_snapshot: dict[tuple[int, int], list[UnitRef]],
            stack_origin_tile: dict[str, tuple[int, int]],
    ) -> tuple[list[MoveResult], list[tuple[str, tuple[int, int]]], list[str], list[dict]]:
        """
        Resolve um tile (movimentos entrantes + combate local + combate remoto por ordens explícitas).
        Correções consolidadas:
          (A) get_unit_stats sempre disponível (evita NameError).
          (B) remoto usa origem do snapshot (stack_origin_tile) para consistência simultânea e logging.
          (C) "houve combate" passa a depender de report_v2.duels (combate efetivo),
              e não apenas de "há ENEMY no pool".
        """
        from config.unit_stats import get_unit_stats  # ✅ (A) garante para local+remoto
        dst_tile = (int(dst_tile[0]), int(dst_tile[1]))
        results: list[MoveResult] = []
        moves: list[tuple[str, tuple[int, int]]] = []
        killed: list[str] = []
        tile_logs: list[dict] = []
        resident_units = list(tile_units_snapshot.get(dst_tile, []))
        resident_civs = {u.owner_id for u in resident_units}
        arriving_civs: dict[int, list[MoveOrder]] = {}
        for order, civ_id in tile_orders:
            arriving_civs.setdefault(int(civ_id), []).append(order)
        arriving_ids = set(arriving_civs.keys())
        # ── BLOCK por civ (NEUTRAL) ────────────────────────────────
        blocked_civs = self._blocked_civs_for_tile(resident_civs, arriving_ids)
        for civ_id in blocked_civs:
            present = (resident_civs | arriving_ids) - {civ_id}
            present_rel = {o: self.diplomacy.relation(civ_id, o).name for o in present}
            for order in arriving_civs.get(civ_id, []):
                results.append(
                    MoveResult(
                        result_type=MoveResultType.BLOCKED,
                        reason="Entrada cancelada: há pelo menos um NEUTRAL (residente ou entrante) para esta civ.",
                        stack_uid=order.stack_uid,
                        dst_tile=dst_tile,
                        debug={"present_relations": present_rel, "blocked_by_civ_rule": True},
                    )
                )
        allowed_orders = [(o, c) for (o, c) in tile_orders if int(c) not in blocked_civs]
        if not allowed_orders:
            return results, moves, killed, tile_logs
        # ── Entrantes (das stacks) ─────────────────────────────────
        entrant_units: list[UnitRef] = []
        invalid_stack_uids: set[str] = set()
        for order, civ_id in allowed_orders:
            stack = self.stacks.get_stack(order.stack_uid)
            if stack is None or stack.is_empty():
                invalid_stack_uids.add(order.stack_uid)
                results.append(
                    MoveResult(
                        result_type=MoveResultType.INVALID,
                        reason="Stack entrante não existe ou está vazia.",
                        stack_uid=order.stack_uid,
                        dst_tile=dst_tile,
                    )
                )
                continue
            for u in stack.units:
                entrant_units.append(
                    UnitRef(
                        unit_key=u.unit_key,
                        uid=u.uid,
                        owner_id=int(civ_id),
                        meta={"stack_uid": stack.uid, "resident": False},
                    )
                )
        # ── Pool por domínio (bioma) ───────────────────────────────
        biome = self.biome_at(dst_tile)
        aquatic = biome in {"Coast", "Sea", "Ocean"}

        def domain_ok(u: UnitRef) -> bool:
            from config.unit_stats import UnitCategory
            st = get_unit_stats(u.unit_key)
            if not st:
                return True
            if st.category == UnitCategory.AIR:
                return False
            if aquatic:
                sub = getattr(UnitCategory, "SUB", None)
                if sub is not None:
                    return st.category in (UnitCategory.NAVAL, sub)
                return st.category == UnitCategory.NAVAL
            return st.category == UnitCategory.LAND

        pool_local = [u for u in (resident_units + entrant_units) if domain_ok(u)]
        # ── Pool REMOTO (sem pull): somente por ordem explícita ────
        remote_unit_runtimes: list[UnitRuntime] = []
        remote_attackers_meta: list[dict] = []  # para logs
        graph = self.graph_provider() if callable(self.graph_provider) else None
        can_remote = (graph is not None) and callable(self.attack_orders_for_tile)
        dist_from_dst: dict[tuple[int, int], int] | None = None
        if can_remote:
            G = graph.to_undirected(as_view=True) if hasattr(graph, "to_undirected") else graph
            dist_from_dst = nx.single_source_shortest_path_length(G, dst_tile)

            def distance_fn(a: tuple[int, int], b: tuple[int, int]) -> int | None:
                if a == b:
                    return 0
                if b == dst_tile:
                    return dist_from_dst.get(a) if dist_from_dst is not None else None
                try:
                    return nx.shortest_path_length(G, a, b)
                except Exception:
                    return None
        else:
            distance_fn = None  # type: ignore[assignment]
        if can_remote and dist_from_dst is not None:
            remote_orders = list(self.attack_orders_for_tile(dst_tile) or ())
            for ro in remote_orders:
                stack_uid = str(ro.get("stack_uid", "") or "")
                if not stack_uid:
                    continue
                stack = self.stacks.get_stack(stack_uid)
                if stack is None or stack.is_empty():
                    continue
                # ✅ (B) origem consistente com snapshot do turno
                origin_tile = stack_origin_tile.get(stack_uid)
                if origin_tile is None:
                    ot = getattr(stack, "tile", None)
                    if ot is None:
                        continue
                    origin_tile = (int(ot[0]), int(ot[1]))
                else:
                    origin_tile = (int(origin_tile[0]), int(origin_tile[1]))
                # não inclui se já é local (evita duplicar)
                if origin_tile == dst_tile:
                    continue
                dist = dist_from_dst.get(origin_tile)
                if dist is None:
                    continue
                owner_civ_id = int(ro.get("owner_civ_id", stack.owner_id))
                evasion_mode_req = str(ro.get("evasion_mode", "COMMITTED") or "COMMITTED").upper()
                target_layer = ro.get("target_layer", None)  # reservado
                # log de origem (para redaction no TurnReport)
                remote_attackers_meta.append(
                    {
                        "attacker_civ_id": owner_civ_id,
                        "stack_uid": stack_uid,
                        "from_tile": origin_tile,
                        "to_tile": dst_tile,
                        "dist": int(dist),
                        "target_layer": target_layer,
                    }
                )
                for u in stack.units:
                    st = get_unit_stats(u.unit_key)
                    u_range = int(getattr(st, "range", 0) or 0) if st else 0
                    layer = str(getattr(st, "layer", "SURFACE") or "SURFACE") if st else "SURFACE"
                    can_evasive = bool(getattr(st, "can_evasive", False)) if st else False
                    # alcance: se não alcança, nem entra no runtime (economiza)
                    if dist > u_range:
                        continue
                    # turns_per_tile é velocidade/custo (não é elegibilidade evasive)
                    origin_biome = self.biome_at(origin_tile)
                    tpt = float(get_entry_cost(u.unit_key, origin_biome) or 999.0)
                    # ✅ contrato 2.1.1: normaliza EVASIVE por capacidade intrínseca (can_evasive)
                    effective_evasion = normalize_evasion_mode(evasion_mode_req, can_evasive=can_evasive)
                    remote_unit_runtimes.append(
                        UnitRuntime(
                            uid=u.uid,
                            unit_key=u.unit_key,
                            owner_id=owner_civ_id,
                            tile=origin_tile,
                            layer=layer,
                            range=u_range,
                            turns_per_tile=tpt,
                            can_evasive=can_evasive,
                            evasion_mode=effective_evasion,
                            primary_target_tile=dst_tile,
                        )
                    )
        # ── Decide se existe ENEMY no pool total (local + remoto) ───
        civs_in_pool = {u.owner_id for u in pool_local} | {u.owner_id for u in remote_unit_runtimes}
        civ_list = list(civs_in_pool)
        has_enemy = False
        for i in range(len(civ_list)):
            for j in range(i + 1, len(civ_list)):
                if self.diplomacy.relation(civ_list[i], civ_list[j]) == Relation.ENEMY:
                    has_enemy = True
                    break
            if has_enemy:
                break
        battle_report: TileBattleReport | None = None  # legado
        # ── Combate v2.1 ───────────────────────────────────────────
        report_v2 = None
        if has_enemy and (pool_local or remote_unit_runtimes):
            runtimes: list[UnitRuntime] = []
            # locais viram UnitRuntime com tile==dst_tile
            for ur in pool_local:
                st = get_unit_stats(ur.unit_key)
                u_range = int(getattr(st, "range", 0) or 0) if st else 0
                layer = str(getattr(st, "layer", "SURFACE") or "SURFACE") if st else "SURFACE"
                can_evasive = bool(getattr(st, "can_evasive", False)) if st else False
                tpt = float(get_entry_cost(ur.unit_key, biome) or 999.0)
                runtimes.append(
                    UnitRuntime(
                        uid=ur.uid,
                        unit_key=ur.unit_key,
                        owner_id=int(ur.owner_id),
                        tile=dst_tile,
                        layer=layer,
                        range=u_range,
                        turns_per_tile=tpt,
                        can_evasive=can_evasive,
                        evasion_mode="COMMITTED",  # TODO: quando houver ordem local de postura, derive aqui
                        primary_target_tile=None,
                    )
                )
            # remotos já estão no formato UnitRuntime
            runtimes.extend(remote_unit_runtimes)
            ctx = CombatContext(attacker_tile=None, defender_tile=dst_tile)
            if distance_fn is not None:
                report_v2 = self.combat_engine_v2.resolve_for_tile(
                    tile=dst_tile,
                    units=runtimes,
                    ctx=ctx,
                    distance_fn=distance_fn,
                )
            else:
                report_v2 = self.combat_engine_v2.resolve_tile_local(
                    tile=dst_tile,
                    units=[u for u in runtimes if u.tile == dst_tile],
                    ctx=ctx,
                )
            killed.extend(report_v2.killed_uids)
            if report_v2.duels:
                attacker_origins: list[dict] = []
                # entrantes (ordens de movimento)
                for order, civ_id in allowed_orders:
                    from_tile = stack_origin_tile.get(order.stack_uid)
                    if from_tile is None:
                        st = self.stacks.get_stack(order.stack_uid)
                        if st and (not st.is_empty()) and getattr(st, "tile", None) is not None:
                            t = st.tile
                            from_tile = (int(t[0]), int(t[1]))
                    attacker_origins.append(
                        {
                            "attacker_civ_id": int(civ_id),
                            "stack_uid": str(order.stack_uid),
                            "from_tile": from_tile,
                            "to_tile": dst_tile,
                        }
                    )
                # remotos (ordem explícita)
                attacker_origins.extend(remote_attackers_meta)
                tile_logs.append(
                    {
                        "system": "combat_v2",
                        "defender_tile": dst_tile,
                        "attacker_origins": attacker_origins,
                        "resident_civs_at_start": sorted(int(x) for x in resident_civs),
                        "duels": [
                            {
                                "attacker_uid": d.attacker_uid,
                                "defender_uid": d.defender_uid,
                                "attacker_killed": bool(d.attacker_killed),
                                "defender_killed": bool(d.defender_killed),
                                "debug": d.debug,
                            }
                            for d in report_v2.duels
                        ],
                        "killed_uids": list(report_v2.killed_uids),
                        "stopped_by_max_duels": bool(report_v2.stopped_by_max_duels),
                    }
                )
        # ✅ (C) “combate efetivo” = houve duelos
        had_effective_combat = bool(report_v2 and report_v2.duels)
        # ── Resultados por ordem (entrantes) ───────────────────────
        killed_set = set(killed)
        for order, civ_id in allowed_orders:
            if order.stack_uid in invalid_stack_uids:
                continue
            stack = self.stacks.get_stack(order.stack_uid)
            if stack is None or stack.is_empty():
                continue
            if not had_effective_combat:
                results.append(
                    MoveResult(
                        result_type=MoveResultType.MOVED,
                        reason="Entrada sem combate (nenhum duelo efetivo no tile/pool).",
                        stack_uid=order.stack_uid,
                        dst_tile=dst_tile,
                    )
                )
                moves.append((order.stack_uid, dst_tile))
                continue
            survived_any = any((u.uid not in killed_set) for u in stack.units)
            if not survived_any:
                results.append(
                    MoveResult(
                        result_type=MoveResultType.DEFEATED,
                        reason="Derrota na batalha do tile.",
                        stack_uid=order.stack_uid,
                        dst_tile=dst_tile,
                        battle_report=battle_report,
                    )
                )
            else:
                results.append(
                    MoveResult(
                        result_type=MoveResultType.MOVED_AFTER_VICTORY,
                        reason="Sobreviveu à batalha do tile.",
                        stack_uid=order.stack_uid,
                        dst_tile=dst_tile,
                        battle_report=battle_report,
                    )
                )
                moves.append((order.stack_uid, dst_tile))
        return results, moves, killed, tile_logs

    # ─── Validação ────────────────────────────────────────────────

    def _validate_order(self, order: MoveOrder) -> MoveResult | None:
        stack = self.stacks.get_stack(order.stack_uid)

        if stack is None:
            return MoveResult(
                result_type=MoveResultType.INVALID,
                reason=f"Stack '{order.stack_uid}' não existe.",
                stack_uid=order.stack_uid,
                dst_tile=order.dst_tile,
            )

        if stack.is_empty():
            return MoveResult(
                result_type=MoveResultType.INVALID,
                reason=f"Stack '{order.stack_uid}' está vazia.",
                stack_uid=order.stack_uid,
                dst_tile=order.dst_tile,
            )

        if stack.tile == order.dst_tile:
            return MoveResult(
                result_type=MoveResultType.INVALID,
                reason="Destino é o tile atual.",
                stack_uid=order.stack_uid,
                dst_tile=order.dst_tile,
            )

        return None

    # ─── Limpeza ──────────────────────────────────────────────────

    def _cleanup_all_empty_stacks(self) -> None:
        empty_uids = [uid for uid, stack in self.stacks.stacks_by_uid.items() if stack.is_empty()]
        for uid in empty_uids:
            self.stacks.delete_stack(uid)

    # ─── Helper ──────────────────────────────────────────────────

    def _blocked_civs_for_tile(self, resident_civs: set[int], arriving_civs: set[int]) -> set[int]:
        blocked: set[int] = set()
        all_civs = resident_civs | arriving_civs
        for x in arriving_civs:
            for cid in (all_civs - {x}):
                if self.diplomacy.relation(x, cid) == Relation.NEUTRAL:
                    blocked.add(x)
                    break
        return blocked
