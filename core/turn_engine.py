# core/turn_engine.py

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from core.combat.apply import killed_unit_uids, apply_kills
from core.combat.models import CombatContext
from core.combat.resolver import CombatResolver
from core.combat.modifiers import AdvantageModifier
from core.combat.tile_battle import TileBattleResolver, UnitRef, TileBattleReport
from core.diplomacy import DiplomacyMatrix
from core.rules.tile_entry import decide_entry, EntryOutcome
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

    Ciclo de um turno:
        1. submit_order()   — cada civ submete suas ordens (pode ser chamado N vezes)
        2. resolve_turn()   — processa TUDO de uma vez contra o estado do início do turno
        3. (internamente)   — agrupa conflitos, resolve combates, aplica baixas em batch

    Princípio-chave: nenhuma ordem altera o mundo até que TODAS sejam processadas.
    """

    def __init__(
        self,
        stacks: StackRepository,
        diplomacy: DiplomacyMatrix,
        *,
        duel_resolver: CombatResolver | None = None,
    ):
        self.stacks = stacks
        self.diplomacy = diplomacy
        self.turn_number = 0

        if duel_resolver is None:
            duel_resolver = CombatResolver(modifiers=[AdvantageModifier()])

        self.battle_resolver = TileBattleResolver(duel_resolver=duel_resolver)

        # Fila de ordens pendentes para o turno atual
        self._pending_orders: list[MoveOrder] = []

    # ─── Fase 1: Coleta de ordens ─────────────────────────────────

    def submit_order(self, stack_uid: str, dst_tile: tuple[int, int]) -> None:
        """
        Submete uma ordem de movimento. Não executa nada ainda.
        Pode ser chamada múltiplas vezes antes de resolve_turn().
        """
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
            2. Fotografar estado atual (quem está onde)
            3. Agrupar ordens por tile destino (detectar colisões)
            4. Resolver combates onde necessário
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
            result = self._validate_order(order)
            if result is not None:
                # Ordem inválida — registra e pula
                report.results.append(result)
                continue

            stack = self.stacks.get_stack(order.stack_uid)
            validated.append((order, stack.owner_id))

        # ── 2. Fotografar estado: quem está em cada tile AGORA ───
        #    (antes de qualquer modificação)
        tile_snapshot: dict[tuple[int, int], set[int]] = {}
        for tile, uids in self.stacks.stack_uids_by_tile.items():
            civs = set()
            for uid in uids:
                s = self.stacks.get_stack(uid)
                if s and not s.is_empty():
                    civs.add(s.owner_id)
            if civs:
                tile_snapshot[tile] = civs

        # ── 3. Agrupar ordens por tile destino ───────────────────
        orders_by_dst: dict[tuple[int, int], list[tuple[MoveOrder, int]]] = {}
        for order, civ_id in validated:
            orders_by_dst.setdefault(order.dst_tile, []).append((order, civ_id))

        # ── 4. Processar cada tile destino ───────────────────────
        #    Acumular ações a aplicar DEPOIS
        pending_moves: list[tuple[str, tuple[int, int]]] = []     # (stack_uid, dst_tile)
        all_killed_uids: list[str] = []

        for dst_tile, tile_orders in orders_by_dst.items():
            tile_results, tile_moves, tile_killed = self._resolve_tile(
                dst_tile, tile_orders, tile_snapshot
            )
            report.results.extend(tile_results)
            pending_moves.extend(tile_moves)
            all_killed_uids.extend(tile_killed)

            # Coletar battle reports
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
        dst_tile: tuple[int, int],
        tile_orders: list[tuple[MoveOrder, int]],
        tile_snapshot: dict[tuple[int, int], set[int]],
    ) -> tuple[list[MoveResult], list[tuple[str, tuple[int, int]]], list[str]]:
        """
        Resolve todas as ordens direcionadas a um mesmo tile.

        Retorna:
            - lista de MoveResult
            - lista de movimentos pendentes (stack_uid, dst)
            - lista de unit_uids mortos
        """
        results: list[MoveResult] = []
        moves: list[tuple[str, tuple[int, int]]] = []
        killed: list[str] = []

        # Civs que JÁ ESTAVAM no tile no início do turno (snapshot)
        resident_civs = tile_snapshot.get(dst_tile, set())

        # Civs que estão CHEGANDO neste tile
        arriving_civs: dict[int, list[MoveOrder]] = {}
        for order, civ_id in tile_orders:
            arriving_civs.setdefault(civ_id, []).append(order)

        all_involved_civs = resident_civs | set(arriving_civs.keys())

        # Para cada ordem, decidir individualmente
        for order, civ_id in tile_orders:
            # Quem está no tile? Residentes + outras civs chegando
            present_civ_ids = (resident_civs | set(arriving_civs.keys())) - {civ_id}

            decision = decide_entry(
                mover_civ_id=civ_id,
                present_civ_ids=present_civ_ids,
                diplomacy=self.diplomacy,
            )

            if decision.outcome == EntryOutcome.ALLOW_NO_COMBAT:
                moves.append((order.stack_uid, dst_tile))
                results.append(MoveResult(
                    result_type=MoveResultType.MOVED,
                    reason=decision.reason,
                    stack_uid=order.stack_uid,
                    dst_tile=dst_tile,
                ))

            elif decision.outcome == EntryOutcome.ALLOW_WITH_COMBAT:
                result, tile_killed = self._resolve_combat(
                    order, civ_id, dst_tile, resident_civs
                )
                results.append(result)
                killed.extend(tile_killed)

                # Se venceu, agenda movimento
                if result.result_type == MoveResultType.MOVED_AFTER_VICTORY:
                    moves.append((order.stack_uid, dst_tile))

            else:  # BLOCK
                results.append(MoveResult(
                    result_type=MoveResultType.BLOCKED,
                    reason=decision.reason,
                    stack_uid=order.stack_uid,
                    dst_tile=dst_tile,
                    debug={"present_relations": decision.present_relations},
                ))

        return results, moves, killed

    # ─── Combate ──────────────────────────────────────────────────

    def _resolve_combat(
        self,
        order: MoveOrder,
        attacker_civ_id: int,
        dst_tile: tuple[int, int],
        resident_civs: set[int],
    ) -> tuple[MoveResult, list[str]]:
        """
        Resolve um combate entre a stack atacante e os defensores no tile.

        Retorna:
            - MoveResult
            - Lista de unit_uids mortos (para aplicação em batch)
        """
        stack = self.stacks.get_stack(order.stack_uid)
        if stack is None or stack.is_empty():
            return MoveResult(
                result_type=MoveResultType.INVALID,
                reason="Stack atacante não existe ou está vazia.",
                stack_uid=order.stack_uid,
                dst_tile=dst_tile,
            ), []

        # Montar atacantes
        attackers = [
            UnitRef(unit_key=u.unit_key, uid=u.uid, meta={})
            for u in stack.units
        ]

        # Montar defensores (todas as stacks inimigas no tile)
        enemy_civs = {cid for cid in resident_civs if cid != attacker_civ_id}
        defenders: list[UnitRef] = []
        for def_stack in self.stacks.stacks_in_tile(dst_tile):
            if def_stack.owner_id in enemy_civs:
                for u in def_stack.units:
                    defenders.append(
                        UnitRef(unit_key=u.unit_key, uid=u.uid, meta={"stack_uid": def_stack.uid})
                    )

        if not defenders:
            return MoveResult(
                result_type=MoveResultType.MOVED,
                reason="Sem defensores reais no tile.",
                stack_uid=order.stack_uid,
                dst_tile=dst_tile,
            ), []

        # Resolver batalha
        ctx = CombatContext(attacker_tile=stack.tile, defender_tile=dst_tile)
        battle_report = self.battle_resolver.resolve(
            attackers=attackers,
            defenders=defenders,
            ctx=ctx,
        )

        # Coletar mortos (NÃO aplicar ainda — será feito em batch)
        killed = killed_unit_uids(battle_report)

        attacker_won = (
            len(battle_report.survivors_attackers) > 0
            and len(battle_report.survivors_defenders) == 0
        )

        if attacker_won:
            return MoveResult(
                result_type=MoveResultType.MOVED_AFTER_VICTORY,
                reason=(
                    f"Vitória! {len(battle_report.survivors_attackers)} unidade(s) sobrevivente(s)."
                ),
                stack_uid=order.stack_uid,
                dst_tile=dst_tile,
                battle_report=battle_report,
                debug={"killed_uids": killed},
            ), killed

        return MoveResult(
            result_type=MoveResultType.DEFEATED,
            reason=(
                f"Derrota. {len(battle_report.survivors_defenders)} defensor(es) sobrevivente(s)."
            ),
            stack_uid=order.stack_uid,
            dst_tile=dst_tile,
            battle_report=battle_report,
            debug={"killed_uids": killed},
        ), killed

    # ─── Validação ────────────────────────────────────────────────

    def _validate_order(self, order: MoveOrder) -> MoveResult | None:
        """
        Valida uma ordem. Retorna MoveResult se inválida, None se OK.
        """
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

        return None  # Ordem válida

    # ─── Limpeza ──────────────────────────────────────────────────

    def _cleanup_all_empty_stacks(self) -> None:
        """Remove TODAS as stacks vazias do repositório."""
        empty_uids = [
            uid for uid, stack in self.stacks.stacks_by_uid.items()
            if stack.is_empty()
        ]
        for uid in empty_uids:
            self.stacks.delete_stack(uid)
