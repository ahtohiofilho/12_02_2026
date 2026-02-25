# core/commands/manager.py
from __future__ import annotations

from typing import Optional

from core.commands.models import UnitCommand, CommandType, CommandStatus
from core.commands.validator import CommandValidator, ValidationResult
from core.stacks.repo import StackRepository
from core.turn_engine import TurnEngine

Tile = tuple[int, int]


class CommandManager:
    """
    Gerencia comandos pendentes (inclui ordens multi-turno).

    Ciclo:
        1. Jogador dá comandos (issue_move_command)
        2. Comandos ficam PENDING com path completo
        3. No fim do turno, flush_to_engine() calcula o avanço deste turno
           e submete apenas o próximo tile alcançável ao TurnEngine
        4. TurnEngine.resolve_turn() resolve (1 tile por vez)
        5. Pós-turno: advance_persistent_commands() atualiza remaining_path
           - Se chegou ao destino → remove comando
           - Se não → mantém como PENDING para o próximo turno

    Regra: 1 comando por stack (o último sobrescreve).
    """

    def __init__(
        self,
        graph,
        stacks: StackRepository,
        turn_engine: TurnEngine,
    ):
        self.graph = graph
        self.validator = CommandValidator(graph, stacks)
        self.stacks = stacks
        self.turn_engine = turn_engine

        # stack_uid -> UnitCommand (1 por stack)
        self._pending: dict[str, UnitCommand] = {}

    def issue_move_command(
        self,
        stack_uid: str,
        destination: Tile,
        owner_civ_id: int,
    ) -> tuple[bool, str, Optional[UnitCommand]]:
        """
        Tenta emitir um comando de movimento.
        O path completo é armazenado; o avanço por turno é calculado no flush.
        """
        result = self.validator.validate_move(stack_uid, destination)

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

        # Sobrescreve comando anterior da mesma stack (se houver)
        old = self._pending.get(stack_uid)
        if old:
            old.status = CommandStatus.CANCELLED

        self._pending[stack_uid] = cmd

        total_cost = result.cost if result.cost is not None else 0
        return True, f"Comando registrado (custo total: {total_cost:.0f} turnos)", cmd

    def cancel_command(self, stack_uid: str) -> bool:
        """Cancela o comando pendente de uma stack."""
        cmd = self._pending.pop(stack_uid, None)
        if cmd:
            cmd.status = CommandStatus.CANCELLED
            return True
        return False

    def get_command(self, stack_uid: str) -> Optional[UnitCommand]:
        """Retorna o comando pendente de uma stack (se houver)."""
        return self._pending.get(stack_uid)

    def all_pending(self) -> list[UnitCommand]:
        """Todos os comandos pendentes do turno."""
        return [c for c in self._pending.values() if c.status == CommandStatus.PENDING]

    def pending_count(self) -> int:
        return len(self.all_pending())

    def flush_to_engine(self) -> int:
        """
        Para cada comando PENDING, calcula o próximo tile alcançável
        neste turno (considerando budget acumulado) e submete ao TurnEngine.

        Returns:
            Número de ordens submetidas.
        """
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

            # Recalibrar remaining_path se a stack não está no início
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

            # Adicionar budget deste turno ao acumulado
            cmd.accumulated_budget += TURN_BUDGET

            # Quantos tiles do remaining_path a stack percorre com o budget acumulado
            advance_idx = tiles_reachable_this_turn(
                self.graph,
                rpath[0],
                rpath,
                unit_keys,
                allowed_biomes=allowed,
                budget=cmd.accumulated_budget,
            )

            if advance_idx == 0:
                # Ainda não tem budget suficiente para o próximo tile
                # Mantém PENDING, o budget acumulado já foi incrementado
                cmd.status = CommandStatus.PENDING
                continue

            # Calcular custo real do trecho percorrido e descontar do acumulado
            cost_spent = 0
            for i in range(1, advance_idx + 1):
                tile = rpath[i]
                biome = self.graph.nodes[tile].get("bioma", "Meadow") if tile in self.graph else "Meadow"
                c = get_stack_entry_cost(unit_keys, biome)
                cost_spent += (c if c else 0)

            cmd.accumulated_budget -= cost_spent
            if cmd.accumulated_budget < 0:
                cmd.accumulated_budget = 0

            # Submeter o tile destino deste turno ao TurnEngine
            step_target = rpath[advance_idx]
            self.turn_engine.submit_order(cmd.stack_uid, step_target)
            cmd.status = CommandStatus.SUBMITTED
            count += 1

        return count

    def advance_persistent_commands(self) -> None:
        """
        Chamado APÓS resolve_turn().
        Atualiza remaining_path dos comandos que ainda não chegaram ao destino.
        Remove comandos que completaram a jornada.
        """
        to_remove: list[str] = []

        for uid, cmd in self._pending.items():
            if cmd.status == CommandStatus.CANCELLED:
                to_remove.append(uid)
                continue

            stack = self.stacks.get_stack(uid)
            if not stack or stack.is_empty():
                to_remove.append(uid)
                continue

            rpath = cmd.remaining_path
            if not rpath:
                to_remove.append(uid)
                continue

            current_tile = stack.tile

            # Chegou ao destino final?
            if current_tile == cmd.destination:
                to_remove.append(uid)
                print(f"  ✅ Stack {uid[:8]}… chegou ao destino {cmd.destination}.")
                continue

            # Atualizar remaining_path para começar do tile atual
            if current_tile in rpath:
                idx = rpath.index(current_tile)
                cmd.remaining_path = rpath[idx:]
            else:
                # Stack foi parar em tile fora do path — recalcular
                from core.commands.pathfinding import (
                    find_path,
                    allowed_biomes_for_stack,
                )
                allowed = allowed_biomes_for_stack(self.graph, stack)
                unit_keys = [u.unit_key for u in stack.units]
                new_path = find_path(
                    self.graph,
                    current_tile,
                    cmd.destination,
                    allowed_biomes=allowed,
                    unit_keys=unit_keys,
                )
                if new_path:
                    cmd.remaining_path = new_path
                    cmd.path = new_path
                else:
                    to_remove.append(uid)
                    print(f"  ⚠️ Stack {uid[:8]}… sem caminho para {cmd.destination}. Comando removido.")
                    continue

            # Manter como PENDING para o próximo turno
            cmd.status = CommandStatus.PENDING

        for uid in to_remove:
            self._pending.pop(uid, None)

    def clear(self) -> None:
        """Limpa TODOS os comandos (usar apenas em reset total, NÃO entre turnos)."""
        self._pending.clear()
