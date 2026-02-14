from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .models import CombatContext, CombatResult
from .resolver import CombatResolver
from .unit_adapter import combat_unit_from_key


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
    """
    def __init__(self, duel_resolver: CombatResolver | None = None):
        self.duel_resolver = duel_resolver or CombatResolver()

    def resolve(
        self,
        attackers: Iterable[UnitRef],
        defenders: Iterable[UnitRef],
        ctx: CombatContext | None = None,
        *,
        shuffle: bool = True,
        max_duels: int = 1_000_000,
    ) -> TileBattleReport:
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

        def duel(a: UnitRef, b: UnitRef) -> CombatResult:
            a_unit = combat_unit_from_key(a.unit_key)
            b_unit = combat_unit_from_key(b.unit_key)
            return self.duel_resolver.resolve(a_unit, b_unit, ctx)

        # Loop de ciclos
        while atk and dfn:
            if duel_index >= max_duels:
                break

            # -----------------------
            # Fase 1: 1-para-1
            # -----------------------
            pairs = min(len(atk), len(dfn))

            atk_survivors_phase1: list[UnitRef] = []
            dfn_survivors_phase1: list[UnitRef] = []

            # Guardar excedentes (ainda não agiram nesse ciclo)
            atk_excess = atk[pairs:]   # se atk maior
            dfn_excess = dfn[pairs:]   # se dfn maior

            for i in range(pairs):
                if duel_index >= max_duels:
                    break

                a = atk[i]
                b = dfn[i]
                res = duel(a, b)
                events.append(DuelEvent(duel_index, a, b, res))
                duel_index += 1

                # Determinar vencedor comparando pelas keys normalizadas do adapter
                a_key = combat_unit_from_key(a.unit_key).key
                if res.winner.key == a_key:
                    atk_survivors_phase1.append(a)
                else:
                    dfn_survivors_phase1.append(b)

            if duel_index >= max_duels:
                # estado “no meio”: retornamos o que temos
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
            # (literal: começam no índice "len(menor)")
            # -----------------------
            if len(atk) > len(dfn):
                start = len(dfn)  # atacante # (D+1)
                idx_def = 0
                i = start
                while i < len(atk) and dfn:
                    if duel_index >= max_duels:
                        break

                    a = atk[i]
                    b = dfn[idx_def % len(dfn)]
                    res = duel(a, b)
                    events.append(DuelEvent(duel_index, a, b, res))
                    duel_index += 1

                    a_key = combat_unit_from_key(a.unit_key).key
                    if res.winner.key == a_key:
                        # defensor morre
                        dfn.remove(b)
                        # idx_def fica consistente mesmo com remoção
                        if dfn:
                            idx_def = idx_def % len(dfn)
                        i += 1  # atacante viveu, próximo excedente
                    else:
                        # atacante morre
                        atk.remove(a)
                        # não incrementa i: próximo excedente “cai” nessa posição

                if duel_index >= max_duels:
                    break

            elif len(dfn) > len(atk):
                start = len(atk)  # defensor # (A+1) retaliando
                idx_atk = 0
                i = start
                while i < len(dfn) and atk:
                    if duel_index >= max_duels:
                        break

                    d = dfn[i]
                    a = atk[idx_atk % len(atk)]
                    res = duel(d, a)
                    events.append(DuelEvent(duel_index, d, a, res))
                    duel_index += 1

                    d_key = combat_unit_from_key(d.unit_key).key
                    if res.winner.key == d_key:
                        # atacante morre
                        atk.remove(a)
                        if atk:
                            idx_atk = idx_atk % len(atk)
                        i += 1  # defensor viveu, próximo excedente
                    else:
                        # defensor morre
                        dfn.remove(d)
                        # não incrementa i: próximo excedente “cai” nessa posição

                if duel_index >= max_duels:
                    break

            else:
                # tamanhos iguais: só fase 1 já resolve o ciclo inteiro
                pass

            # Se após fase 2 ainda existem ambos, o loop reinicia automaticamente (novo ciclo),
            # que é exatamente “o menor foi persistente o suficiente”.
            # (E como as listas já estão embaralhadas e a ordem é preservada, isso vira uma “ordem fixa”.)

        return TileBattleReport(
            events=events,
            initial_attackers=initial_atk,
            initial_defenders=initial_dfn,
            survivors_attackers=atk,
            survivors_defenders=dfn,
        )
