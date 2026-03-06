# core/commands/manager.py
from __future__ import annotations

from typing import Optional

from config.gameplay import FOUND_PROVINCE_TURNS
from core.commands.models import UnitCommand, CommandType, CommandStatus
from core.commands.validator import CommandValidator
from core.stacks.repo import StackRepository
from core.turn_engine import TurnEngine

Tile = tuple[int, int]


class CommandManager:
    """
    Gerencia comandos pendentes (inclui ordens multi-turno).

    Consolidação (v2.1):
    - MOVE: mantém fluxo atual (remaining_path + accumulated_budget).
    - FOUND_PROVINCE: mantém fluxo atual (extra: worker_uid, target_tile, turns_left).
    - ATTACK_TILE (NOVO): ordem explícita de atacar um tile, sem “puxar pro pool”.
        * Não usa remaining_path.
        * O TurnEngine/CombatV2 usa essa ordem para incluir unidades remotas no pool
          SOMENTE quando o alvo (target_tile) é o tile resolvido.
        * Validação: separada do MOVE (normalmente permite mirar território inimigo).
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

    # ─────────────────────────────────────────────────────────────
    # Emissão de comandos
    # ─────────────────────────────────────────────────────────────
    def issue_move_command(
        self,
        stack_uid: str,
        destination: Tile,
        owner_civ_id: int,
        planet=None,
    ) -> tuple[bool, str, Optional[UnitCommand]]:
        """
        Emite um comando de movimento.

        Observação:
        - Usa validator.validate_move (pode bloquear por território).
        - Armazena path e inicializa remaining_path.
        """
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

    def issue_attack_tile_command(
        self,
        *,
        stack_uid: str,
        target_tile: Tile,
        owner_civ_id: int,
        planet=None,
        target_layer: str | None = None,
        evasion_mode: str | None = None,  # "EVASIVE"|"COMMITTED"
    ) -> tuple[bool, str, Optional[UnitCommand]]:
        """
        Emite uma ordem explícita ATTACK_TILE.

        Regras:
        - Não move a stack (sem path).
        - TurnEngine/CombatV2 decide elegibilidade por alcance (dist <= range).
        - Validação deve ser diferente de MOVE:
            * normalmente você quer permitir mirar tile inimigo/neutro
              mesmo quando MOVE é bloqueado (não atravessar fronteira).
        """
        active_planet = planet or self.planet

        # Se você ainda não implementou validate_attack_tile(), caímos para um mínimo defensivo.
        validate_fn = getattr(self.validator, "validate_attack_tile", None)
        if callable(validate_fn):
            result = validate_fn(
                stack_uid,
                target_tile,
                planet=active_planet,
                owner_civ_id=owner_civ_id,
                target_layer=target_layer,
            )
            if not result.valid:
                return False, result.reason, None

        stack = self.stacks.get_stack(stack_uid)
        if stack is None or stack.is_empty():
            return False, "Stack não existe ou está vazia.", None

        cmd = UnitCommand(
            command_type=CommandType.ATTACK_TILE,
            stack_uid=stack_uid,
            owner_civ_id=owner_civ_id,
            origin=stack.tile,
            destination=target_tile,  # compat/fallback (prefira extra["target_tile"])
            path=None,
            remaining_path=None,
            accumulated_budget=0,
            status=CommandStatus.PENDING,
            extra={
                "target_tile": (int(target_tile[0]), int(target_tile[1])),
                "target_layer": (str(target_layer) if target_layer is not None else None),
                "explicit_attack": True,
                "evasion_mode": (str(evasion_mode).upper() if evasion_mode else "COMMITTED"),
                "start_turn": int(getattr(self.turn_engine, "turn_number", 0) or 0),
            },
        )

        old = self._pending.get(stack_uid)
        if old:
            old.status = CommandStatus.CANCELLED
        self._pending[stack_uid] = cmd

        return True, f"Ataque ao tile {target_tile} agendado.", cmd

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

        from core.workforce.facade import ProvinceWorkforceFacade

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
                "start_turn": int(self.turn_engine.turn_number),
            },
        )

        old = self._pending.get(stack_uid)
        if old:
            old.status = CommandStatus.CANCELLED

        self._pending[stack_uid] = cmd
        return True, f"Fundação agendada ({FOUND_PROVINCE_TURNS} turnos).", cmd

    # ─────────────────────────────────────────────────────────────
    # Acesso/consulta
    # ─────────────────────────────────────────────────────────────
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

    # ─────────────────────────────────────────────────────────────
    # Submissão ao TurnEngine (execução de movimento)
    # ─────────────────────────────────────────────────────────────
    def flush_to_engine(self) -> int:
        """
        Envia ao TurnEngine apenas comandos que geram ordem de MOVIMENTO neste turno.

        Observação:
        - ATTACK_TILE não gera submit_order() (não move).
        - FOUND_PROVINCE também não gera submit_order() (é processado no advance_persistent_commands()).
        """
        from core.commands.pathfinding import (
            tiles_reachable_this_turn,
            allowed_biomes_for_stack,
            TURN_BUDGET,
        )
        from config.movement_costs import get_stack_entry_cost

        count = 0

        for cmd in self.all_pending():
            if cmd.command_type != CommandType.MOVE:
                # ATTACK_TILE / FOUND_PROVINCE: permanecem PENDING até o resolve/advance tratar
                continue

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
                t = rpath[i]
                biome = self.graph.nodes[t].get("bioma", "Meadow") if t in self.graph else "Meadow"
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

    # ─────────────────────────────────────────────────────────────
    # Persistência / avanço pós-turno
    # ─────────────────────────────────────────────────────────────
    def advance_persistent_commands(self) -> None:
        """
        Chamado APÓS resolve_turn().

        Regras:
        - CANCELLED: removido aqui (libera para ordens no turno seguinte).
        - INVALID/RESOLVED: removidos aqui.

        FOUND_PROVINCE:
          - não usa remaining_path
          - usa cmd.extra: worker_uid, target_tile, turns_left
          - se a stack sair do tile alvo, vira CANCELLED (e removida no próximo turno)

        MOVE:
          - se chegou ao destino, remove
          - se desviou do caminho, tenta recalcular path
        ATTACK_TILE:
          - por padrão, é "one-turn intent": remove no fim do turno (RESOLVED),
            a menos que você queira suportar ataque persistente (aí mude aqui).
        """
        to_remove: list[str] = []

        for uid, cmd in list(self._pending.items()):
            # (0) Cancelados: removemos agora
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

                if stack.tile != target_tile:
                    cmd.status = CommandStatus.CANCELLED
                    continue

                turns_left = int(cmd.extra.get("turns_left", 0))
                if turns_left <= 0:
                    turns_left = 1

                turns_left -= 1
                cmd.extra["turns_left"] = turns_left

                if turns_left > 0:
                    cmd.status = CommandStatus.PENDING
                    continue

                from core.workforce.facade import ProvinceWorkforceFacade

                ok = ProvinceWorkforceFacade.found_province(
                    unit_uid=str(worker_uid),
                    planet=self.planet,
                )

                cmd.status = CommandStatus.RESOLVED if ok else CommandStatus.INVALID
                to_remove.append(uid)
                continue

            # ============================================================
            # (B) ATTACK_TILE (one-turn intent)
            # ============================================================
            if cmd.command_type == CommandType.ATTACK_TILE:
                # Se você quiser "ataque contínuo até cancelar", troque isso por:
                #   cmd.status = CommandStatus.PENDING
                # e mantenha no _pending.
                cmd.status = CommandStatus.RESOLVED
                to_remove.append(uid)
                continue

            # ============================================================
            # (C) MOVE (seu código atual)
            # ============================================================
            if cmd.command_type == CommandType.MOVE:
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
                continue

            # desconhecido
            cmd.status = CommandStatus.INVALID
            to_remove.append(uid)

        for uid in to_remove:
            self._pending.pop(uid, None)

    def clear(self) -> None:
        self._pending.clear()
