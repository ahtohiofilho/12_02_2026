# core/commands/validator.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.commands.pathfinding import (
    find_path,
    allowed_biomes_for_stack,
)
from config.movement_costs import get_stack_entry_cost
from core.stacks.repo import StackRepository

Tile = tuple[int, int]


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    reason: str
    path: Optional[list[Tile]] = None
    cost: float = 0.0


class CommandValidator:
    """
    Valida comandos ANTES de submetê-los ao TurnEngine.
    Dá feedback imediato ao jogador.

    NOTA: Não limita por budget de 1 turno. O comando pode ser multi-turno.
    A validação aqui garante apenas que:
      - A stack existe e não está vazia
      - O destino existe e é acessível (bioma compatível)
      - Existe um caminho válido até o destino (sem limite de custo)

    O controle de avanço por turno é responsabilidade do CommandManager.flush_to_engine().
    """

    def __init__(self, graph, stacks: StackRepository):
        self.graph = graph
        self.stacks = stacks

    def validate_move(
        self,
        stack_uid: str,
        destination: Tile,
    ) -> ValidationResult:
        """Valida um comando de movimento/ataque."""

        stack = self.stacks.get_stack(stack_uid)
        if stack is None:
            return ValidationResult(False, "Stack não existe.")

        if stack.is_empty():
            return ValidationResult(False, "Stack está vazia.")

        if stack.tile == destination:
            return ValidationResult(False, "Destino é o tile atual.")

        if not self.graph.has_node(destination):
            return ValidationResult(False, "Tile destino não existe no mapa.")

        # Biomas permitidos para esta stack
        biomes = allowed_biomes_for_stack(self.graph, stack, self.stacks)
        if not biomes:
            return ValidationResult(False, "Stack não tem biomas válidos (erro de config).")

        # Verificar bioma do destino
        dest_biome = self.graph.nodes.get(destination, {}).get("bioma", "")
        if dest_biome not in biomes:
            return ValidationResult(
                False,
                f"Bioma '{dest_biome}' não é acessível para esta stack.",
            )

        # Unit keys da stack (para custos variáveis)
        unit_keys = [u.unit_key for u in stack.units]

        # Pathfinding SEM limite de custo (comando multi-turno)
        path = find_path(
            self.graph,
            origin=stack.tile,
            destination=destination,
            movement_points=None,
            allowed_biomes=biomes,
            unit_keys=unit_keys,
        )

        if path is None:
            return ValidationResult(
                False,
                "Sem caminho válido até o destino.",
            )

        # Calcular custo total (informativo — quantos "turnos-custo" a jornada leva)
        total_cost = 0.0
        for tile in path[1:]:
            biome = self.graph.nodes[tile].get("bioma", "Meadow")
            entry = get_stack_entry_cost(unit_keys, biome)
            total_cost += entry if entry is not None else 1.0

        return ValidationResult(
            valid=True,
            reason="OK",
            path=path,
            cost=total_cost,
        )
