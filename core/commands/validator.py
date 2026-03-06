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
    Valida comandos **antes** de submetê-los ao TurnEngine e retorna feedback imediato ao jogador.

    Escopo:
    - Esta classe valida a *intenção* do comando (MOVE / ATTACK_TILE) e evita ordens inviáveis
      (stack inválida, tile inexistente, bioma incompatível etc.).
    - Ela **não** executa movimento por turno e **não** resolve combate.

    Regras atuais (4X clássico + combate v2.1):
    - MOVE:
        * A stack deve existir e não estar vazia.
        * O tile de destino deve existir no grafo.
        * O bioma do destino deve ser acessível para a stack (domínio/biomas permitidos).
        * Restrições diplomáticas no destino (se `planet` for fornecido):
            - entrar em território **NEUTRAL** é bloqueado;
            - entrar em território **ALLY** é permitido;
            - entrar em território **ENEMY** é permitido (o combate será resolvido pelo TurnEngine ao entrar).
        * Deve existir um caminho válido (pathfinding sem limite de custo, pois o comando pode ser multi-turno).

    - ATTACK_TILE:
        * Validação separada do MOVE.
        * Não exige path (não move a stack).
        * Pode exigir que exista alvo inimigo no tile (província ou stack), dependendo da configuração.
        * Alcance (distância <= range) é verificado na fase
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
        # 4X clássico: bloqueia NEUTRAL, permite ENEMY (combate acontece no TurnEngine)
        effective_owner = int(owner_civ_id) if owner_civ_id is not None else int(stack.owner_id)
        if planet is not None:
            from core.diplomacy import Relation
            destination = (int(destination[0]), int(destination[1]))
            dest_province = planet.provinces_by_tile.get(destination)
            if dest_province and dest_province.owner is not None:
                dest_owner_id = int(dest_province.owner.id)
                if dest_owner_id != effective_owner:
                    rel = planet.diplomacy.relation(effective_owner, dest_owner_id)
                    # ✅ Regra 4X: não entra em território NEUTRAL
                    if rel == Relation.NEUTRAL:
                        return ValidationResult(
                            False,
                            "Destino pertence a uma civilização neutral.",
                        )
                    # ✅ ALLY: permitido
                    # ✅ ENEMY: permitido (o combate resolve ao entrar)
                    # (Se existir outro estado no futuro, trate aqui.)

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

    def validate_attack_tile(
        self,
        stack_uid: str,
        target_tile: Tile,
        *,
        planet=None,
        owner_civ_id: int | None = None,
        target_layer: str | None = None,
    ) -> ValidationResult:
        stack = self.stacks.get_stack(stack_uid)
        if stack is None:
            return ValidationResult(False, "Stack não existe.")
        if stack.is_empty():
            return ValidationResult(False, "Stack está vazia.")

        target_tile = (int(target_tile[0]), int(target_tile[1]))

        if not self.graph.has_node(target_tile):
            return ValidationResult(False, "Tile alvo não existe no mapa.")

        if stack.tile == target_tile:
            return ValidationResult(False, "Tile alvo é o tile atual (use combate local/movimento).")

        effective_owner = owner_civ_id if owner_civ_id is not None else stack.owner_id

        # (opcional) exige que exista inimigo no tile alvo (província ou stack)
        if planet is not None and effective_owner is not None:
            from core.diplomacy import Relation

            enemy_present = False

            prov = planet.provinces_by_tile.get(target_tile)
            if prov and prov.owner is not None:
                if planet.diplomacy.relation(int(effective_owner), int(prov.owner.id)) == Relation.ENEMY:
                    enemy_present = True

            if not enemy_present:
                for s in planet.stacks.stacks_in_tile(target_tile):
                    if s.is_empty():
                        continue
                    if planet.diplomacy.relation(int(effective_owner), int(s.owner_id)) == Relation.ENEMY:
                        enemy_present = True
                        break

            if not enemy_present:
                return ValidationResult(False, "Não há inimigo no tile alvo.")

        # alcance será validado no TurnEngine/CombatV2, então aqui é OK.
        # Retorna valid=True sem path.
        return ValidationResult(True, "OK", path=None, cost=0.0)
