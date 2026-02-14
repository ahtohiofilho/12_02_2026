from __future__ import annotations

from core.combat.tile_battle import TileBattleReport
from core.stacks.repo import StackRepository


def killed_unit_uids(report: TileBattleReport) -> list[str]:
    killed: list[str] = []
    for e in report.events:
        winner_key = e.result.winner.key

        a_key = e.result.attacker.key
        d_key = e.result.defender.key

        # se winner é attacker do duelo, loser foi defender
        if winner_key == a_key:
            killed.append(e.defender.uid)
        else:
            killed.append(e.attacker.uid)
    return killed


def apply_kills(stacks: StackRepository, unit_uids: list[str]) -> None:
    for uid in unit_uids:
        stacks.remove_unit(uid)
