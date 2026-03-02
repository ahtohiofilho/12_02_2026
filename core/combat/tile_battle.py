# core/combat/tile_battle.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from core.combat.models import CombatContext
from core.combat.resolver import CombatResolver
from core.combat.models import CombatResult
from config.unit_stats import UNIT_STATS
from core.combat.models import combat_unit_from_stats

# Ajuste este import conforme o seu projeto:
# A ideia é: diplomacy fornece um método para saber se dois owners são inimigos.
from core.diplomacy import DiplomacyMatrix, Relation


def combat_unit_from_key(unit_key: str):
    stats = UNIT_STATS.get(unit_key)
    if stats is None:
        raise KeyError(f"UnitStats não encontrado para unit_key={unit_key!r}")
    return combat_unit_from_stats(unit_key, stats)


@dataclass(frozen=True, slots=True)
class UnitRef:
    unit_key: str
    uid: str
    owner_id: int
    meta: dict[str, Any]


@dataclass(frozen=True, slots=True)
class DuelEvent:
    duel_index: int
    attacker: UnitRef
    defender: UnitRef
    result: CombatResult


@dataclass(frozen=True, slots=True)
class TileBattleReport:
    events: list[DuelEvent]

    # legado (2 lados)
    initial_attackers: list[UnitRef] = field(default_factory=list)
    initial_defenders: list[UnitRef] = field(default_factory=list)
    survivors_attackers: list[UnitRef] = field(default_factory=list)
    survivors_defenders: list[UnitRef] = field(default_factory=list)

    # novo (unificado)
    initial_units: list[UnitRef] = field(default_factory=list)
    survivors_units: list[UnitRef] = field(default_factory=list)

    stopped_by_max_duels: bool = False


class TileBattleResolver:
    def __init__(self, duel_resolver: CombatResolver, diplomacy: DiplomacyMatrix):
        self.duel_resolver = duel_resolver
        self.diplomacy = diplomacy

    # -------------------------
    # Resolver NOVO (unificado)
    # -------------------------
    def resolve(
        self,
        *,
        units: Iterable[UnitRef],
        ctx: CombatContext | None = None,
        shuffle: bool = True,
        max_duels: int = 1_000_000,
    ) -> TileBattleReport:
        """
        Resolve batalha em 1 tile com múltiplas civs.
        Regra: continuam duelos enquanto houver pelo menos 2 lados com relação HOSTILE entre si.
        """
        if max_duels <= 0:
            raise ValueError("max_duels deve ser > 0")

        ctx = ctx or CombatContext()
        alive: list[UnitRef] = list(units)
        initial_units = list(alive)

        if shuffle:
            self.duel_resolver.rng.shuffle(alive)

        events: list[DuelEvent] = []
        duel_index = 0
        stopped_by_max_duels = False

        def relation(a_owner: int, b_owner: int) -> Relation:
            return self.diplomacy.relation(a_owner, b_owner)

        def hostile(a: UnitRef, b: UnitRef) -> bool:
            if a.owner_id == b.owner_id:
                return False
            return relation(a.owner_id, b.owner_id) == Relation.ENEMY

        def duel(a: UnitRef, b: UnitRef) -> CombatResult:
            a_unit = combat_unit_from_key(a.unit_key)
            b_unit = combat_unit_from_key(b.unit_key)
            return self.duel_resolver.resolve(a_unit, b_unit, ctx)

        def still_has_hostiles(pool: list[UnitRef]) -> bool:
            owners = list({u.owner_id for u in pool})
            # checa se existe ao menos um par ENEMY
            for i in range(len(owners)):
                for j in range(i + 1, len(owners)):
                    if relation(owners[i], owners[j]) == Relation.ENEMY:
                        return True
            return False

        # Loop principal: escolhe um duelista e um inimigo e resolve 1 duelo por iteração
        while len(alive) >= 2 and still_has_hostiles(alive):
            if duel_index >= max_duels:
                stopped_by_max_duels = True
                break

            # escolhe um atacante que tenha algum inimigo disponível
            attacker: UnitRef | None = None
            defender: UnitRef | None = None

            # varredura simples (determinística dado shuffle inicial)
            for a in alive:
                for b in alive:
                    if a is b:
                        continue
                    if hostile(a, b):
                        attacker = a
                        defender = b
                        break
                if attacker is not None:
                    break

            if attacker is None or defender is None:
                break  # não há mais pares hostis

            res = duel(attacker, defender)
            events.append(DuelEvent(duel_index, attacker, defender, res))
            duel_index += 1

            # vencedor é CombatUnit com .key igual ao unit_key do UnitRef correspondente
            winner_key = res.winner.key
            if winner_key == attacker.unit_key:
                # defensor morre
                # remove por uid (mais seguro que 'is'/'==', e mantém integridade)
                alive = [u for u in alive if u.uid != defender.uid]
            else:
                # atacante morre
                alive = [u for u in alive if u.uid != attacker.uid]

        return TileBattleReport(
            events=events,
            initial_units=initial_units,
            survivors_units=alive,
            stopped_by_max_duels=stopped_by_max_duels,
        )

    # -----------------------------------
    # Resolver LEGADO (2 lados, seu código)
    # -----------------------------------
    def resolve_two_sided(
        self,
        attackers: Iterable[UnitRef],
        defenders: Iterable[UnitRef],
        ctx: CombatContext | None = None,
        *,
        shuffle: bool = True,
        max_duels: int = 1_000_000,
    ) -> TileBattleReport:
        if max_duels <= 0:
            raise ValueError("max_duels deve ser > 0")

        ctx = ctx or CombatContext()

        atk = list(attackers)
        dfn = list(defenders)

        initial_atk = list(atk)
        initial_dfn = list(dfn)

        if shuffle:
            self.duel_resolver.rng.shuffle(atk)
            self.duel_resolver.rng.shuffle(dfn)

        events: list[DuelEvent] = []
        duel_index = 0
        stopped_by_max_duels = False

        def duel(a: UnitRef, b: UnitRef) -> CombatResult:
            a_unit = combat_unit_from_key(a.unit_key)
            b_unit = combat_unit_from_key(b.unit_key)
            return self.duel_resolver.resolve(a_unit, b_unit, ctx)

        def _winner_is_attacker(res: CombatResult, a: UnitRef) -> bool:
            return res.winner.key == a.unit_key

        while atk and dfn:
            if duel_index >= max_duels:
                stopped_by_max_duels = True
                break

            pairs = min(len(atk), len(dfn))

            atk_survivors_phase1: list[UnitRef] = []
            dfn_survivors_phase1: list[UnitRef] = []

            atk_excess = atk[pairs:]
            dfn_excess = dfn[pairs:]

            for i in range(pairs):
                if duel_index >= max_duels:
                    stopped_by_max_duels = True
                    break

                a = atk[i]
                b = dfn[i]
                res = duel(a, b)
                events.append(DuelEvent(duel_index, a, b, res))
                duel_index += 1

                if _winner_is_attacker(res, a):
                    atk_survivors_phase1.append(a)
                else:
                    dfn_survivors_phase1.append(b)

            if stopped_by_max_duels:
                atk = atk_survivors_phase1 + atk_excess
                dfn = dfn_survivors_phase1 + dfn_excess
                break

            atk = atk_survivors_phase1 + atk_excess
            dfn = dfn_survivors_phase1 + dfn_excess

            if not atk or not dfn:
                break

            if len(atk) > len(dfn):
                i = len(dfn)
                idx_def = 0

                while i < len(atk) and dfn:
                    if duel_index >= max_duels:
                        stopped_by_max_duels = True
                        break

                    a = atk[i]
                    b = dfn[idx_def % len(dfn)]

                    res = duel(a, b)
                    events.append(DuelEvent(duel_index, a, b, res))
                    duel_index += 1

                    if _winner_is_attacker(res, a):
                        dfn.remove(b)
                        if dfn:
                            idx_def = idx_def % len(dfn)
                        i += 1
                    else:
                        atk.remove(a)

                if stopped_by_max_duels:
                    break

            elif len(dfn) > len(atk):
                i = len(atk)
                idx_atk = 0

                while i < len(dfn) and atk:
                    if duel_index >= max_duels:
                        stopped_by_max_duels = True
                        break

                    d = dfn[i]
                    a = atk[idx_atk % len(atk)]

                    res = duel(d, a)
                    events.append(DuelEvent(duel_index, d, a, res))
                    duel_index += 1

                    if res.winner.key == d.unit_key:
                        atk.remove(a)
                        if atk:
                            idx_atk = idx_atk % len(atk)
                        i += 1
                    else:
                        dfn.remove(d)

                if stopped_by_max_duels:
                    break

        return TileBattleReport(
            events=events,
            initial_attackers=initial_atk,
            initial_defenders=initial_dfn,
            survivors_attackers=atk,
            survivors_defenders=dfn,
            stopped_by_max_duels=stopped_by_max_duels,
        )
