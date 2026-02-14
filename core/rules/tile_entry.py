from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterable, Protocol

from core.diplomacy import Relation


class DiplomacyProvider(Protocol):
    """
    Interface mínima: o motor pergunta a relação entre duas civs.
    Você implementa isso no Planet/GameState depois.
    """
    def relation(self, mover_civ_id: int, other_civ_id: int) -> Relation: ...


class EntryOutcome(Enum):
    ALLOW_NO_COMBAT = auto()
    ALLOW_WITH_COMBAT = auto()
    BLOCK = auto()


@dataclass(frozen=True, slots=True)
class EntryDecision:
    outcome: EntryOutcome
    reason: str
    present_relations: dict[int, Relation]  # other_civ_id -> relation


def decide_entry(
    *,
    mover_civ_id: int,
    present_civ_ids: Iterable[int],
    diplomacy: DiplomacyProvider,
) -> EntryDecision:
    present = [cid for cid in set(present_civ_ids) if cid != mover_civ_id]

    if not present:
        return EntryDecision(
            outcome=EntryOutcome.ALLOW_NO_COMBAT,
            reason="tile vazio (ou apenas unidades próprias)",
            present_relations={},
        )

    rels: dict[int, Relation] = {cid: diplomacy.relation(mover_civ_id, cid) for cid in present}
    rel_values = set(rels.values())

    if rel_values == {Relation.ALLY}:
        return EntryDecision(
            outcome=EntryOutcome.ALLOW_NO_COMBAT,
            reason="todas as civs presentes são aliadas",
            present_relations=rels,
        )

    if rel_values == {Relation.ENEMY}:
        return EntryDecision(
            outcome=EntryOutcome.ALLOW_WITH_COMBAT,
            reason="todas as civs presentes são inimigas (ataque permitido)",
            present_relations=rels,
        )

    return EntryDecision(
        outcome=EntryOutcome.BLOCK,
        reason="movimento proibido: mistura de relações no tile (não é 'tudo aliado' nem 'tudo inimigo')",
        present_relations=rels,
    )
