# ui/province/combat_preview.py
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QGroupBox
from PySide6.QtCore import Qt

from core.combat import CombatResolver, AdvantageModifier, combat_unit_from_key, CombatContext
from config.unit_stats import UNIT_STATS


class CombatPreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.resolver = CombatResolver(modifiers=[AdvantageModifier()])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        row = QHBoxLayout()
        self.cmb_attacker = QComboBox()
        self.cmb_defender = QComboBox()

        keys = sorted(UNIT_STATS.keys())
        self.cmb_attacker.addItems(keys)
        self.cmb_defender.addItems(keys)

        row.addWidget(QLabel("Attacker:"))
        row.addWidget(self.cmb_attacker, 1)
        row.addWidget(QLabel("Defender:"))
        row.addWidget(self.cmb_defender, 1)
        layout.addLayout(row)

        group = QGroupBox("Result")
        g = QVBoxLayout(group)

        self.lbl_odds = QLabel("—")
        self.lbl_odds.setAlignment(Qt.AlignLeft)
        g.addWidget(self.lbl_odds)

        self.lbl_mods = QLabel("—")
        self.lbl_mods.setWordWrap(True)
        self.lbl_mods.setStyleSheet("color: #aaa; font-size: 11px;")
        g.addWidget(self.lbl_mods)

        layout.addWidget(group)

        self.cmb_attacker.currentTextChanged.connect(self.update_preview)
        self.cmb_defender.currentTextChanged.connect(self.update_preview)

        self.update_preview()

    def update_preview(self) -> None:
        a_key = self.cmb_attacker.currentText()
        d_key = self.cmb_defender.currentText()

        ctx = CombatContext()
        a = combat_unit_from_key(a_key)
        d = combat_unit_from_key(d_key)

        odds = self.resolver.odds(a, d, ctx)
        res = self.resolver.resolve(a, d, ctx)  # só para debug/multipliers (pode trocar por _effective se expor)

        self.lbl_odds.setText(
            f"P(attacker win) = {odds.p_attacker_win:.3f} | "
            f"P(defender win) = {odds.p_defender_win:.3f}"
        )

        # Debug multipliers
        mults = res.debug.get("multipliers", [])
        if mults:
            parts = []
            for m in mults:
                parts.append(f"{m['modifier']}: attacker×{m['attacker']:.2f}, defender×{m['defender']:.2f}")
            self.lbl_mods.setText("Multipliers: " + " | ".join(parts))
        else:
            self.lbl_mods.setText("Multipliers: none")
