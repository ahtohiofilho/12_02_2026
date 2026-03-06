# core/combat_v2/engine.py
from __future__ import annotations

import random
from typing import Callable

from core.combat.models import CombatContext
from core.combat.resolver import CombatResolver
from core.diplomacy import DiplomacyMatrix, Relation

from .api import UnitRuntime, TileCombatReportV2
from .target_selection import weighted_choice
from .tables import local_exposure, remote_preference, remote_distance_multiplier
from .duel import resolve_duel


Tile = tuple[int, int]
DistanceFn = Callable[[Tile, Tile], int | None]


class TileCombatEngineV2:
    """
    v2.1 (consolidado, compatível com o MVP-1):

    - P1: 1 duelo COMO ATACANTE por unidade por rodada (u.attacked_this_round)
    - EVASIVE (detalhe extra do contrato, conforme você corrigiu):
        * EVASIVE pode ser alvo/defensor
        * EVASIVE NÃO pode atacar (logo, não entra na lista de "attackers")
    - Seleção estocástica de defensor:
        * range(A)==0  => usa T4 (local_exposure)
        * range(A)>0   => usa T5 (remote_preference) e (opcional) m_remote_distance
    - Retaliação por distância: delegada para resolve_duel(dist_tiles=...)
      (resolve_duel checa dist<=range(D))

    Observação:
    - Este engine continua "local-only" no sentido de que resolve o combate para um tile,
      mas agora suporta atacar defensores a distâncias >0 DESDE que as unidades fornecidas
      incluam unidades remotas e que distance_fn seja fornecida.
    - Pool/ordens explícitas ("ninguém é puxado pro pool") deve ser garantido por quem
      monta o input `units`.
    """

    def __init__(
        self,
        *,
        resolver: CombatResolver,
        diplomacy: DiplomacyMatrix,
        rng: random.Random | None = None,
    ):
        self.resolver = resolver
        self.diplomacy = diplomacy
        self.rng = rng or random.Random()

    @staticmethod
    def _can_attack(u: UnitRuntime) -> bool:
        """Regra extra: EVASIVE não pode atacar."""
        return bool(getattr(u, "evasion_mode", "COMMITTED") != "EVASIVE")

    @staticmethod
    def _dist(distance_fn: DistanceFn | None, a: Tile, b: Tile) -> int | None:
        if a == b:
            return 0
        if distance_fn is None:
            # Sem distance_fn, só suportamos duelos locais com dist=0
            return None
        try:
            d = distance_fn(a, b)
        except Exception:
            return None
        if d is None:
            return None
        try:
            di = int(d)
        except Exception:
            return None
        return di if di >= 0 else None

    def resolve_for_tile(
        self,
        *,
        tile: Tile,
        units: list[UnitRuntime],
        ctx: CombatContext | None = None,
        max_duels: int = 1_000_000,
        distance_fn: DistanceFn | None = None,
    ) -> TileCombatReportV2:
        """
        Resolve combate "associado" a um tile `tile`.

        Importante:
        - `units` deve conter exatamente o pool permitido (local + remotos explicitamente ordenados).
        - A função NÃO descobre ordens; ela apenas executa a resolução estocástica/duelos.

        `distance_fn(a,b)` deve retornar distância em tiles (0,1,2,...) ou None se desconhecida.
        """
        ctx = ctx or CombatContext(defender_tile=tile)

        alive = [u for u in units if getattr(u, "alive", True)]
        alive_count = len(alive)

        killed_uids: list[str] = []
        duels = []
        stopped = False
        duel_count = 0

        def hostile(a: UnitRuntime, b: UnitRuntime) -> bool:
            return (
                a.owner_id != b.owner_id
                and self.diplomacy.relation(a.owner_id, b.owner_id) == Relation.ENEMY
            )

        def still_has_hostiles(pool: list[UnitRuntime]) -> bool:
            owners = list({u.owner_id for u in pool if u.alive})
            for i in range(len(owners)):
                for j in range(i + 1, len(owners)):
                    if self.diplomacy.relation(owners[i], owners[j]) == Relation.ENEMY:
                        return True
            return False

        # início da rodada
        for u in alive:
            u.attacked_this_round = False

        while alive_count >= 2 and still_has_hostiles(alive):
            if duel_count >= max_duels:
                stopped = True
                break

            attackers: list[UnitRuntime] = []
            for u in alive:
                if not u.alive:
                    continue
                if u.attacked_this_round:
                    continue
                if not self._can_attack(u):
                    continue  # ✅ EVASIVE não ataca
                # elegível se existir ao menos um defensor hostil alcançável (dist <= range(A))
                found = False
                for v in alive:
                    if not v.alive or not hostile(u, v):
                        continue
                    dist = self._dist(distance_fn, u.tile, v.tile)
                    if dist is None:
                        continue
                    if dist <= int(getattr(u, "range", 0) or 0):
                        found = True
                        break
                if found:
                    attackers.append(u)

            if not attackers:
                # nova rodada
                for u in alive:
                    if u.alive:
                        u.attacked_this_round = False
                continue

            # atacante uniforme (você pode ponderar no futuro; contrato só exige estocástico)
            A = self.rng.choice(attackers)

            # defensores hostis + em alcance
            defenders: list[UnitRuntime] = []
            dists: list[int] = []  # dist(A, D) alinhado com defenders
            for v in alive:
                if not v.alive:
                    continue
                if not hostile(A, v):
                    continue
                dist = self._dist(distance_fn, A.tile, v.tile)
                if dist is None:
                    continue
                if dist <= int(getattr(A, "range", 0) or 0):
                    defenders.append(v)
                    dists.append(dist)

            if not defenders:
                # sem defensor elegível (por alcance/sem distance_fn), consome o ataque e segue
                A.attacked_this_round = True
                continue

            # pesos (T4/T5 + opcional dist bonus)
            A_range = int(getattr(A, "range", 0) or 0)
            weights: list[float] = []
            for v, dist in zip(defenders, dists):
                w = 1.0
                if A_range <= 0:
                    w *= local_exposure(v.unit_key)
                else:
                    w *= remote_preference(v.unit_key)
                    w *= remote_distance_multiplier(dist)
                weights.append(float(w))

            D = weighted_choice(self.rng, defenders, weights)
            if D is None:
                # fallback: uniforme
                D = self.rng.choice(defenders)

            # encontra dist de D escolhido (necessário p/ retaliação)
            dist_tiles = None
            for vv, dd in zip(defenders, dists):
                if vv is D:
                    dist_tiles = dd
                    break
            if dist_tiles is None:
                dist_tiles = 0 if A.tile == D.tile else (self._dist(distance_fn, A.tile, D.tile) or 0)

            outcome = resolve_duel(
                attacker=A,
                defender=D,
                resolver=self.resolver,
                ctx=ctx,
                rng=self.rng,
                dist_tiles=int(dist_tiles),
            )
            duels.append(outcome)
            duel_count += 1

            if outcome.attacker_killed and A.alive:
                A.alive = False
                alive_count -= 1
                killed_uids.append(A.uid)

            if outcome.defender_killed and D.alive:
                D.alive = False
                alive_count -= 1
                killed_uids.append(D.uid)

            # P1
            A.attacked_this_round = True

        return TileCombatReportV2(
            tile=tile,
            duels=duels,
            killed_uids=killed_uids,
            stopped_by_max_duels=stopped,
        )

    # ─────────────────────────────────────────────────────────────
    # Compat: mantém sua API anterior (local-only) chamando a nova
    # ─────────────────────────────────────────────────────────────
    def resolve_tile_local(
        self,
        *,
        tile: Tile,
        units: list[UnitRuntime],
        ctx: CombatContext | None = None,
        max_duels: int = 1_000_000,
    ) -> TileCombatReportV2:
        """
        Backward compatible: resolve apenas dist=0.
        Note que, sem distance_fn, só serão elegíveis pares no mesmo tile.
        """
        # Para local-only, passamos distance_fn=None e esperamos que u.tile==v.tile.
        return self.resolve_for_tile(
            tile=tile,
            units=units,
            ctx=ctx,
            max_duels=max_duels,
            distance_fn=None,
        )
