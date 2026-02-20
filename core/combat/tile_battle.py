# core/combat/tile_battle.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .models import CombatContext, CombatResult
from .resolver import CombatResolver
from .unit_adapter import combat_unit_from_key
from .modifiers import AdvantageModifier


@dataclass(frozen=True, slots=True)
class UnitRef:
    unit_key: str
    uid: str
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
    initial_attackers: list[UnitRef]
    initial_defenders: list[UnitRef]
    survivors_attackers: list[UnitRef]
    survivors_defenders: list[UnitRef]
    stopped_by_max_duels: bool = False


class TileBattleResolver:
    """
    Modelo literal (Modo A) com multi-ciclo:

    1) Embaralha atacantes e defensores (ordem fixa).
    2) Repete "ciclos" enquanto ambos lados tiverem unidades:
       - Fase 1: pareia 1-para-1 os primeiros min(A, D) (posição i vs posição i).
       - Fase 2: se A > D, atacantes excedentes (índices D..A-1) atacam defensores sobreviventes em wrap-around.
                se D > A, defensores excedentes retaliam (índices A..D-1) em wrap-around contra atacantes sobreviventes.
    3) Se após a Fase 2 ambos ainda existirem, inicia novo ciclo voltando ao início do grupo maior
       (porque o menor foi persistente o suficiente).

    Cada duelo elimina exatamente 1 unidade (perdedor).

    Notas:
    - Este resolver injeta AdvantageModifier por padrão (vantagem ponderada por par).
    - Para performance, não re-cria CombatUnit só para comparar vencedor: usa unit_key diretamente.
    """
    def __init__(self, duel_resolver: CombatResolver | None = None):
        self.duel_resolver = duel_resolver or CombatResolver(modifiers=[AdvantageModifier()])

    def resolve(
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
            # CombatUnit.key == unit_key (adapter). Então podemos comparar direto.
            return res.winner.key == a.unit_key

        # Loop de ciclos
        while atk and dfn:
            if duel_index >= max_duels:
                stopped_by_max_duels = True
                break

            # -----------------------
            # Fase 1: 1-para-1
            # -----------------------
            pairs = min(len(atk), len(dfn))

            atk_survivors_phase1: list[UnitRef] = []
            dfn_survivors_phase1: list[UnitRef] = []

            # Excedentes (ainda não agiram nesse ciclo)
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

            # Se paramos no meio do ciclo, devolve estado consistente
            if stopped_by_max_duels:
                atk = atk_survivors_phase1 + atk_excess
                dfn = dfn_survivors_phase1 + dfn_excess
                break

            # Atualiza listas vivas após fase 1 (mantém ordem relativa)
            atk = atk_survivors_phase1 + atk_excess
            dfn = dfn_survivors_phase1 + dfn_excess

            if not atk or not dfn:
                break

            # -----------------------
            # Fase 2: excedentes do maior atacam em wrap-around
            # -----------------------
            if len(atk) > len(dfn):
                # atacantes excedentes começam no índice len(dfn)
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
                        # defensor morre
                        dfn.remove(b)
                        if dfn:
                            idx_def = idx_def % len(dfn)
                        i += 1  # atacante viveu, próximo excedente
                    else:
                        # atacante morre
                        atk.remove(a)
                        # não incrementa i: próximo excedente cai nessa posição

                if stopped_by_max_duels:
                    break

            elif len(dfn) > len(atk):
                # defensores excedentes começam no índice len(atk)
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

                    # aqui o "attacker do duelo" é d (defensor excedente retaliando)
                    if res.winner.key == d.unit_key:
                        atk.remove(a)
                        if atk:
                            idx_atk = idx_atk % len(atk)
                        i += 1
                    else:
                        dfn.remove(d)
                        # não incrementa i

                if stopped_by_max_duels:
                    break

            # tamanhos iguais: fase 1 já fez tudo; loop reinicia (novo ciclo) se ainda houver ambos

        return TileBattleReport(
            events=events,
            initial_attackers=initial_atk,
            initial_defenders=initial_dfn,
            survivors_attackers=atk,
            survivors_defenders=dfn,
            stopped_by_max_duels=stopped_by_max_duels,
        )
