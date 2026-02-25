# core/commands/validator.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.commands.pathfinding import (
    find_path,
    allowed_biomes_for_stack,
    movement_budget_for_stack,
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
    Dá feedback imediato ao jogador (não precisa esperar o turno resolver).
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

        # Budget baseado no domínio
        budget = movement_budget_for_stack(stack)
        if budget <= 0:
            return ValidationResult(False, "Stack não tem pontos de movimento.")

        # Pathfinding com custos variáveis por unidade×bioma
        path = find_path(
            self.graph,
            origin=stack.tile,
            destination=destination,
            movement_points=budget,
            allowed_biomes=biomes,
            unit_keys=unit_keys,
        )

        if path is None:
            # Tentar sem budget para distinguir "fora de alcance" de "impossível"
            path_unlimited = find_path(
                self.graph,
                origin=stack.tile,
                destination=destination,
                movement_points=None,
                allowed_biomes=biomes,
                unit_keys=unit_keys,
            )

            if path_unlimited is None:
                return ValidationResult(
                    False,
                    "Sem caminho válido até o destino.",
                )
            else:
                return ValidationResult(
                    False,
                    f"Destino fora de alcance neste turno (budget={budget}).",
                )

        # Calcular custo real usando os custos por unidade×bioma
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
