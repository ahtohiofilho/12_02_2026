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

    Garante que:
      - A stack existe e não está vazia
      - O destino existe e é acessível (bioma compatível)
      - Existe um caminho válido até o destino (sem limite de custo)
      - O caminho não passa por territórios inimigos ou neutros

    O controle de avanço por turno é responsabilidade do CommandManager.flush_to_engine().
    """

    def __init__(self, graph, stacks: StackRepository):
        self.graph = graph
        self.stacks = stacks

    def validate_move(
        self,
        stack_uid: str,
        destination: Tile,
        *,
        planet=None,
        owner_civ_id: int | None = None,
    ) -> ValidationResult:
        """
        Valida um comando de movimento/ataque.

        Args:
            stack_uid:    UID da stack
            destination:  tile destino
            planet:       instância do Planet (para filtro de território)
            owner_civ_id: id da civ dona da stack (para filtro de território)
        """
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

        # ── Verificar se destino é território bloqueado ──
        effective_owner = owner_civ_id if owner_civ_id is not None else stack.owner_id
        if planet is not None and effective_owner is not None:
            from core.diplomacy import Relation

            dest_province = planet.provinces_by_tile.get(destination)
            if dest_province and dest_province.owner is not None:
                dest_owner_id = dest_province.owner.id
                if dest_owner_id != effective_owner:
                    rel = planet.diplomacy.relation(effective_owner, dest_owner_id)
                    if rel != Relation.ALLY:
                        rel_name = rel.name.lower()
                        return ValidationResult(
                            False,
                            f"Destino pertence a uma civilização {rel_name}.",
                        )

        # Unit keys da stack (para custos variáveis)
        unit_keys = [u.unit_key for u in stack.units]

        # Pathfinding SEM limite de custo (comando multi-turno)
        # ✅ Passa planet e owner_id para filtrar territórios inimigos/neutros
        path = find_path(
            self.graph,
            origin=stack.tile,
            destination=destination,
            movement_points=None,
            allowed_biomes=biomes,
            unit_keys=unit_keys,
            planet=planet,
            owner_id=effective_owner,
        )

        if path is None:
            return ValidationResult(
                False,
                "Sem caminho válido até o destino (bloqueado por território hostil ou bioma).",
            )

        # Calcular custo total (informativo)
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
