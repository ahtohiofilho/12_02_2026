# core/workforce/facade.py
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from config.unit_stats import get_unit_stats
from config.gameplay import MIN_WORKERS_FIXOS
from core.production.queue import QueueItem, QueueItemType
from core.economy.production import calculate_production, worker_cost

if TYPE_CHECKING:
    from core.planet import Planet
    from core.civilization import Province

Tile = tuple[int, int]


@dataclass(frozen=True, slots=True)
class WorkerInfo:
    current: int
    workers_food: int
    workers_ore: int
    next_cost: float


class ProvinceWorkforceFacade:
    """
    Facade que conecta a UI de workforce aos repositórios do core.

    Responsabilidades:
      - enfileirar itens de produção
      - cancelar/remover itens com refund (50% do pago)
      - destacar worker fixo → unidade móvel no mapa
      - reintegrar worker móvel → worker fixo em qualquer província
      - fundar nova província via worker móvel
    """

    def __init__(self, *, planet: "Planet", province: "Province"):
        self.planet = planet
        self.province = province
        self.tile: Tile = province.tile_coords

    # ------------------------------------------------------------------ #
    #  Info                                                                #
    # ------------------------------------------------------------------ #

    def worker_info(self) -> WorkerInfo:
        econ = self.planet.econ_repo.get(self.tile)
        if not econ:
            return WorkerInfo(current=0, workers_food=0, workers_ore=0, next_cost=worker_cost(0))

        current = int(econ.workers)
        civ = self.province.owner
        cost = worker_cost(civ.workers_purchased) if civ else worker_cost(0)

        return WorkerInfo(
            current=current,
            workers_food=int(econ.workers_food_int),
            workers_ore=int(econ.workers_ore_int),
            next_cost=float(cost),
        )

    def resource_names(self) -> tuple[str, str]:
        econ = self.planet.econ_repo.get(self.tile)
        food_name = econ.food_type if econ and econ.food_type else "Food"
        ore_name  = econ.ore_type  if econ and econ.ore_type  else "Ore"
        return str(food_name), str(ore_name)

    def outputs(self) -> tuple[float, float]:
        econ = self.planet.econ_repo.get(self.tile)
        if not econ:
            return 0.0, 0.0
        return float(econ.food_output or 0.0), float(econ.ore_output or 0.0)

    def productivities(self) -> tuple[float, float]:
        econ = self.planet.econ_repo.get(self.tile)
        if not econ:
            return 0.0, 0.0
        return float(econ.food_productivity or 0.0), float(econ.ore_productivity or 0.0)

    def treasury(self) -> float:
        econ = self.planet.econ_repo.get(self.tile)
        return float(econ.treasury) if econ else 0.0

    def biome(self) -> str:
        if self.planet.graph.has_node(self.tile):
            return self.planet.graph.nodes[self.tile].get("bioma", "Unknown")
        return "Unknown"

    def has_food_production(self) -> bool:
        econ = self.planet.econ_repo.get(self.tile)
        return econ is not None and float(econ.food_productivity or 0.0) > 0.0

    def has_ore_production(self) -> bool:
        econ = self.planet.econ_repo.get(self.tile)
        return econ is not None and float(econ.ore_productivity or 0.0) > 0.0

    # ------------------------------------------------------------------ #
    #  Revenue / Allocation                                                #
    # ------------------------------------------------------------------ #

    def revenue_total(self) -> float:
        r = self.planet.economy.calcular_equilibrio()
        return float(r.get_receita_total(self.tile))

    def get_food_pref(self) -> float:
        return float(self.planet.workforce_repo.ensure(self.tile).food_pref)

    def set_food_pref(self, v: float) -> None:
        pref = max(0.0, min(1.0, float(v)))
        self.planet.workforce_repo.ensure(self.tile).food_pref = pref

        econ = self.planet.econ_repo.get(self.tile)
        if econ:
            calculate_production(econ, pref)
            self.planet.economy.invalidar_cache()

    # ------------------------------------------------------------------ #
    #  Destacamento: fixo → móvel                                         #
    # ------------------------------------------------------------------ #

    def detach_worker(self) -> bool:
        """
        Executa imediatamente o destacamento de 1 worker fixo → unidade móvel.

        NÃO deve ser chamado diretamente pela UI.
        É chamado apenas pelo process_production() ao resolver QueueItemType.DETACH_WORKER.
        """
        econ = self.planet.econ_repo.get(self.tile)
        if not econ:
            return False

        if int(econ.workers) <= MIN_WORKERS_FIXOS:
            return False

        if self.province.owner is None:
            return False

        # Remove 1 worker fixo da economia
        econ.workers = int(econ.workers) - 1

        # Cria a unidade móvel em stack exclusiva de workers
        owner_id = self.province.owner.id
        stack = self._get_or_create_worker_stack(owner_id, self.tile)
        self.planet.stacks.add_unit_to_stack(stack.uid, "worker")

        print(f"⚒️ [Workforce] Worker destacado em {self.tile} para civ {owner_id}.")
        return True

    def _get_or_create_worker_stack(self, owner_id: int, tile) -> object:
        """Retorna stack exclusiva de workers ou cria uma nova."""
        for stack in self.planet.stacks.stacks_in_tile(tile):
            if stack.owner_id != owner_id:
                continue
            if stack.is_empty():
                continue
            if all(u.unit_key == "worker" for u in stack.units):
                return stack
        return self.planet.stacks.create_stack(owner_id=owner_id, tile=tile)

    def can_detach_worker(self) -> bool:
        """
        Retorna True se há workers suficientes para destacar.
        Leva em conta também quantos DETACH_WORKER já estão na fila
        (para não agendar mais do que o permitido).
        """
        econ = self.planet.econ_repo.get(self.tile)
        if not econ:
            return False

        # Quantos destacamentos já estão pendentes na fila?
        pending = sum(
            1 for it in self.planet.production_queues.items(self.tile)
            if it.item_type == QueueItemType.DETACH_WORKER
        )

        # workers que restarão após todos os destacamentos pendentes + este
        workers_after = int(econ.workers) - pending
        return workers_after > MIN_WORKERS_FIXOS

    def enqueue_detach_worker(self) -> bool:
        """
        Agenda o destacamento de 1 worker fixo para o próximo turno.

        Validações imediatas:
          - mínimo de workers fixos (MIN_WORKERS_FIXOS)
          - provincia tem dono

        Custo: 0 (instantâneo no turno seguinte, sem custo monetário).
        Retorna True se enfileirado com sucesso.
        """
        if not self.can_detach_worker():
            print(f"⚠️ [Workforce] Não é possível agendar destacamento: workers insuficientes em {self.tile}.")
            return False

        if self.province.owner is None:
            print(f"⚠️ [Workforce] Província em {self.tile} não tem dono.")
            return False

        self.planet.production_queues.add(
            self.tile,
            QueueItem(
                item_type=QueueItemType.DETACH_WORKER,
                data=None,
                cost=0.0,  # sem custo monetário: resolve no turno imediatamente
                paid=0.0,
            ),
        )
        print(f"📋 [Workforce] Destacamento agendado em {self.tile}.")
        return True

    # ------------------------------------------------------------------ #
    #  Reintegração: móvel → fixo (qualquer província)                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def can_reattach_worker(unit_uid: str, target_province: "Province", planet: "Planet") -> tuple[bool, str]:
        """
        Verifica se um worker móvel pode ser reintegrado na `target_province`.

        Condições:
          - A unidade deve existir e ser do tipo 'worker'
          - A stack deve estar no tile da província alvo
          - A província alvo deve ter um dono (não precisa ser o mesmo da origem)

        Retorna (ok: bool, motivo: str).
        """
        # Verifica existência da unidade
        stack_uid = planet.stacks.unit_uid_to_stack_uid.get(unit_uid)
        if stack_uid is None:
            return False, "Unidade não encontrada no mapa."

        stack = planet.stacks.get_stack(stack_uid)
        if stack is None or stack.is_empty():
            return False, "Stack da unidade não existe ou está vazia."

        # Verifica tipo da unidade
        unit = next((u for u in stack.units if u.uid == unit_uid), None)
        if unit is None:
            return False, "Unidade não encontrada na stack."
        if unit.unit_key != "worker":
            return False, f"Unidade '{unit.unit_key}' não é um worker."

        # Verifica se a stack está no tile alvo
        if stack.tile != target_province.tile_coords:
            return False, (
                f"Worker está em {stack.tile}, mas a província alvo é {target_province.tile_coords}. "
                "O worker precisa estar no tile da província para ser reintegrado."
            )

        # Verifica que a província alvo tem dono
        if target_province.owner is None:
            return False, "A província alvo não tem dono."

        return True, "OK"

    @staticmethod
    def reattach_worker(
        unit_uid: str,
        target_province: "Province",
        planet: "Planet",
    ) -> bool:
        """
        Reintegra um worker móvel em `target_province` (pode ser qualquer província).

        Fluxo:
          1. Valida condições via can_reattach_worker()
          2. Remove a unidade do mapa (stacks)
          3. Remove uid de mobile_worker_uids da origem (se ainda rastreado)
          4. Incrementa econ.workers na província alvo
          5. Recalcula produção do alvo
          6. Invalida cache de economia

        Retorna True se bem-sucedido.
        """
        ok, reason = ProvinceWorkforceFacade.can_reattach_worker(unit_uid, target_province, planet)
        if not ok:
            print(f"⚠️ [Workforce] Reintegração negada: {reason}")
            return False

        target_tile = target_province.tile_coords
        econ = planet.econ_repo.get(target_tile)
        if econ is None:
            print(f"⚠️ [Workforce] Estado econômico não encontrado para {target_tile}.")
            return False

        workforce_target = planet.workforce_repo.ensure(target_tile)

        # 1. Remove a unidade do mapa
        planet.stacks.remove_unit(unit_uid)

        # 2. Limpa rastreamento na província de origem (se ainda existir)
        #    Percorre todos os WorkforceStates procurando o uid
        for ws in planet.workforce_repo._by_tile.values():
            if unit_uid in ws.mobile_worker_uids:
                ws.mobile_worker_uids.remove(unit_uid)
                break  # uid é único

        # 3. Incrementa worker fixo no alvo
        econ.workers += 1

        # 4. Recalcula produção
        calculate_production(econ, workforce_target.food_pref)

        # 5. Invalida cache
        planet.economy.invalidar_cache()

        print(
            f"✅ [Workforce] Worker (uid={unit_uid[:8]}…) reintegrado em {target_tile} "
            f"(workers={econ.workers})"
        )
        return True

    # ------------------------------------------------------------------ #
    #  Fundação de nova província via worker móvel                         #
    # ------------------------------------------------------------------ #

    @staticmethod
    def can_found_province(
        unit_uid: str,
        planet: "Planet",
    ) -> tuple[bool, str]:
        """
        Verifica se um worker móvel pode fundar uma nova província no tile onde está.

        Condições:
          - A unidade deve existir e ser do tipo 'worker'
          - O tile não pode já ter uma província
          - O bioma do tile deve ser colonizável (terrestre)
        """
        from core.generation._geography import is_colonizable_biome

        stack_uid = planet.stacks.unit_uid_to_stack_uid.get(unit_uid)
        if stack_uid is None:
            return False, "Unidade não encontrada no mapa."

        stack = planet.stacks.get_stack(stack_uid)
        if stack is None or stack.is_empty():
            return False, "Stack da unidade não existe ou está vazia."

        unit = next((u for u in stack.units if u.uid == unit_uid), None)
        if unit is None:
            return False, "Unidade não encontrada na stack."
        if unit.unit_key != "worker":
            return False, f"Unidade '{unit.unit_key}' não é um worker."

        tile = stack.tile

        # Tile já tem província?
        if planet.get_province(tile) is not None:
            return False, f"O tile {tile} já possui uma província."

        # Bioma colonizável?
        biome = planet.graph.nodes.get(tile, {}).get("bioma", "")
        if not is_colonizable_biome(biome):
            return False, f"Bioma '{biome}' não é colonizável."

        return True, "OK"

    @staticmethod
    def found_province(
            unit_uid: str,
            planet: "Planet",
    ) -> bool:
        """
        Funda uma nova província no tile do worker móvel.
        (Agora com nome procedural via services, com fallback.)
        """
        from core.civilization import Province
        from core.economy.production import init_province_economy

        ok, reason = ProvinceWorkforceFacade.can_found_province(unit_uid, planet)
        if not ok:
            print(f"⚠️ [Workforce] Fundação negada: {reason}")
            return False

        stack_uid = planet.stacks.unit_uid_to_stack_uid[unit_uid]
        stack = planet.stacks.get_stack(stack_uid)
        tile = stack.tile
        owner_id = stack.owner_id

        # Encontra a civilização dona
        civ = next((c for c in planet.civilizations if c.id == owner_id), None)
        if civ is None:
            print(f"⚠️ [Workforce] Civilização {owner_id} não encontrada.")
            return False

        # Dados do tile
        node_data = planet.graph.nodes.get(tile, {})
        biome = node_data.get("bioma", "Meadow")
        plate = node_data.get("placa", "Unknown")
        fertility = node_data.get("fertilidade", 3.0)

        # --- NOVO: nome procedural (plugável) ---
        prov_name = f"Colônia de {civ.name}"
        try:
            from services.province_naming_service import generate_unique_province_name

            prov_name = generate_unique_province_name(
                planet=planet,
                civ=civ,
                tile=tile,
                is_capital=False,
                sanitizer="western",
            )
        except ImportError:
            # service não disponível -> fallback
            pass
        except Exception as e:
            print(f"⚠️ [Naming] Falha ao gerar nome de província fundada (civ={civ.id}, tile={tile}): {e}")

        # Cria a Province
        new_province = Province(
            owner=civ,
            tile_coords=tile,
            is_capital=False,
            name=str(prov_name),
        )
        civ.provinces.append(new_province)
        planet.provinces_by_tile[tile] = new_province

        # Inicializa economia (começa com 1 worker — o próprio que fundou)
        econ_state = init_province_economy(
            tile=tile,
            biome=biome,
            fertility=fertility,
            tectonic_plate=plate,
            workers=1,
        )
        planet.econ_repo.upsert(econ_state)

        # Remove unidade do mapa
        planet.stacks.remove_unit(unit_uid)

        # Limpa rastreamento
        for ws in planet.workforce_repo._by_tile.values():
            if unit_uid in ws.mobile_worker_uids:
                ws.mobile_worker_uids.remove(unit_uid)
                break

        # Invalida cache
        planet.economy.invalidar_cache()

        print(
            f"🏛️ [Workforce] Nova província fundada por {civ.name} em {tile} "
            f"(bioma={biome}, fertilidade={fertility:.2f}, nome='{prov_name}')"
        )
        return True

    # ------------------------------------------------------------------ #
    #  Queue: enqueue                                                      #
    # ------------------------------------------------------------------ #

    def enqueue_worker(self) -> bool:
        econ = self.planet.econ_repo.get(self.tile)
        if not econ:
            return False

        civ = self.province.owner
        if not civ:
            return False

        cost = worker_cost(civ.workers_purchased)

        self.planet.production_queues.add(
            self.tile,
            QueueItem(item_type=QueueItemType.WORKER, data=None, cost=float(cost), paid=0.0),
        )
        civ.workers_purchased += 1
        return True

    def enqueue_military_unit(self, unit_key: str) -> bool:
        stats = get_unit_stats(unit_key)
        if not stats:
            print(f"❌ Facade: Unidade desconhecida '{unit_key}'")
            return False

        item = QueueItem(
            item_type=QueueItemType.MILITARY,
            data=str(unit_key),
            cost=float(stats.cost),
            paid=0.0,
        )
        self.planet.production_queues.add(self.tile, item)
        return True

    # ------------------------------------------------------------------ #
    #  Queue: read                                                         #
    # ------------------------------------------------------------------ #

    def queue_items(self) -> list[QueueItem]:
        return self.planet.production_queues.items(self.tile)

    def queue_total_cost(self) -> float:
        return float(sum(float(it.cost or 0.0) for it in self.queue_items()))

    def queue_total_paid(self) -> float:
        return float(sum(float(getattr(it, "paid", 0.0) or 0.0) for it in self.queue_items()))

    def queue_total_remaining(self) -> float:
        return float(sum(float(getattr(it, "remaining", 0.0) or 0.0) for it in self.queue_items()))

    # ------------------------------------------------------------------ #
    #  Queue: cancel / remove                                              #
    # ------------------------------------------------------------------ #

    def queue_remove(self, uid: str) -> bool:
        econ = self.planet.econ_repo.get(self.tile)
        if not econ:
            return False

        q = self.planet.production_queues.ensure(self.tile)

        for i, it in enumerate(q.items):
            if it.uid == uid:
                paid = float(getattr(it, "paid", 0.0) or 0.0)
                refund = 0.5 * paid
                if refund > 0.0:
                    econ.treasury += refund

                if it.item_type == QueueItemType.WORKER:
                    civ = self.province.owner
                    if civ and civ.workers_purchased > 0:
                        civ.workers_purchased -= 1

                q.items.pop(i)
                return True

        return False

    def queue_clear(self) -> int:
        econ = self.planet.econ_repo.get(self.tile)
        if not econ:
            return 0

        q = self.planet.production_queues.ensure(self.tile)

        total_refund = 0.0
        workers_canceled = 0
        for it in q.items:
            total_refund += 0.5 * float(getattr(it, "paid", 0.0) or 0.0)
            if it.item_type == QueueItemType.WORKER:
                workers_canceled += 1

        if total_refund > 0.0:
            econ.treasury += total_refund

        civ = self.province.owner
        if civ and workers_canceled > 0:
            civ.workers_purchased = max(0, civ.workers_purchased - workers_canceled)

        n = len(q.items)
        q.items.clear()
        return n

    # ------------------------------------------------------------------ #
    #  Helpers privados                                                    #
    # ------------------------------------------------------------------ #

    def _get_or_create_owner_stack(self, owner_id: int, tile: Tile):
        """
        Retorna uma stack exclusiva de workers do owner no tile,
        ou cria uma nova se não houver.

        Regra: workers só ficam em stacks cujas unidades são TODAS 'worker'.
        Nunca mistura com unidades militares ou civis de outro tipo.
        """
        for stack in self.planet.stacks.stacks_in_tile(tile):
            if stack.owner_id != owner_id:
                continue
            if stack.is_empty():
                continue
            # Só reutiliza se TODAS as unidades da stack são workers
            if all(u.unit_key == "worker" for u in stack.units):
                return stack

        # Nenhuma stack exclusiva de workers encontrada → cria nova
        return self.planet.stacks.create_stack(owner_id=owner_id, tile=tile)

    # ------------------------------------------------------------------ #
    #  Cálculo de receita                                                #
    # ------------------------------------------------------------------ #

    def get_auto_max_revenue(self) -> bool:
        return bool(self.planet.workforce_repo.ensure(self.tile).auto_max_revenue)

    def set_auto_max_revenue(self, v: bool) -> None:
        self.planet.workforce_repo.ensure(self.tile).auto_max_revenue = bool(v)
