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
    Gerencia comandos pendentes do turno atual.

    Ciclo:
        1. Jogador dá comandos (issue_move_command)
        2. Comandos ficam PENDING (visíveis na UI com path overlay)
        3. No fim do turno, flush_to_engine() submete tudo ao TurnEngine
        4. TurnEngine.resolve_turn() resolve
        5. clear() limpa para o próximo turno

    Regra: 1 comando por stack por turno (o último sobrescreve).
    """

    def __init__(
            self,
            graph,
            stacks: StackRepository,
            turn_engine: TurnEngine,
    ):
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

        Returns:
            (sucesso, mensagem, comando_criado_ou_None)
        """
        # Validar
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
            status=CommandStatus.PENDING,
        )

        # Sobrescreve comando anterior da mesma stack (se houver)
        old = self._pending.get(stack_uid)
        if old:
            old.status = CommandStatus.CANCELLED

        self._pending[stack_uid] = cmd

        return True, f"Comando registrado (custo: {result.cost:.1f})", cmd

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
        Submete todos os comandos PENDING ao TurnEngine.
        Chamado logo antes de resolve_turn().

        Returns:
            Número de ordens submetidas.
        """
        count = 0
        for cmd in self.all_pending():
            if cmd.destination is None:
                cmd.status = CommandStatus.INVALID
                continue

            self.turn_engine.submit_order(cmd.stack_uid, cmd.destination)
            cmd.status = CommandStatus.SUBMITTED
            count += 1

        return count

    def clear(self) -> None:
        """Limpa todos os comandos (pós-turno)."""
        self._pending.clear()
