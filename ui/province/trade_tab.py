# ui/province/trade_tab.py
"""
Aba de Comércio — Exibe vendas da produção local e recebimentos da província.
Contabilidade do produtor (onde a produção é vendida).

Hover em cada item de venda/recebimento aciona overlay 3D da rota via controller.
"""

from __future__ import annotations

import os
from typing import Optional, Sequence, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QScrollArea, QFrame, QSizePolicy,
    QGridLayout,
)
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QPixmap, QColor

from core.trade.facade import ProvinceTradeFacade, TradeRouteInfo
from core.civilization import Civilization

Tile = tuple[int, int]


# ============================================================
# HELPER: bandeira em miniatura
# ============================================================

def get_flag_pixmap(
    civ: Civilization, planet_id: str, size: tuple[int, int] = (24, 15)
) -> QPixmap | None:
    """Carrega a bandeira da civ ou gera um retângulo com a cor."""
    if not civ or not planet_id:
        return None

    flag_path = os.path.join("assets", "flags", str(planet_id), f"{civ.name}.png")
    if os.path.isfile(flag_path):
        px = QPixmap(flag_path)
        if not px.isNull():
            return px.scaled(
                size[0], size[1], Qt.KeepAspectRatio, Qt.SmoothTransformation
            )

    # Fallback: cor sólida
    r, g, b = civ.color
    px = QPixmap(size[0], size[1])
    px.fill(QColor(r, g, b))
    return px


# ============================================================
# WIDGET PRINCIPAL
# ============================================================

class TradeTabWidget(QWidget):
    """Widget para exibição de vendas e recebimentos da província."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.facade: ProvinceTradeFacade | None = None

        # Controla quem ativou o hover (evita limpar overlay ao mudar entre filhos)
        self._hover_owner: QWidget | None = None

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._init_ui()

    # ---- public API ----

    def set_facade(self, facade: ProvinceTradeFacade):
        """Recebe a facade do ProvinceDetailPanel."""
        self.facade = facade
        self.update_display()

    def update_display(self):
        """Ponto de entrada para atualizar os dados da aba."""
        if self.facade:
            self._load_data()
        else:
            self._show_empty()

    # ================================================================
    # HOVER → OVERLAY 3D (Event Filter)
    # ================================================================

    def _get_controller(self):
        """Obtém o controller navegando a árvore de widgets."""
        widget = self.parent()
        while widget is not None:
            if hasattr(widget, "controller"):
                return widget.controller
            widget = widget.parent() if hasattr(widget, "parent") else None
        return None

    def _attach_route_hover(
        self, widget: QWidget, path_tiles: Optional[Sequence[Tile]]
    ):
        """Associa um caminho ao widget e instala eventFilter para Enter/Leave."""
        if not widget:
            return

        widget.setAttribute(Qt.WA_Hover, True)
        widget.setMouseTracking(True)
        widget.setProperty(
            "_route_path_tiles", list(path_tiles) if path_tiles else None
        )
        widget.installEventFilter(self)

    def eventFilter(self, obj: Any, event: QEvent) -> bool:
        et = event.type()
        controller = self._get_controller()

        if et == QEvent.Enter:
            try:
                path = obj.property("_route_path_tiles")
            except Exception:
                path = None

            can_set = controller is not None and hasattr(
                controller, "set_hover_trade_route"
            )
            can_clear = controller is not None and hasattr(
                controller, "clear_hover_trade_route"
            )
            is_valid_path = isinstance(path, (list, tuple)) and len(path) >= 2

            if can_set and is_valid_path:
                self._hover_owner = obj
                controller.set_hover_trade_route(path)
            elif can_clear:
                self._hover_owner = obj
                controller.clear_hover_trade_route()

            return False

        if et == QEvent.Leave:
            if self._hover_owner is obj:
                self._hover_owner = None
                if controller and hasattr(controller, "clear_hover_trade_route"):
                    controller.clear_hover_trade_route()
            return False

        return super().eventFilter(obj, event)

    # ================================================================
    # UI CONSTRUCTION
    # ================================================================

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea { border: none; background-color: transparent; }
            QScrollBar:vertical { background-color: #2a2a2a; width: 10px; }
            QScrollBar::handle:vertical {
                background-color: #555; border-radius: 5px; min-height: 20px;
            }
        """)

        content_widget = QWidget()
        self.content_layout = QVBoxLayout(content_widget)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.content_layout.setSpacing(15)

        self._create_sales_section()
        self._create_receipts_section()
        self._create_summary_section()

        self.content_layout.addStretch()
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

    # ---- Styles ----

    @staticmethod
    def _group_style(color: str) -> str:
        return f"""
            QGroupBox {{
                font-weight: bold;
                border: 1px solid #3a3a3a;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #252525;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: {color};
            }}
        """

    @staticmethod
    def _subgroup_style() -> str:
        return """
            QGroupBox {
                font-weight: normal;
                border: 1px solid #2a2a2a;
                border-radius: 3px;
                margin-top: 8px;
                padding-top: 5px;
                background-color: #2a2a2a;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 3px;
                color: #aaa;
                font-size: 11px;
            }
        """

    # ---- Sales section ----

    def _create_sales_section(self):
        self.sales_group = QGroupBox("💰 Sales (Local Production)")
        self.sales_group.setStyleSheet(self._group_style("#4CAF50"))

        self.sales_layout = QVBoxLayout(self.sales_group)
        self.sales_layout.setContentsMargins(10, 15, 10, 10)
        self.sales_layout.setSpacing(8)

        # Subgrupo: Food
        self.sales_food_group = QGroupBox("🌾 Food")
        self.sales_food_group.setStyleSheet(self._subgroup_style())
        self.sales_food_layout = QVBoxLayout(self.sales_food_group)
        self.sales_food_layout.setContentsMargins(8, 12, 8, 8)
        self.sales_food_layout.setSpacing(4)

        self.sales_food_placeholder = QLabel("No food production")
        self.sales_food_placeholder.setStyleSheet(
            "color: #666; font-style: italic; font-size: 11px;"
        )
        self.sales_food_placeholder.setAlignment(Qt.AlignCenter)
        self.sales_food_layout.addWidget(self.sales_food_placeholder)

        self.sales_layout.addWidget(self.sales_food_group)

        # Subgrupo: Ore
        self.sales_ore_group = QGroupBox("⛏️ Ore")
        self.sales_ore_group.setStyleSheet(self._subgroup_style())
        self.sales_ore_layout = QVBoxLayout(self.sales_ore_group)
        self.sales_ore_layout.setContentsMargins(8, 12, 8, 8)
        self.sales_ore_layout.setSpacing(4)

        self.sales_ore_placeholder = QLabel("No ore production")
        self.sales_ore_placeholder.setStyleSheet(
            "color: #666; font-style: italic; font-size: 11px;"
        )
        self.sales_ore_placeholder.setAlignment(Qt.AlignCenter)
        self.sales_ore_layout.addWidget(self.sales_ore_placeholder)

        self.sales_layout.addWidget(self.sales_ore_group)

        self.content_layout.addWidget(self.sales_group)

    # ---- Receipts section ----

    def _create_receipts_section(self):
        self.receipts_group = QGroupBox("📦 Receipts (Local Consumption)")
        self.receipts_group.setStyleSheet(self._group_style("#64B5F6"))

        self.receipts_layout = QVBoxLayout(self.receipts_group)
        self.receipts_layout.setContentsMargins(10, 15, 10, 10)
        self.receipts_layout.setSpacing(8)

        # Subgrupo: Food
        self.receipts_food_group = QGroupBox("🌾 Food")
        self.receipts_food_group.setStyleSheet(self._subgroup_style())
        self.receipts_food_layout = QVBoxLayout(self.receipts_food_group)
        self.receipts_food_layout.setContentsMargins(8, 12, 8, 8)
        self.receipts_food_layout.setSpacing(4)

        self.receipts_food_placeholder = QLabel("No food received")
        self.receipts_food_placeholder.setStyleSheet(
            "color: #666; font-style: italic; font-size: 11px;"
        )
        self.receipts_food_placeholder.setAlignment(Qt.AlignCenter)
        self.receipts_food_layout.addWidget(self.receipts_food_placeholder)

        self.receipts_layout.addWidget(self.receipts_food_group)

        # Subgrupo: Ore
        self.receipts_ore_group = QGroupBox("⛏️ Ore")
        self.receipts_ore_group.setStyleSheet(self._subgroup_style())
        self.receipts_ore_layout = QVBoxLayout(self.receipts_ore_group)
        self.receipts_ore_layout.setContentsMargins(8, 12, 8, 8)
        self.receipts_ore_layout.setSpacing(4)

        self.receipts_ore_placeholder = QLabel("No ore received")
        self.receipts_ore_placeholder.setStyleSheet(
            "color: #666; font-style: italic; font-size: 11px;"
        )
        self.receipts_ore_placeholder.setAlignment(Qt.AlignCenter)
        self.receipts_ore_layout.addWidget(self.receipts_ore_placeholder)

        self.receipts_layout.addWidget(self.receipts_ore_group)

        self.content_layout.addWidget(self.receipts_group)

    # ---- Summary section ----

    def _create_summary_section(self):
        group = QGroupBox("📊 Summary")
        group.setStyleSheet(self._group_style("#9E9E9E"))

        layout = QGridLayout(group)
        layout.setContentsMargins(10, 15, 10, 10)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Food Sales:"), 0, 0)
        self.label_food_sales = QLabel("0.0")
        self.label_food_sales.setStyleSheet("color: #8BC34A; font-weight: bold;")
        self.label_food_sales.setAlignment(Qt.AlignRight)
        layout.addWidget(self.label_food_sales, 0, 1)

        layout.addWidget(QLabel("Ore Sales:"), 1, 0)
        self.label_ore_sales = QLabel("0.0")
        self.label_ore_sales.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self.label_ore_sales.setAlignment(Qt.AlignRight)
        layout.addWidget(self.label_ore_sales, 1, 1)

        layout.addWidget(QLabel("Total Sales:"), 2, 0)
        self.label_total_sales = QLabel("0.0")
        self.label_total_sales.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self.label_total_sales.setAlignment(Qt.AlignRight)
        layout.addWidget(self.label_total_sales, 2, 1)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("background-color: #3a3a3a;")
        layout.addWidget(separator, 3, 0, 1, 2)

        layout.addWidget(QLabel("Food Receipts:"), 4, 0)
        self.label_food_receipts = QLabel("0.0")
        self.label_food_receipts.setStyleSheet("color: #64B5F6; font-weight: bold;")
        self.label_food_receipts.setAlignment(Qt.AlignRight)
        layout.addWidget(self.label_food_receipts, 4, 1)

        layout.addWidget(QLabel("Ore Receipts:"), 5, 0)
        self.label_ore_receipts = QLabel("0.0")
        self.label_ore_receipts.setStyleSheet("color: #42A5F5; font-weight: bold;")
        self.label_ore_receipts.setAlignment(Qt.AlignRight)
        layout.addWidget(self.label_ore_receipts, 5, 1)

        layout.addWidget(QLabel("Total Receipts:"), 6, 0)
        self.label_total_receipts = QLabel("0.0")
        self.label_total_receipts.setStyleSheet("color: #64B5F6; font-weight: bold;")
        self.label_total_receipts.setAlignment(Qt.AlignRight)
        layout.addWidget(self.label_total_receipts, 6, 1)

        self.content_layout.addWidget(group)

    # ================================================================
    # ITEM WIDGETS
    # ================================================================

    def _create_sale_widget(
        self,
        route: TradeRouteInfo,
        is_local: bool,
        planet_id: str,
    ) -> QFrame:
        """Cria widget para exibir uma venda (destino, quantidade, hops, bandeira)."""
        frame = QFrame()

        bg_color = "#2d3a2d" if is_local else "#333"
        border_color = "#3a4a3a" if is_local else "#444"

        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 4px;
            }}
            QFrame:hover {{
                border-color: #555;
                background-color: #3a3a3a;
            }}
        """)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(8)

        # Bandeira da civilização destino
        flag_pixmap = get_flag_pixmap(route.partner_civ, planet_id, size=(24, 15))
        if flag_pixmap:
            flag_label = QLabel()
            flag_label.setPixmap(flag_pixmap)
            flag_label.setFixedSize(24, 15)
            flag_label.setStyleSheet(
                "border: 1px solid #555; border-radius: 2px;"
            )
            layout.addWidget(flag_label)

        # Nome da civ destino
        destino_text = route.partner_civ.name
        if is_local:
            destino_text += " (local)"
        label_destino = QLabel(f"→ {destino_text}")
        label_destino.setStyleSheet("color: #ddd;")
        layout.addWidget(label_destino)

        layout.addStretch()

        # Distância em hops
        if route.path and len(route.path) > 1:
            hops = len(route.path) - 1
            label_dist = QLabel(f"📍{hops}")
            label_dist.setStyleSheet("color: #666; font-size: 10px;")
            layout.addWidget(label_dist)

        # Quantidade
        label_qty = QLabel(f"{route.quantity:.1f}")
        label_qty.setStyleSheet("color: #4CAF50; font-weight: bold;")
        layout.addWidget(label_qty)

        # Hover → rota 3D
        self._attach_route_hover(frame, route.path)

        return frame

    def _create_receipt_widget(
        self,
        route: TradeRouteInfo,
        is_local: bool,
        planet_id: str,
    ) -> QFrame:
        """Cria widget para exibir um recebimento (origem, recurso, quantidade, hops, bandeira)."""
        frame = QFrame()

        bg_color = "#2d2d3a" if is_local else "#333"
        border_color = "#3a3a4a" if is_local else "#444"

        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 4px;
            }}
            QFrame:hover {{
                border-color: #555;
                background-color: #3a3a3a;
            }}
        """)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(8)

        # Bandeira da civilização origem
        flag_pixmap = get_flag_pixmap(route.partner_civ, planet_id, size=(24, 15))
        if flag_pixmap:
            flag_label = QLabel()
            flag_label.setPixmap(flag_pixmap)
            flag_label.setFixedSize(24, 15)
            flag_label.setStyleSheet(
                "border: 1px solid #555; border-radius: 2px;"
            )
            layout.addWidget(flag_label)

        # Nome da civ origem
        origem_text = route.partner_civ.name
        if is_local:
            origem_text += " (local)"
        label_origem = QLabel(f"← {origem_text}")
        label_origem.setStyleSheet("color: #ddd;")
        layout.addWidget(label_origem)

        # Nome do recurso
        label_produto = QLabel(f"[{route.resource_name}]")
        label_produto.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(label_produto)

        layout.addStretch()

        # Distância em hops
        if route.path and len(route.path) > 1:
            hops = len(route.path) - 1
            label_dist = QLabel(f"📍{hops}")
            label_dist.setStyleSheet("color: #666; font-size: 10px;")
            layout.addWidget(label_dist)

        # Quantidade
        label_qty = QLabel(f"{route.quantity:.1f}")
        label_qty.setStyleSheet("color: #64B5F6; font-weight: bold;")
        layout.addWidget(label_qty)

        # Hover → rota 3D
        self._attach_route_hover(frame, route.path)

        return frame

    # ================================================================
    # DATA LOADING
    # ================================================================

    def _clear_layout_keep_placeholder(self, layout):
        """Remove todos os widgets exceto o placeholder (índice 0)."""
        while layout.count() > 1:
            item = layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

    def _classify_route(self, route: TradeRouteInfo) -> str:
        """
        Classifica uma rota como 'food' ou 'ore' comparando
        o resource_name com o food_type da província no econ_repo.
        """
        if not self.facade:
            return "food"

        econ = self.facade.planet.econ_repo.get(self.facade.tile)
        if not econ:
            return "food"

        # Se o nome do recurso bate com o food_type desta província, é food.
        # Se bate com o ore_type, é ore.
        # Para recebimentos (imports), o recurso pode ser de OUTRA província,
        # então comparamos com os food_types e ore_types globais.
        if econ.food_type and route.resource_name == econ.food_type:
            return "food"
        if econ.ore_type and route.resource_name == econ.ore_type:
            return "ore"

        # Fallback: verificar se o recurso existe como food_type de alguma província
        for state in self.facade.planet.econ_repo.all():
            if state.food_type == route.resource_name:
                return "food"
            if state.ore_type == route.resource_name:
                return "ore"

        return "food"  # default

    def _load_data(self):
        """Carrega dados de comércio via ProvinceTradeFacade e popula a UI."""
        if not self.facade:
            return

        planet = self.facade.planet
        tile = self.facade.tile
        planet_id = planet.id

        # Atualizar títulos dos subgrupos com nomes dos recursos locais
        econ = planet.econ_repo.get(tile)
        if econ:
            food_name = econ.food_type or "Food"
            ore_name = econ.ore_type or "Ore"
            self.sales_food_group.setTitle(f"🌾 {food_name}")
            self.sales_ore_group.setTitle(f"⛏️ {ore_name}")

        # Obter todas as rotas via facade
        all_routes = self.facade.get_trade_routes()

        # Separar vendas e recebimentos
        sales = [r for r in all_routes if r.is_sale]
        receipts = [r for r in all_routes if not r.is_sale]

        # Classificar por tipo de recurso (food vs ore)
        sales_food = [r for r in sales if self._classify_route(r) == "food"]
        sales_ore = [r for r in sales if self._classify_route(r) == "ore"]
        receipts_food = [r for r in receipts if self._classify_route(r) == "food"]
        receipts_ore = [r for r in receipts if self._classify_route(r) == "ore"]

        # Limpar layouts (mantendo placeholder no índice 0)
        self._clear_layout_keep_placeholder(self.sales_food_layout)
        self._clear_layout_keep_placeholder(self.sales_ore_layout)
        self._clear_layout_keep_placeholder(self.receipts_food_layout)
        self._clear_layout_keep_placeholder(self.receipts_ore_layout)

        # ========== Vendas — Food ==========
        if sales_food:
            self.sales_food_placeholder.hide()
            for route in sorted(sales_food, key=lambda r: -r.quantity):
                is_local = self._is_local_trade(route)
                widget = self._create_sale_widget(route, is_local, planet_id)
                self.sales_food_layout.addWidget(widget)
        else:
            self.sales_food_placeholder.show()

        # ========== Vendas — Ore ==========
        if sales_ore:
            self.sales_ore_placeholder.hide()
            for route in sorted(sales_ore, key=lambda r: -r.quantity):
                is_local = self._is_local_trade(route)
                widget = self._create_sale_widget(route, is_local, planet_id)
                self.sales_ore_layout.addWidget(widget)
        else:
            self.sales_ore_placeholder.show()

        # ========== Recebimentos — Food ==========
        if receipts_food:
            self.receipts_food_placeholder.hide()
            for route in sorted(receipts_food, key=lambda r: -r.quantity):
                is_local = self._is_local_trade(route)
                widget = self._create_receipt_widget(route, is_local, planet_id)
                self.receipts_food_layout.addWidget(widget)
        else:
            self.receipts_food_placeholder.show()

        # ========== Recebimentos — Ore ==========
        if receipts_ore:
            self.receipts_ore_placeholder.hide()
            for route in sorted(receipts_ore, key=lambda r: -r.quantity):
                is_local = self._is_local_trade(route)
                widget = self._create_receipt_widget(route, is_local, planet_id)
                self.receipts_ore_layout.addWidget(widget)
        else:
            self.receipts_ore_placeholder.show()

        # Atualizar resumo
        self._update_summary(sales_food, sales_ore, receipts_food, receipts_ore)

    def _is_local_trade(self, route: TradeRouteInfo) -> bool:
        """Verifica se a rota é comércio local (parceiro está no mesmo tile)."""
        if not self.facade:
            return False

        tile = self.facade.tile
        owner = self.facade.owner

        # Comércio local = o parceiro é a mesma civilização dona da província
        if owner and route.partner_civ and route.partner_civ.id == owner.id:
            # Verifica se o path é trivial (mesmo tile ou adjacente via capital)
            if route.path and len(route.path) <= 1:
                return True
            # Ou se a província parceira está no mesmo tile
            for prov in route.partner_civ.provinces:
                if prov.tile_coords == tile:
                    return True

        return False

    def _update_summary(
        self,
        sales_food: list[TradeRouteInfo],
        sales_ore: list[TradeRouteInfo],
        receipts_food: list[TradeRouteInfo],
        receipts_ore: list[TradeRouteInfo],
    ):
        """Atualiza o resumo com totais."""
        total_food_sales = sum(r.quantity for r in sales_food)
        total_ore_sales = sum(r.quantity for r in sales_ore)
        total_sales = total_food_sales + total_ore_sales

        total_food_receipts = sum(r.quantity for r in receipts_food)
        total_ore_receipts = sum(r.quantity for r in receipts_ore)
        total_receipts = total_food_receipts + total_ore_receipts

        self.label_food_sales.setText(f"{total_food_sales:.1f}")
        self.label_ore_sales.setText(f"{total_ore_sales:.1f}")
        self.label_total_sales.setText(f"{total_sales:.1f}")

        self.label_food_receipts.setText(f"{total_food_receipts:.1f}")
        self.label_ore_receipts.setText(f"{total_ore_receipts:.1f}")
        self.label_total_receipts.setText(f"{total_receipts:.1f}")

    # ================================================================
    # EMPTY STATE
    # ================================================================

    def _show_empty(self):
        """Reseta a UI para estado vazio."""
        self._clear_layout_keep_placeholder(self.sales_food_layout)
        self._clear_layout_keep_placeholder(self.sales_ore_layout)
        self._clear_layout_keep_placeholder(self.receipts_food_layout)
        self._clear_layout_keep_placeholder(self.receipts_ore_layout)

        self.sales_food_placeholder.show()
        self.sales_ore_placeholder.show()
        self.receipts_food_placeholder.show()
        self.receipts_ore_placeholder.show()

        self.sales_food_group.setTitle("🌾 Food")
        self.sales_ore_group.setTitle("⛏️ Ore")

        self.label_food_sales.setText("0.0")
        self.label_ore_sales.setText("0.0")
        self.label_total_sales.setText("0.0")
        self.label_food_receipts.setText("0.0")
        self.label_ore_receipts.setText("0.0")
        self.label_total_receipts.setText("0.0")
