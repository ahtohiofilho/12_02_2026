# ui/province/workforce_tab.py
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QSlider,
    QProgressBar, QSizePolicy, QGridLayout, QPushButton,
    QScrollArea, QListWidget, QListWidgetItem, QAbstractItemView, QFrame,
    QCheckBox
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor

from core.production.queue import QueueItemType
from ui.province.military_ui import UNIT_ICONS, UNIT_COLORS


class WorkforceTabWidget(QWidget):
    """
    Aba Workforce com adaptação por bioma.

    Comportamento por tipo de tile:
      - Sem produção (Ocean/Ice): exibe mensagem informativa, desabilita controles
      - Apenas food: slider fixo em 100% food, desabilitado
      - Apenas ore: slider fixo em 100% ore, desabilitado
      - Ambos: controles completos (slider, barras, split visual)

    Depende de ProvinceWorkforceFacade (não conhece Planet/Province diretamente).
    """

    allocation_changed = Signal(float, float)  # food_pct, ore_pct
    queue_changed = Signal()

    def __init__(self, controller, parent=None):
        super().__init__(parent)

        self.facade = None
        self.controller = controller

        # debounce do slider
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(200)
        self._update_timer.timeout.connect(self._apply_allocation_change)

        self._pending_value: int | None = None
        self._allocation_preference_pct: int = 50

        # Estado de produção do bioma (atualizado em set_facade)
        self._has_food = False
        self._has_ore = False

        # --- Civ revenue total (baseline + delta) ---
        self._baseline_civ_revenue_total: float | None = None

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._init_ui()

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def set_facade(self, facade) -> None:
        self.facade = facade

        if self.facade:
            self._has_food = self.facade.has_food_production()
            self._has_ore = self.facade.has_ore_production()
            self._allocation_preference_pct = int(round(self.facade.get_food_pref() * 100.0))
        else:
            self._has_food = False
            self._has_ore = False

        self._update_biome_adaptation()

        # ✅ aplica/mostra estado do governor (auto ON por default)
        self._sync_auto_controls_from_state(apply_optimize=True)

        # Baseline da sessão (ao entrar/selecionar província)
        self._baseline_civ_revenue_total = self._calc_civ_total_revenue()

        self.update_display()

    def _sync_auto_controls_from_state(self, *, apply_optimize: bool) -> None:
        if not self.facade:
            return

        has_both = bool(self._has_food) and bool(self._has_ore)

        auto = bool(self.facade.get_auto_max_revenue()) if hasattr(self.facade, "get_auto_max_revenue") else True

        if hasattr(self, "chk_auto_max"):
            self.chk_auto_max.blockSignals(True)
            self.chk_auto_max.setChecked(auto)
            self.chk_auto_max.blockSignals(False)
            self.chk_auto_max.setEnabled(has_both)

        if hasattr(self, "btn_optimize_now"):
            self.btn_optimize_now.setEnabled(has_both)

        # slider só faz sentido quando há ambos e auto está OFF
        self.slider_allocation.setEnabled(has_both and (not auto))

        if auto and has_both and apply_optimize:
            self._optimize_allocation_max_revenue()


    def _calc_civ_total_revenue(self) -> float:
        if not self.facade:
            return 0.0

        civ = getattr(self.controller, "controlled_civ", None)
        if civ is None:
            return 0.0

        planet = self.facade.planet
        r = planet.economy.calcular_equilibrio()

        return float(sum(float(r.get_receita_total(p.tile_coords) or 0.0) for p in civ.provinces))

    def _refresh_civ_total_revenue_labels(self) -> None:
        # labels só existem depois do _init_ui/_create_revenue_section
        if not hasattr(self, "label_civ_total_revenue"):
            return

        total = self._calc_civ_total_revenue()
        self.label_civ_total_revenue.setText(f"${total:.2f}")

        if self._baseline_civ_revenue_total is None:
            self.label_civ_total_revenue_delta.setText("")
            self.label_civ_total_revenue_delta.setStyleSheet("color: #888; font-style: italic;")
            return

        delta = total - float(self._baseline_civ_revenue_total)
        if abs(delta) < 1e-6:
            self.label_civ_total_revenue_delta.setText("(+0.00)")
            self.label_civ_total_revenue_delta.setStyleSheet("color: #9e9e9e; font-style: italic;")
        elif delta > 0:
            self.label_civ_total_revenue_delta.setText(f"(+{delta:.2f})")
            self.label_civ_total_revenue_delta.setStyleSheet("color: #4CAF50; font-style: italic;")
        else:
            self.label_civ_total_revenue_delta.setText(f"({delta:.2f})")  # delta já é negativo
            self.label_civ_total_revenue_delta.setStyleSheet("color: #F44336; font-style: italic;")

    def update_display(self) -> None:
        if not self.facade:
            self._set_empty_state()
            return

        # ---- Resource names ----
        food_name, ore_name = self.facade.resource_names()
        self.label_food_name.setText(f"🌾 {food_name}:")
        self.label_ore_name.setText(f"⛏️ {ore_name}:")
        self.label_food_revenue_name.setText("🌾 Food:")
        self.label_ore_revenue_name.setText("⛏️ Ore:")

        # ---- Hiring ----
        info = self.facade.worker_info()
        self.label_workers_current.setText(f"Current: {info.current} workers")
        self.label_worker_cost.setText(f"Next worker: {info.next_cost:.1f}G (paid over turns)")
        self.btn_buy_worker.setEnabled(True)

        # ── Botão Detach: habilitado apenas se pode destacar ──
        can_detach = self.facade.can_detach_worker()
        self.btn_detach_worker.setEnabled(can_detach)
        if not can_detach:
            self.label_detach_status.setText("⚠ Minimum 1 worker must remain.")
            self.label_detach_status.setStyleSheet(
                "color: #888; font-size: 11px; font-style: italic;"
            )
        else:
            # Só limpa a mensagem de aviso; preserva mensagens de feedback (✅/❌)
            if self.label_detach_status.text().startswith("⚠"):
                self.label_detach_status.setText("")

        # ---- Allocation UI (consistent with core ints) ----
        has_food = bool(self._has_food)
        has_ore = bool(self._has_ore)
        has_both = has_food and has_ore

        if has_both:
            pref_pct = int(self._allocation_preference_pct)
            self.slider_allocation.blockSignals(True)
            self.slider_allocation.setValue(pref_pct)
            self.slider_allocation.blockSignals(False)
            self.progress_food.setValue(pref_pct)
            self.progress_ore.setValue(100 - pref_pct)
        elif has_food:
            self.progress_food.setValue(100)
            self.progress_ore.setValue(0)
        elif has_ore:
            self.progress_food.setValue(0)
            self.progress_ore.setValue(100)

        # Sempre usa valores reais do core (evita divergência com split_workers)
        self.label_farmers.setText(f"{food_name}: {info.workers_food}")
        self.label_miners.setText(f"{ore_name}: {info.workers_ore}")

        # ---- Output ----
        food_out, ore_out = self.facade.outputs()
        self.label_food_output.setText(f"{food_out:.1f}")
        self.label_ore_output.setText(f"{ore_out:.1f}")
        self.label_total_output.setText(f"{(food_out + ore_out):.1f}")

        # ---- Revenue ----
        total_rev = self.facade.revenue_total()
        self.label_food_revenue.setText("—")
        self.label_ore_revenue.setText("—")
        self.label_total_revenue.setText(f"${total_rev:.2f}")

        # ---- Hire status: limpa quando fila esvaziar ----
        queue_items = self.facade.queue_items()
        has_worker_in_queue = any(
            it.item_type == QueueItemType.WORKER for it in queue_items
        )
        if not has_worker_in_queue:
            self.label_hire_status.setText("")

        # ---- Queue ----
        self._update_queue_display()

        self._refresh_civ_total_revenue_labels()

    # ------------------------------------------------------------------ #
    #  Biome adaptation                                                    #
    # ------------------------------------------------------------------ #

    def _update_biome_adaptation(self) -> None:
        """Mostra/esconde seções conforme o tipo de produção do tile."""
        has_any = self._has_food or self._has_ore
        has_both = self._has_food and self._has_ore

        self.no_production_label.setVisible(not has_any)

        self.single_production_label.setVisible(has_any and not has_both)
        if self._has_food and not self._has_ore:
            food_name = "Food"
            if self.facade:
                food_name, _ = self.facade.resource_names()
            self.single_production_label.setText(
                f"🌾 All workers are assigned to {food_name} production.\n"
                f"No ore resources available in this biome."
            )
            self.single_production_label.setStyleSheet(
                "color: #4CAF50; font-style: italic; padding: 10px;"
            )
        elif self._has_ore and not self._has_food:
            ore_name = "Ore"
            if self.facade:
                _, ore_name = self.facade.resource_names()
            self.single_production_label.setText(
                f"⛏️ All workers are assigned to {ore_name} production.\n"
                f"No food resources available in this biome."
            )
            self.single_production_label.setStyleSheet(
                "color: #FF9800; font-style: italic; padding: 10px;"
            )

        self.slider_allocation.setVisible(has_both)
        self.label_food_icon.setVisible(has_both)
        self.label_ore_icon.setVisible(has_both)

        self.progress_food.setVisible(has_any)
        self.progress_ore.setVisible(has_any)
        self.label_farmers.setVisible(has_any)
        self.label_miners.setVisible(has_any)

        self.group_hiring.setVisible(has_any)
        self.group_queue.setVisible(has_any)
        self.group_allocation.setVisible(has_any)
        self.group_output.setVisible(has_any)
        self.group_revenue.setVisible(has_any)

        # Controles de automação só fazem sentido quando há os dois recursos
        if hasattr(self, "chk_auto_max"):
            self.chk_auto_max.setVisible(has_both)
        if hasattr(self, "btn_optimize_now"):
            self.btn_optimize_now.setVisible(has_both)

    def _set_empty_state(self) -> None:
        self.btn_buy_worker.setEnabled(False)
        self.btn_detach_worker.setEnabled(False)
        self.label_detach_status.setText("")
        self.queue_list.clear()
        self.label_queue_count.setText("Empty queue")
        self.label_queue_cost.setText("Remaining: 0.0G")
        self.label_queue_status.setText("")
        self.label_workers_current.setText("Current: —")
        self.label_worker_cost.setText("Next worker: —")
        self.label_farmers.setText("Food: —")
        self.label_miners.setText("Ore: —")
        self.label_food_output.setText("0.0")
        self.label_ore_output.setText("0.0")
        self.label_total_output.setText("0.0")
        self.label_food_revenue.setText("—")
        self.label_ore_revenue.setText("—")
        self.label_total_revenue.setText("$0.00")

    # ------------------------------------------------------------------ #
    #  UI building                                                         #
    # ------------------------------------------------------------------ #

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(10)

        # Bioma sem produção
        self.no_production_label = QLabel(
            "⛰️ This biome has no economic production.\n"
            "It can still be used for strategic or settlement purposes."
        )
        self.no_production_label.setAlignment(Qt.AlignCenter)
        self.no_production_label.setStyleSheet(
            "color: #888; font-style: italic; padding: 20px;"
        )
        self.no_production_label.setWordWrap(True)
        self.no_production_label.setVisible(False)
        scroll_layout.addWidget(self.no_production_label)

        # Produção única (só food ou só ore)
        self.single_production_label = QLabel("")
        self.single_production_label.setAlignment(Qt.AlignCenter)
        self.single_production_label.setWordWrap(True)
        self.single_production_label.setVisible(False)
        scroll_layout.addWidget(self.single_production_label)

        # Seções
        self.group_hiring = self._create_hiring_section()
        scroll_layout.addWidget(self.group_hiring)

        self.group_queue = self._create_queue_section()
        scroll_layout.addWidget(self.group_queue)

        self.group_allocation = self._create_allocation_section()
        scroll_layout.addWidget(self.group_allocation)

        self.group_output = self._create_output_section()
        scroll_layout.addWidget(self.group_output)

        self.group_revenue = self._create_revenue_section()
        scroll_layout.addWidget(self.group_revenue)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

    def _group_style(self, color: str) -> str:
        return f"""
            QGroupBox {{
                font-weight: bold;
                border: 1px solid #3a3a3a;
                border-radius: 5px;
                margin-top: 8px;
                padding-top: 8px;
                background-color: #252525;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: {color};
            }}
        """

    def _create_hiring_section(self) -> QGroupBox:
        group = QGroupBox("👷 Workers")
        group.setStyleSheet(self._group_style("#64B5F6"))
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 15, 10, 10)
        layout.setSpacing(8)

        # ── Linha: workers atuais + custo do próximo ──
        info_layout = QHBoxLayout()
        self.label_workers_current = QLabel("Current: —")
        self.label_workers_current.setStyleSheet("color: #ddd; font-weight: bold;")
        info_layout.addWidget(self.label_workers_current)
        info_layout.addStretch()
        self.label_worker_cost = QLabel("Next worker: —")
        self.label_worker_cost.setStyleSheet("color: #FFD700;")
        info_layout.addWidget(self.label_worker_cost)
        layout.addLayout(info_layout)

        # ── Linha: status + botão comprar ──
        buy_layout = QHBoxLayout()
        self.label_hire_status = QLabel("")
        self.label_hire_status.setStyleSheet("color: #888; font-size: 11px;")
        buy_layout.addWidget(self.label_hire_status, 1)

        self.btn_buy_worker = QPushButton("Buy Worker")
        self.btn_buy_worker.setFixedWidth(140)
        self.btn_buy_worker.clicked.connect(self._on_buy_worker)
        self.btn_buy_worker.setStyleSheet("""
            QPushButton { background-color: #1565C0; border: none; border-radius: 4px;
                         padding: 8px 12px; color: white; font-weight: bold; }
            QPushButton:hover { background-color: #1976D2; }
            QPushButton:pressed { background-color: #0D47A1; }
            QPushButton:disabled { background-color: #333; color: #666; }
        """)
        buy_layout.addWidget(self.btn_buy_worker)
        layout.addLayout(buy_layout)

        # ── Separador visual ──
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #3a3a3a; margin: 4px 0;")
        layout.addWidget(sep)

        # ── Linha: descrição + botão destacar ──
        detach_layout = QHBoxLayout()

        detach_info = QLabel("Detach a worker → mobile unit on the map")
        detach_info.setStyleSheet("color: #aaa; font-size: 11px; font-style: italic;")
        detach_info.setWordWrap(True)
        detach_layout.addWidget(detach_info, 1)

        self.btn_detach_worker = QPushButton("⚒ Detach")
        self.btn_detach_worker.setFixedWidth(100)
        self.btn_detach_worker.setToolTip(
            "Remove 1 worker from this province and\n"
            "create a mobile Worker unit on the map.\n"
            "Minimum 1 worker must remain."
        )
        self.btn_detach_worker.clicked.connect(self._on_detach_worker)
        self.btn_detach_worker.setStyleSheet("""
            QPushButton { background-color: #4E342E; border: none; border-radius: 4px;
                         padding: 8px 12px; color: white; font-weight: bold; }
            QPushButton:hover { background-color: #6D4C41; }
            QPushButton:pressed { background-color: #3E2723; }
            QPushButton:disabled { background-color: #333; color: #666; }
        """)
        detach_layout.addWidget(self.btn_detach_worker)
        layout.addLayout(detach_layout)

        # ── Status do destacamento ──
        self.label_detach_status = QLabel("")
        self.label_detach_status.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self.label_detach_status)

        return group

    def _create_queue_section(self) -> QGroupBox:
        group = QGroupBox("📋 Production Queue")
        group.setStyleSheet(self._group_style("#FF9800"))
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 15, 10, 10)
        layout.setSpacing(8)

        header_layout = QHBoxLayout()
        self.label_queue_count = QLabel("Empty queue")
        self.label_queue_count.setStyleSheet("color: #aaa;")
        header_layout.addWidget(self.label_queue_count)
        header_layout.addStretch()
        self.label_queue_cost = QLabel("Remaining: 0.0G")
        self.label_queue_cost.setStyleSheet("color: #FFD700; font-weight: bold;")
        header_layout.addWidget(self.label_queue_cost)
        layout.addLayout(header_layout)

        self.queue_list = QListWidget()
        self.queue_list.setMaximumHeight(140)
        self.queue_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.queue_list.setStyleSheet("""
            QListWidget { background-color: #1e1e1e; border: 1px solid #3a3a3a;
                          border-radius: 4px; padding: 2px; }
            QListWidget::item { padding: 4px 8px; border-bottom: 1px solid #2a2a2a; color: #ddd; }
            QListWidget::item:selected { background-color: #3a4a5a; border: none; }
            QListWidget::item:hover { background-color: #2a3a4a; }
        """)
        layout.addWidget(self.queue_list)

        btn_layout = QHBoxLayout()
        self.label_queue_status = QLabel("")
        self.label_queue_status.setStyleSheet("color: #666; font-size: 10px;")
        btn_layout.addWidget(self.label_queue_status, 1)

        self.btn_remove_selected = QPushButton("Remove")
        self.btn_remove_selected.setFixedWidth(70)
        self.btn_remove_selected.clicked.connect(self._on_remove_selected)
        self.btn_remove_selected.setEnabled(False)
        self.btn_remove_selected.setStyleSheet("""
            QPushButton { background-color: #5D4037; border: none; border-radius: 3px;
                         padding: 5px 10px; color: #ddd; font-size: 11px; }
            QPushButton:hover { background-color: #6D4C41; }
            QPushButton:disabled { background-color: #333; color: #555; }
        """)
        btn_layout.addWidget(self.btn_remove_selected)

        self.btn_clear_queue = QPushButton("Clear All")
        self.btn_clear_queue.setFixedWidth(70)
        self.btn_clear_queue.clicked.connect(self._on_clear_queue)
        self.btn_clear_queue.setEnabled(False)
        self.btn_clear_queue.setStyleSheet("""
            QPushButton { background-color: #B71C1C; border: none; border-radius: 3px;
                         padding: 5px 10px; color: #ddd; font-size: 11px; }
            QPushButton:hover { background-color: #C62828; }
            QPushButton:disabled { background-color: #333; color: #555; }
        """)
        btn_layout.addWidget(self.btn_clear_queue)
        layout.addLayout(btn_layout)

        self.queue_list.itemSelectionChanged.connect(self._on_queue_selection_changed)

        hint = QLabel("💡 Queue is per-province. Processing integrates with turns.")
        hint.setStyleSheet("color: #555; font-size: 9px; font-style: italic;")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return group

    def _create_allocation_section(self) -> QGroupBox:
        group = QGroupBox("📊 Worker Allocation")
        group.setStyleSheet(self._group_style("#81C784"))
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 15, 10, 10)
        layout.setSpacing(8)

        # --- Auto optimize row ---
        auto_row = QHBoxLayout()

        self.chk_auto_max = QCheckBox("Auto (Max $)")
        self.chk_auto_max.setToolTip("Automatically sets allocation to maximize revenue for this province.")
        self.chk_auto_max.toggled.connect(self._on_auto_toggled)
        auto_row.addWidget(self.chk_auto_max)

        auto_row.addStretch()

        self.btn_optimize_now = QPushButton("Optimize now")
        self.btn_optimize_now.setFixedWidth(120)
        self.btn_optimize_now.clicked.connect(self._optimize_now_clicked)
        self.btn_optimize_now.setStyleSheet("""
            QPushButton { background-color: #2E7D32; border: none; border-radius: 4px;
                         padding: 6px 10px; color: white; font-weight: bold; }
            QPushButton:hover { background-color: #388E3C; }
            QPushButton:pressed { background-color: #1B5E20; }
            QPushButton:disabled { background-color: #333; color: #666; }
        """)
        auto_row.addWidget(self.btn_optimize_now)

        layout.addLayout(auto_row)

        slider_layout = QHBoxLayout()
        self.label_food_icon = QLabel("🌾")
        self.label_food_icon.setFont(QFont("Segoe UI", 14))
        slider_layout.addWidget(self.label_food_icon)

        self.slider_allocation = QSlider(Qt.Horizontal)
        self.slider_allocation.setRange(0, 100)
        self.slider_allocation.setValue(50)
        self.slider_allocation.setTickPosition(QSlider.TicksBelow)
        self.slider_allocation.setTickInterval(10)
        self.slider_allocation.valueChanged.connect(self._on_slider_changed)
        self.slider_allocation.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px;
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4CAF50, stop:1 #FF9800
                );
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #fff;
                border: 2px solid #888;
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover { border-color: #4CAF50; }
        """)
        slider_layout.addWidget(self.slider_allocation)

        self.label_ore_icon = QLabel("⛏️")
        self.label_ore_icon.setFont(QFont("Segoe UI", 14))
        slider_layout.addWidget(self.label_ore_icon)
        layout.addLayout(slider_layout)

        workers_layout = QHBoxLayout()
        self.label_farmers = QLabel("Food: —")
        self.label_farmers.setStyleSheet("color: #4CAF50; font-weight: bold;")
        workers_layout.addWidget(self.label_farmers)
        workers_layout.addStretch()
        self.label_miners = QLabel("Ore: —")
        self.label_miners.setStyleSheet("color: #FF9800; font-weight: bold;")
        workers_layout.addWidget(self.label_miners)
        layout.addLayout(workers_layout)

        bars_layout = QHBoxLayout()
        bars_layout.setSpacing(4)

        self.progress_food = QProgressBar()
        self.progress_food.setFormat("%p%")
        self.progress_food.setFixedHeight(16)
        self.progress_food.setStyleSheet("""
            QProgressBar { border: 1px solid #3a3a3a; border-radius: 3px;
                           text-align: center; font-size: 10px; }
            QProgressBar::chunk { background-color: #4CAF50; }
        """)
        bars_layout.addWidget(self.progress_food)

        self.progress_ore = QProgressBar()
        self.progress_ore.setFormat("%p%")
        self.progress_ore.setFixedHeight(16)
        self.progress_ore.setStyleSheet("""
            QProgressBar { border: 1px solid #3a3a3a; border-radius: 3px;
                           text-align: center; font-size: 10px; }
            QProgressBar::chunk { background-color: #FF9800; }
        """)
        bars_layout.addWidget(self.progress_ore)

        layout.addLayout(bars_layout)
        return group

    def _create_output_section(self) -> QGroupBox:
        group = QGroupBox("📦 Output")
        group.setStyleSheet(self._group_style("#FFB74D"))
        layout = QGridLayout(group)
        layout.setContentsMargins(10, 15, 10, 10)
        layout.setSpacing(6)

        self.label_food_name = QLabel("🌾 Food:")
        layout.addWidget(self.label_food_name, 0, 0)
        self.label_food_output = QLabel("0.0")
        self.label_food_output.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self.label_food_output.setAlignment(Qt.AlignRight)
        layout.addWidget(self.label_food_output, 0, 1)

        self.label_ore_name = QLabel("⛏️ Ore:")
        layout.addWidget(self.label_ore_name, 1, 0)
        self.label_ore_output = QLabel("0.0")
        self.label_ore_output.setStyleSheet("color: #FF9800; font-weight: bold;")
        self.label_ore_output.setAlignment(Qt.AlignRight)
        layout.addWidget(self.label_ore_output, 1, 1)

        layout.addWidget(QLabel("Total:"), 2, 0)
        self.label_total_output = QLabel("0.0")
        self.label_total_output.setStyleSheet("font-weight: bold;")
        self.label_total_output.setAlignment(Qt.AlignRight)
        layout.addWidget(self.label_total_output, 2, 1)
        return group

    def _create_revenue_section(self) -> QGroupBox:
        group = QGroupBox("💰 Revenue (Total)")
        group.setStyleSheet(self._group_style("#FFD700"))
        layout = QGridLayout(group)
        layout.setContentsMargins(10, 15, 10, 10)
        layout.setSpacing(6)

        # ---- Per-province revenue ----
        self.label_food_revenue_name = QLabel("🌾 Food:")
        layout.addWidget(self.label_food_revenue_name, 0, 0)
        self.label_food_revenue = QLabel("—")
        self.label_food_revenue.setStyleSheet("color: #666;")
        self.label_food_revenue.setAlignment(Qt.AlignRight)
        layout.addWidget(self.label_food_revenue, 0, 1)

        self.label_ore_revenue_name = QLabel("⛏️ Ore:")
        layout.addWidget(self.label_ore_revenue_name, 1, 0)
        self.label_ore_revenue = QLabel("—")
        self.label_ore_revenue.setStyleSheet("color: #666;")
        self.label_ore_revenue.setAlignment(Qt.AlignRight)
        layout.addWidget(self.label_ore_revenue, 1, 1)

        layout.addWidget(QLabel("Total:"), 2, 0)
        self.label_total_revenue = QLabel("$0.00")
        self.label_total_revenue.setStyleSheet("color: #FFD700; font-weight: bold;")
        self.label_total_revenue.setAlignment(Qt.AlignRight)
        layout.addWidget(self.label_total_revenue, 2, 1)

        note = QLabel("Uses MarketSystem total revenue for this tile.")
        note.setStyleSheet("color: #666; font-size: 9px; font-style: italic;")
        note.setWordWrap(True)
        layout.addWidget(note, 3, 0, 1, 2)

        # ---- Civilization totals (all provinces) ----
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #3a3a3a; margin: 6px 0;")
        layout.addWidget(sep, 4, 0, 1, 2)

        layout.addWidget(QLabel("Civilization total:"), 5, 0)
        self.label_civ_total_revenue = QLabel("—")
        self.label_civ_total_revenue.setStyleSheet("color: #ddd; font-weight: bold;")
        self.label_civ_total_revenue.setAlignment(Qt.AlignRight)
        layout.addWidget(self.label_civ_total_revenue, 5, 1)

        layout.addWidget(QLabel("Δ (session):"), 6, 0)
        self.label_civ_total_revenue_delta = QLabel("")
        self.label_civ_total_revenue_delta.setStyleSheet("color: #888; font-style: italic;")
        self.label_civ_total_revenue_delta.setAlignment(Qt.AlignRight)
        layout.addWidget(self.label_civ_total_revenue_delta, 6, 1)

        return group

    # ------------------------------------------------------------------ #
    #  Queue helpers                                                       #
    # ------------------------------------------------------------------ #

    def _update_queue_display(self) -> None:
        self.queue_list.clear()
        if not self.facade:
            return

        items = self.facade.queue_items()

        total_cost = float(self.facade.queue_total_cost() or 0.0)
        total_paid = float(
            getattr(self.facade, "queue_total_paid", lambda: 0.0)() or 0.0
        )
        total_remaining = float(
            getattr(
                self.facade,
                "queue_total_remaining",
                lambda: total_cost - total_paid,
            )() or 0.0
        )

        if items:
            self.label_queue_count.setText(f"{len(items)} item(s) queued")
            self.label_queue_cost.setText(
                f"Remaining: {total_remaining:.1f}G  (Paid: {total_paid:.1f}G)"
            )
        else:
            self.label_queue_count.setText("Empty queue")
            self.label_queue_cost.setText("Remaining: 0.0G")

        for it in items:
            if it.item_type == QueueItemType.WORKER:
                icon = "👷"
                name = "Worker"
                color = "#64B5F6"
            else:
                unit_key = str(it.data)
                icon = UNIT_ICONS.get(unit_key, "•")
                name = unit_key.replace("_", " ").title()
                color = UNIT_COLORS.get(unit_key, "#aaa")

            cost = float(getattr(it, "cost", 0.0) or 0.0)
            paid = float(getattr(it, "paid", 0.0) or 0.0)
            remaining = float(
                getattr(it, "remaining", max(0.0, cost - paid)) or 0.0
            )
            progress = min(1.0, max(0.0, paid / cost)) if cost > 1e-9 else 0.0

            text = (
                f"{icon} {name} — "
                f"{paid:.1f}/{cost:.1f}G ({int(progress * 100)}%) "
                f"rem {remaining:.1f}G"
            )

            li = QListWidgetItem(text)
            li.setData(Qt.UserRole, it.uid)
            li.setForeground(QColor(color))
            self.queue_list.addItem(li)

        has_items = len(items) > 0
        self.btn_clear_queue.setEnabled(has_items)
        self.btn_remove_selected.setEnabled(False)
        self.label_queue_status.setText("")

    def _optimize_allocation_max_revenue(self) -> None:
        if not self.facade:
            return
        if not (self._has_food and self._has_ore):
            return

        # cancela debounce pendente
        self._update_timer.stop()
        self._pending_value = None

        planet = self.facade.planet
        tile = self.facade.tile

        def revenue_at(pref: float) -> float:
            # set pref (isso recalcula produção + invalida cache)
            self.facade.set_food_pref(pref)
            r = planet.economy.calcular_equilibrio()
            return float(r.get_receita_total(tile) or 0.0)

        # 1) coarse
        best_pct = 50
        best_rev = -1e30
        for pct in range(0, 101, 5):
            rev = revenue_at(pct / 100.0)
            if rev > best_rev + 1e-9:
                best_rev = rev
                best_pct = pct

        # 2) refine around coarse best
        lo = max(0, best_pct - 5)
        hi = min(100, best_pct + 5)
        for pct in range(lo, hi + 1):
            rev = revenue_at(pct / 100.0)
            if rev > best_rev + 1e-9:
                best_rev = rev
                best_pct = pct

        best_pref = best_pct / 100.0
        self.facade.set_food_pref(best_pref)

        # Atualiza slider/progress sem disparar loop
        self.slider_allocation.blockSignals(True)
        self.slider_allocation.setValue(int(best_pct))
        self.slider_allocation.blockSignals(False)

        self.progress_food.setValue(int(best_pct))
        self.progress_ore.setValue(100 - int(best_pct))

        # mantém o estado interno coerente
        self._allocation_preference_pct = int(best_pct)


    # ------------------------------------------------------------------ #
    #  Callbacks                                                           #
    # ------------------------------------------------------------------ #

    def _on_buy_worker(self) -> None:
        if not self.facade:
            return
        ok = self.facade.enqueue_worker()
        if ok:
            self.label_hire_status.setText("✅ Worker queued!")
            self.label_hire_status.setStyleSheet("color: #4CAF50; font-size: 11px;")
            self.update_display()
            self.queue_changed.emit()
        else:
            self.label_hire_status.setText("❌ Failed")
            self.label_hire_status.setStyleSheet("color: #F44336; font-size: 11px;")

    def _on_detach_worker(self) -> None:
        if not self.facade or not self.controller:
            return

        ok = self.controller.action_detach_worker(self.facade.province)

        if ok:
            self.label_detach_status.setText("📋 Detach scheduled for next turn.")  # ← mudou
            self.label_detach_status.setStyleSheet("color: #64B5F6; font-size: 11px;")
            self.update_display()  # atualiza fila (vai aparecer na queue_list)
        else:
            self.label_detach_status.setText("❌ Cannot detach (minimum reached)")
            self.label_detach_status.setStyleSheet("color: #F44336; font-size: 11px;")

    def _on_queue_selection_changed(self) -> None:
        self.btn_remove_selected.setEnabled(
            len(self.queue_list.selectedItems()) > 0
        )

    def _on_remove_selected(self) -> None:
        if not self.facade:
            return
        items = self.queue_list.selectedItems()
        if not items:
            return
        uid = items[0].data(Qt.UserRole)
        if uid and self.facade.queue_remove(str(uid)):
            self.update_display()
            self.queue_changed.emit()

    def _on_clear_queue(self) -> None:
        if not self.facade:
            return
        self.facade.queue_clear()
        self.update_display()
        self.queue_changed.emit()

    # ── Slider ──
    def _on_slider_changed(self, value: int) -> None:
        if not self.facade:
            return

        # ✅ manual override desliga o governor
        if hasattr(self, "chk_auto_max") and self.chk_auto_max.isChecked():
            self.chk_auto_max.setChecked(False)  # dispara _on_auto_toggled (persistindo no repo)

        self._allocation_preference_pct = int(value)
        self._pending_value = int(value)
        self._update_timer.start()
        self.progress_food.setValue(int(value))
        self.progress_ore.setValue(100 - int(value))

    def _on_auto_toggled(self, checked: bool) -> None:
        if not self.facade:
            return

        if hasattr(self.facade, "set_auto_max_revenue"):
            self.facade.set_auto_max_revenue(bool(checked))

        has_both = bool(self._has_food) and bool(self._has_ore)
        self.slider_allocation.setEnabled(has_both and (not checked))

        if checked and has_both:
            self._optimize_allocation_max_revenue()
            self.update_display()

    def _optimize_now_clicked(self) -> None:
        if not self.facade:
            return
        if not (self._has_food and self._has_ore):
            return
        self._optimize_allocation_max_revenue()
        self.update_display()


    def _apply_allocation_change(self) -> None:
        if self._pending_value is None or not self.facade:
            return
        value = int(self._pending_value)
        self._pending_value = None

        food_pct = value / 100.0
        ore_pct = 1.0 - food_pct

        self.facade.set_food_pref(food_pct)
        self.update_display()
        self.allocation_changed.emit(food_pct, ore_pct)
