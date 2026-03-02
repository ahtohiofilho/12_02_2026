# core/turn_engine.py

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable

from core.combat.apply import killed_unit_uids, apply_kills
from core.combat.models import CombatContext
from core.combat.modifiers import AdvantageModifier
from core.combat.resolver import CombatResolver
from core.combat.tile_battle import TileBattleResolver, TileBattleReport, UnitRef
from core.diplomacy import DiplomacyMatrix, Relation
from core.stacks.repo import StackRepository


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

    @property
    def total_orders(self) -> int:
        return len(self.results)

    @property
    def total_battles(self) -> int:
        return len(self.battles)

    def results_for_civ(self, civ_id: int, stacks: StackRepository) -> list[MoveResult]:
        """Filtra resultados pertencentes a uma civilização."""
        civ_stack_uids = stacks.stack_uids_by_owner.get(civ_id, set())
        return [r for r in self.results if r.stack_uid in civ_stack_uids]


# ─── Engine ───────────────────────────────────────────────────────────

class TurnEngine:
    """
    Motor de turnos com resolução simultânea.

    Princípio-chave: nenhuma ordem altera o mundo até que TODAS sejam processadas.
    """

    def __init__(
        self,
        stacks: StackRepository,
        diplomacy: DiplomacyMatrix,
        *,
        biome_at: Callable[[tuple[int, int]], str] | None = None,
        duel_resolver: CombatResolver | None = None,
    ):
        self.stacks = stacks
        self.diplomacy = diplomacy
        self.turn_number = 0

        # Fail-fast: bioma é necessário para regras de domínio (LAND/NAVAL).
        if biome_at is None:
            raise ValueError(
                "TurnEngine requer biome_at(tile)->str (ex.: lambda t: planet.graph.nodes[t]['bioma'])."
            )
        self.biome_at = biome_at

        if duel_resolver is None:
            duel_resolver = CombatResolver(modifiers=[AdvantageModifier()])

        # Importante: aqui assume-se que você trocou o TileBattleResolver para a versão unificada
        # (mesmo nome de classe), com assinatura resolve(units=..., ctx=...).
        self.battle_resolver = TileBattleResolver(
            duel_resolver=duel_resolver,
            diplomacy=self.diplomacy,
        )

        # Fila de ordens pendentes para o turno atual
        self._pending_orders: list[MoveOrder] = []

    # ─── Fase 1: Coleta de ordens ─────────────────────────────────

    def submit_order(self, stack_uid: str, dst_tile: tuple[int, int]) -> None:
        """Submete uma ordem de movimento. Não executa nada ainda."""
        self._pending_orders.append(MoveOrder(stack_uid=stack_uid, dst_tile=dst_tile))

    def clear_orders(self) -> None:
        """Limpa todas as ordens pendentes (ex.: cancelamento)."""
        self._pending_orders.clear()

    @property
    def pending_count(self) -> int:
        return len(self._pending_orders)

    # ─── Fase 2: Resolução simultânea ─────────────────────────────

    def resolve_turn(self) -> TurnReport:
        """
        Processa TODAS as ordens pendentes simultaneamente.

        Etapas internas:
            1. Validar ordens
            2. Fotografar estado atual (snapshot de unidades residentes por tile)
            3. Agrupar ordens por tile destino
            4. Resolver por tile (BLOCK por civ + pool + batalha unificada)
            5. Aplicar baixas em batch
            6. Aplicar movimentos em batch
            7. Limpar stacks vazias
        """
        self.turn_number += 1
        report = TurnReport(turn_number=self.turn_number)

        orders = list(self._pending_orders)
        self._pending_orders.clear()

        if not orders:
            return report

        # ── 1. Validar e classificar cada ordem ──────────────────
        validated: list[tuple[MoveOrder, int]] = []  # (order, owner_civ_id)
        for order in orders:
            invalid = self._validate_order(order)
            if invalid is not None:
                report.results.append(invalid)
                continue

            stack = self.stacks.get_stack(order.stack_uid)
            assert stack is not None
            validated.append((order, stack.owner_id))

        # ── 2. Snapshot: unidades residentes por tile ────────────
        tile_units_snapshot: dict[tuple[int, int], list[UnitRef]] = {}

        for tile, stack_uids in self.stacks.stack_uids_by_tile.items():
            units: list[UnitRef] = []
            for stack_uid in stack_uids:
                s = self.stacks.get_stack(stack_uid)
                if not s or s.is_empty():
                    continue
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

        # ── 3. Agrupar ordens por tile destino ───────────────────
        orders_by_dst: dict[tuple[int, int], list[tuple[MoveOrder, int]]] = {}
        for order, civ_id in validated:
            orders_by_dst.setdefault(order.dst_tile, []).append((order, civ_id))

        # ── 4. Processar cada tile destino ───────────────────────
        pending_moves: list[tuple[str, tuple[int, int]]] = []
        all_killed_uids: list[str] = []

        for dst_tile, tile_orders in orders_by_dst.items():
            tile_results, tile_moves, tile_killed = self._resolve_tile(
                dst_tile=dst_tile,
                tile_orders=tile_orders,
                tile_units_snapshot=tile_units_snapshot,
            )

            report.results.extend(tile_results)
            pending_moves.extend(tile_moves)
            all_killed_uids.extend(tile_killed)

            for r in tile_results:
                if r.battle_report is not None:
                    report.battles.append(r.battle_report)

        # ── 5. Aplicar TODAS as baixas de uma vez ────────────────
        apply_kills(self.stacks, all_killed_uids)

        # ── 6. Aplicar TODOS os movimentos de uma vez ────────────
        for stack_uid, dst_tile in pending_moves:
            stack = self.stacks.get_stack(stack_uid)
            if stack and not stack.is_empty():
                self.stacks.move_stack_position_only(stack_uid, dst_tile)

        # ── 7. Limpeza global de stacks vazias ───────────────────
        self._cleanup_all_empty_stacks()

        return report

    # ─── Resolução por tile ───────────────────────────────────────

    def _resolve_tile(
        self,
        *,
        dst_tile: tuple[int, int],
        tile_orders: list[tuple[MoveOrder, int]],
        tile_units_snapshot: dict[tuple[int, int], list[UnitRef]],
    ) -> tuple[list[MoveResult], list[tuple[str, tuple[int, int]]], list[str]]:
        results: list[MoveResult] = []
        moves: list[tuple[str, tuple[int, int]]] = []
        killed: list[str] = []

        # Residentes (snapshot do início do turno)
        resident_units = list(tile_units_snapshot.get(dst_tile, []))
        resident_civs = {u.owner_id for u in resident_units}

        # Entrantes (por civ)
        arriving_civs: dict[int, list[MoveOrder]] = {}
        for order, civ_id in tile_orders:
            arriving_civs.setdefault(civ_id, []).append(order)
        arriving_ids = set(arriving_civs.keys())

        # ── v2.6: BLOCK por civ (NEUTRAL presente) ───────────────
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

        allowed_orders = [(o, c) for (o, c) in tile_orders if c not in blocked_civs]
        if not allowed_orders:
            return results, moves, killed

        # ── Build entrant units (das stacks) ─────────────────────
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
                        owner_id=civ_id,
                        meta={"stack_uid": stack.uid, "resident": False},
                    )
                )

        # ── Pool por domínio (T) conforme bioma ───────────────────
        biome = self.biome_at(dst_tile)
        aquatic = biome in {"Coast", "Sea", "Ocean"}

        def domain_ok(u: UnitRef) -> bool:
            # Usa suas categorias; AIR fica de fora da fase T.
            from config.unit_stats import UnitCategory, get_unit_stats

            st = get_unit_stats(u.unit_key)
            if not st:
                return True  # fallback: não bloqueia unidade desconhecida
            if st.category == UnitCategory.AIR:
                return False
            if aquatic:
                sub = getattr(UnitCategory, "SUB", None)
                if sub is not None:
                    return st.category in (UnitCategory.NAVAL, sub)
                return st.category == UnitCategory.NAVAL
            return st.category == UnitCategory.LAND

        pool = [u for u in (resident_units + entrant_units) if domain_ok(u)]

        # ── Decide se existe conflito ENEMY no pool ───────────────
        civs_in_pool = {u.owner_id for u in pool}
        civ_list = list(civs_in_pool)
        has_enemy = False
        for i in range(len(civ_list)):
            for j in range(i + 1, len(civ_list)):
                if self.diplomacy.relation(civ_list[i], civ_list[j]) == Relation.ENEMY:
                    has_enemy = True
                    break
            if has_enemy:
                break

        battle_report: TileBattleReport | None = None
        if has_enemy and pool:
            # Nota: CombatContext pode aceitar None dependendo do seu dataclass; se não aceitar,
            # ajuste para stack.tile de alguma unidade, ou só passe defender_tile=dst_tile.
            ctx = CombatContext(attacker_tile=None, defender_tile=dst_tile)
            battle_report = self.battle_resolver.resolve(units=pool, ctx=ctx)
            killed.extend(killed_unit_uids(battle_report))

        # ── Resultados por ordem/stack entrante ───────────────────
        survivors_uids = {u.uid for u in battle_report.survivors_units} if battle_report else set()

        for order, civ_id in allowed_orders:
            if order.stack_uid in invalid_stack_uids:
                continue

            stack = self.stacks.get_stack(order.stack_uid)
            if stack is None or stack.is_empty():
                continue

            if battle_report is None:
                results.append(
                    MoveResult(
                        result_type=MoveResultType.MOVED,
                        reason="Entrada sem combate (nenhum ENEMY elegível no tile/pool).",
                        stack_uid=order.stack_uid,
                        dst_tile=dst_tile,
                    )
                )
                moves.append((order.stack_uid, dst_tile))
                continue

            survived = any((u.uid in survivors_uids) for u in stack.units)
            if not survived:
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

        return results, moves, killed

    # ─── Validação ────────────────────────────────────────────────

    def _validate_order(self, order: MoveOrder) -> MoveResult | None:
        """Valida uma ordem. Retorna MoveResult se inválida, None se OK."""
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
        """Remove TODAS as stacks vazias do repositório."""
        empty_uids = [
            uid for uid, stack in self.stacks.stacks_by_uid.items()
            if stack.is_empty()
        ]
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
