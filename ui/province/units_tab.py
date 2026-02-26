# ui/province/units_tab.py
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QFrame, QLabel
from PySide6.QtCore import Qt

from ui.selection_panel import SelectionPanel
from ui.province.combat_preview import CombatPreviewWidget


class ProvinceUnitsTabWidget(QWidget):
    """
    Aba "Units" dentro do ProvinceDetailPanel.

    Reuso de código:
      - Embute um SelectionPanel e chama update_from_selection(controller)
        (mesma fonte de verdade do painel lateral).
      - Mantém CombatPreviewWidget abaixo.
    """

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        # --- Embedded SelectionPanel (reuso) ---
        self.selection_embed = SelectionPanel(controller=self.controller, parent=self)

        # “Modo embed”: esconder header/back/go-to e hints do fim, para não ficar duplicado na UI
        # (sem refatorar SelectionPanel inteiro)
        self._apply_embed_mode()

        layout.addWidget(self.selection_embed, 1)

        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #3a3a3a;")
        layout.addWidget(sep)

        # --- Combat preview (ferramenta existente) ---
        self.combat_preview = CombatPreviewWidget()
        layout.addWidget(self.combat_preview, 0)

        # Nota opcional (pode remover)
        note = QLabel("Tip: select a stack on the map to see its units here.")
        note.setStyleSheet("color: #666; font-size: 10px; font-style: italic;")
        note.setAlignment(Qt.AlignLeft)
        layout.addWidget(note)

    def _apply_embed_mode(self) -> None:
        """
        Ajustes visuais para o SelectionPanel funcionar como “sub-widget” da aba.
        """
        # Header do SelectionPanel: é o primeiro widget adicionado no layout principal dele.
        # Como não temos um handle direto do frame, a forma segura é esconder controles individuais.
        if hasattr(self.selection_embed, "btn_back"):
            self.selection_embed.btn_back.hide()
        if hasattr(self.selection_embed, "btn_go_to"):
            self.selection_embed.btn_go_to.hide()
        if hasattr(self.selection_embed, "title_label"):
            self.selection_embed.title_label.setText("🎖️ Selected Stack")

        # Hints: é um QFrame local não guardado como atributo.
        # Sem refatorar, não dá para esconder diretamente.
        # Solução: manter (não é o fim do mundo), ou refatorar SelectionPanel para salvar self.hints_frame.
        # Aqui vamos pelo caminho mínimo: deixa como está.

    def update_display(self) -> None:
        """
        Chamado pelo ProvinceDetailPanel.update_display/_load_province_data().
        Atualiza a parte “SelectionPanel” com base no estado real de seleção.
        """
        self.selection_embed.update_from_selection(self.controller)
        # CombatPreviewWidget é independente; não precisa atualizar aqui.
