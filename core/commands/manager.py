# core/commands/manager.py
from __future__ import annotations

from typing import Optional

from config.gameplay import FOUND_PROVINCE_TURNS
from core.commands.models import UnitCommand, CommandType, CommandStatus
from core.commands.validator import CommandValidator, ValidationResult
from core.stacks.repo import StackRepository
from core.turn_engine import TurnEngine

Tile = tuple[int, int]


class CommandManager:
    """
    Gerencia comandos pendentes (inclui ordens multi-turno).
    """

    def __init__(
        self,
        graph,
        stacks: StackRepository,
        turn_engine: TurnEngine,
        planet=None,
    ):
        self.graph = graph
        self.planet = planet
        self.validator = CommandValidator(graph, stacks)
        self.stacks = stacks
        self.turn_engine = turn_engine

        self._pending: dict[str, UnitCommand] = {}

    def issue_move_command(
        self,
        stack_uid: str,
        destination: Tile,
        owner_civ_id: int,
        planet=None,
    ) -> tuple[bool, str, Optional[UnitCommand]]:
        """
        Tenta emitir um comando de movimento.
        Agora aceita `planet` para filtrar rotas por território.
        """
        # Usa o planet passado como argumento, ou o armazenado
        active_planet = planet or self.planet

        result = self.validator.validate_move(
            stack_uid,
            destination,
            planet=active_planet,
            owner_civ_id=owner_civ_id,
        )

        if not result.valid:
            return False, result.reason, None

        stack = self.stacks.get_stack(stack_uid)

        cmd = UnitCommand(
            command_type=CommandType.MOVE,
            stack_uid=stack_uid,
            owner_civ_id=owner_civ_id,
            origin=stack.tile if stack else None,
            destination=destination,
            path=result.path,
            remaining_path=list(result.path) if result.path else None,
            accumulated_budget=0,
            status=CommandStatus.PENDING,
        )

        old = self._pending.get(stack_uid)
        if old:
            old.status = CommandStatus.CANCELLED

        self._pending[stack_uid] = cmd

        total_cost = result.cost if result.cost is not None else 0
        return True, f"Comando registrado (custo total: {total_cost:.0f} turnos)", cmd

    def cancel_command(self, stack_uid: str) -> bool:
        cmd = self._pending.get(stack_uid)
        if cmd:
            cmd.status = CommandStatus.CANCELLED
            return True
        return False

    def get_command(self, stack_uid: str) -> Optional[UnitCommand]:
        return self._pending.get(stack_uid)

    def all_pending(self) -> list[UnitCommand]:
        return [c for c in self._pending.values() if c.status == CommandStatus.PENDING]

    def pending_count(self) -> int:
        return len(self.all_pending())

    def flush_to_engine(self) -> int:
        from core.commands.pathfinding import (
            tiles_reachable_this_turn,
            allowed_biomes_for_stack,
            TURN_BUDGET,
        )
        from config.movement_costs import get_stack_entry_cost

        count = 0

        for cmd in self.all_pending():
            stack = self.stacks.get_stack(cmd.stack_uid)
            if not stack or stack.is_empty():
                cmd.status = CommandStatus.INVALID
                continue

            rpath = cmd.remaining_path
            if not rpath or len(rpath) < 2:
                cmd.status = CommandStatus.INVALID
                continue

            if rpath[0] != stack.tile:
                try:
                    idx = rpath.index(stack.tile)
                    rpath = rpath[idx:]
                    cmd.remaining_path = rpath
                except ValueError:
                    cmd.status = CommandStatus.INVALID
                    continue

            if len(rpath) < 2:
                cmd.status = CommandStatus.INVALID
                continue

            unit_keys = [u.unit_key for u in stack.units]
            allowed = allowed_biomes_for_stack(self.graph, stack)

            cmd.accumulated_budget += TURN_BUDGET

            advance_idx = tiles_reachable_this_turn(
                self.graph,
                rpath[0],
                rpath,
                unit_keys,
                allowed_biomes=allowed,
                budget=cmd.accumulated_budget,
            )

            if advance_idx == 0:
                cmd.status = CommandStatus.PENDING
                continue

            cost_spent = 0
            for i in range(1, advance_idx + 1):
                tile = rpath[i]
                biome = self.graph.nodes[tile].get("bioma", "Meadow") if tile in self.graph else "Meadow"
                c = get_stack_entry_cost(unit_keys, biome)
                cost_spent += (c if c else 0)

            cmd.accumulated_budget -= cost_spent
            if cmd.accumulated_budget < 0:
                cmd.accumulated_budget = 0

            step_target = rpath[advance_idx]
            self.turn_engine.submit_order(cmd.stack_uid, step_target)
            cmd.status = CommandStatus.SUBMITTED
            count += 1

        return count

    def advance_persistent_commands(self) -> None:
        """
        Chamado APÓS resolve_turn().

        Regra de cancelamento (conforme combinado):
          - Se o jogador cancelar, o comando fica marcado como CANCELLED
            e SÓ é removido aqui (no avanço do turno), liberando a stack no turno seguinte.

        FOUND_PROVINCE:
          - não usa remaining_path
          - usa cmd.extra: worker_uid, target_tile, turns_left
          - se a stack sair do tile alvo, o comando é CANCELLED (e removido no próximo turno)
        """
        from core.commands.models import CommandType, CommandStatus

        to_remove: list[str] = []

        for uid, cmd in list(self._pending.items()):
            # 1) Cancelados: removemos agora (libera para ordens no próximo turno)
            if cmd.status == CommandStatus.CANCELLED:
                to_remove.append(uid)
                continue

            stack = self.stacks.get_stack(uid)
            if not stack or stack.is_empty():
                to_remove.append(uid)
                continue

            # ============================================================
            # (A) FOUND_PROVINCE
            # ============================================================
            if cmd.command_type == CommandType.FOUND_PROVINCE:
                worker_uid = cmd.extra.get("worker_uid")
                target_tile = cmd.extra.get("target_tile")

                if not worker_uid or not target_tile:
                    cmd.status = CommandStatus.INVALID
                    to_remove.append(uid)
                    continue

                target_tile = tuple(target_tile)

                # Saiu do tile alvo -> cancela, mas NÃO remove agora.
                # Ele será removido no próximo turno pelo bloco CANCELLED acima.
                if stack.tile != target_tile:
                    cmd.status = CommandStatus.CANCELLED
                    continue

                turns_left = int(cmd.extra.get("turns_left", 0))
                if turns_left <= 0:
                    turns_left = 1  # fallback defensivo p/ não "concluir instantâneo" por bug de estado

                turns_left -= 1
                cmd.extra["turns_left"] = turns_left

                if turns_left > 0:
                    cmd.status = CommandStatus.PENDING
                    continue

                # Concluiu: executa
                from core.workforce.facade import ProvinceWorkforceFacade

                ok = ProvinceWorkforceFacade.found_province(
                    unit_uid=str(worker_uid),
                    planet=self.planet,
                )

                cmd.status = CommandStatus.RESOLVED if ok else CommandStatus.INVALID
                to_remove.append(uid)
                continue

            # ============================================================
            # (B) MOVE (seu código atual)
            # ============================================================
            rpath = cmd.remaining_path
            if not rpath:
                to_remove.append(uid)
                continue

            current_tile = stack.tile

            if current_tile == cmd.destination:
                to_remove.append(uid)
                print(f"  ✅ Stack {uid[:8]}… chegou ao destino {cmd.destination}.")
                continue

            if current_tile in rpath:
                idx = rpath.index(current_tile)
                cmd.remaining_path = rpath[idx:]
            else:
                from core.commands.pathfinding import find_path, allowed_biomes_for_stack

                allowed = allowed_biomes_for_stack(self.graph, stack)
                unit_keys = [u.unit_key for u in stack.units]

                new_path = find_path(
                    self.graph,
                    current_tile,
                    cmd.destination,
                    allowed_biomes=allowed,
                    unit_keys=unit_keys,
                    planet=self.planet,
                    owner_id=cmd.owner_civ_id,
                )
                if new_path:
                    cmd.remaining_path = new_path
                    cmd.path = new_path
                else:
                    to_remove.append(uid)
                    print(f"  ⚠️ Stack {uid[:8]}… sem caminho para {cmd.destination}. Comando removido.")
                    continue

            cmd.status = CommandStatus.PENDING

        for uid in to_remove:
            self._pending.pop(uid, None)

    def issue_found_province_command(
        self,
        *,
        stack_uid: str,
        owner_civ_id: int,
        planet,
    ) -> tuple[bool, str, UnitCommand | None]:
        stack = self.stacks.get_stack(stack_uid)
        if stack is None or stack.is_empty():
            return False, "Stack não existe ou está vazia.", None

        # valida: stack tem worker? tile colonizável? tile sem província?
        # Reaproveita sua regra existente:
        from core.workforce.facade import ProvinceWorkforceFacade

        # aqui você precisa do unit_uid do worker (found_province usa unit_uid)
        worker_unit = next((u for u in stack.units if u.unit_key == "worker"), None)
        if worker_unit is None:
            return False, "É necessário um worker para fundar província.", None

        ok, reason = ProvinceWorkforceFacade.can_found_province(worker_unit.uid, planet)
        if not ok:
            return False, reason, None

        cmd = UnitCommand(
            command_type=CommandType.FOUND_PROVINCE,
            stack_uid=stack_uid,
            owner_civ_id=owner_civ_id,
            origin=stack.tile,
            destination=stack.tile,  # fundação é “no lugar”
            path=None,
            remaining_path=None,
            accumulated_budget=0,
            status=CommandStatus.PENDING,
            extra={
                "worker_uid": worker_unit.uid,
                "turns_total": int(FOUND_PROVINCE_TURNS),
                "turns_left": int(FOUND_PROVINCE_TURNS),
                "target_tile": stack.tile,
            },
        )

        # um stack só pode ter 1 comando ativo (mesma regra do MOVE)
        old = self._pending.get(stack_uid)
        if old:
            old.status = CommandStatus.CANCELLED

        self._pending[stack_uid] = cmd
        return True, f"Fundação agendada ({FOUND_PROVINCE_TURNS} turnos).", cmd

    def clear(self) -> None:
        self._pending.clear()
