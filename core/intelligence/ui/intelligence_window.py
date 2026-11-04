"""
core/intelligence/ui/intelligence_window.py — Native PyQt6 Mission Control & Intelligence Platform Dashboard.

Provides an integrated, holographic Stark HUD dashboard presenting all 7 core intelligence systems:
1. Mission Control: DAG task decomposition, autonomous state machine, progress tracking.
2. Neural Memory 2.0: Project continuity, categorized records, instant keyword search, forgetting/redaction.
3. Context Awareness: Active foreground window, PID, visual grounding permission gating, untrusted boundary indicators.
4. Skill Builder: Declarative skill repository, parameter schemas, interactive dry-run runner.
5. Research Studio: Multi-source evidence synthesis, cross-verification, confidence metrics, markdown report viewer.
6. Engineering Studio: Precision calculators (Voltage divider, Buck converter, RC filter, Bolt circle) & BOM compiler.
7. Reliability Centre: Health diagnostics, subsystem status, system summary, structured audit trail inspector.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.intelligence.context.context_engine import ContextEngine
from core.intelligence.engineering.engineering_intelligence import EngineeringIntelligence
from core.intelligence.memory.neural_memory import NeuralMemoryEngine
from core.intelligence.mission_control.orchestrator import MissionOrchestrator
from core.intelligence.models import (
    MemoryCategory,
    Mission,
    MissionStatus,
    StepStatus,
)
from core.intelligence.reliability.health_monitor import HealthMonitor
from core.intelligence.research.research_manager import ResearchManager
from core.intelligence.skills.skill_builder import SkillBuilder
from core.intelligence.storage import IntelligenceStorage

logger = logging.getLogger("JARVIS.Intelligence.UI")

# HUD Styling Palette
C_BG = "#00060a"
C_PANEL = "#010d14"
C_PANEL_ALT = "#021622"
C_BORDER = "#0d3347"
C_BORDER_BRIGHT = "#1a5c7a"
C_PRI = "#00d4ff"
C_PRI_DIM = "#007a99"
C_ACCENT = "#ff6b00"
C_SUCCESS = "#00ff88"
C_ERROR = "#ff3355"
C_TEXT = "#8ffcff"
C_TEXT_DIM = "#3a8a9a"
C_TEXT_MUTED = "#245260"


_WINDOW_INSTANCE: Optional[IntelligencePlatformWindow] = None


def get_intelligence_window(base_dir: Optional[Path] = None) -> IntelligencePlatformWindow:
    """Retrieve or create the singleton Intelligence Platform window."""
    global _WINDOW_INSTANCE
    if _WINDOW_INSTANCE is None:
        _WINDOW_INSTANCE = IntelligencePlatformWindow(base_dir=base_dir)
    return _WINDOW_INSTANCE


class IntelligencePlatformWindow(QMainWindow):
    """Integrated command console for JARVIS Intelligence Platform 1.0."""

    def __init__(self, base_dir: Optional[Path] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._base_dir = base_dir or Path(__file__).resolve().parent.parent.parent.parent

        # Subsystem backends
        self._orchestrator = MissionOrchestrator.get_instance(self._base_dir)
        self._memory = NeuralMemoryEngine.get_instance(self._base_dir)
        self._context = ContextEngine.get_instance(self._base_dir)
        self._skills = SkillBuilder.get_instance(self._base_dir)
        self._research = ResearchManager.get_instance(self._base_dir)
        self._engineering = EngineeringIntelligence.get_instance(self._base_dir)
        self._reliability = HealthMonitor.get_instance(self._base_dir)
        self._storage = IntelligenceStorage(self._base_dir / "memory" / "intelligence.db")

        self.setWindowTitle("J.A.R.V.I.S. — INTELLIGENCE PLATFORM 1.0")
        self.resize(1120, 780)
        self.setMinimumSize(880, 600)

        self._setup_styles()
        self._build_ui()

        # Refresh timers
        self._timer = QTimer(self)
        self._timer.setInterval(4000)
        self._timer.timeout.connect(self._on_periodic_refresh)
        self._timer.start()

        # Initial refresh
        self._refresh_all()

    def _setup_styles(self) -> None:
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {C_BG};
            }}
            QWidget {{
                background-color: {C_BG};
                color: {C_TEXT};
                font-family: 'Consolas', 'Segoe UI', monospace;
                font-size: 11px;
            }}
            QTabWidget::pane {{
                border: 1px solid {C_BORDER};
                background: {C_PANEL};
                border-radius: 4px;
            }}
            QTabBar::tab {{
                background: {C_PANEL};
                color: {C_TEXT_DIM};
                border: 1px solid {C_BORDER};
                border-bottom: none;
                padding: 7px 14px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-weight: bold;
            }}
            QTabBar::tab:selected {{
                background: {C_PANEL_ALT};
                color: {C_PRI};
                border-color: {C_BORDER_BRIGHT};
                border-bottom: 2px solid {C_PRI};
            }}
            QTabBar::tab:hover {{
                color: #ffffff;
                background: #042030;
            }}
            QGroupBox {{
                border: 1px solid {C_BORDER};
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
                color: {C_PRI};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 4px;
                background-color: {C_BG};
            }}
            QLineEdit, QTextEdit, QComboBox {{
                background-color: #02121d;
                border: 1px solid {C_BORDER};
                border-radius: 3px;
                color: {C_TEXT};
                padding: 4px 6px;
                selection-background-color: {C_PRI_DIM};
            }}
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
                border: 1px solid {C_PRI};
            }}
            QPushButton {{
                background-color: {C_PANEL_ALT};
                border: 1px solid {C_BORDER_BRIGHT};
                border-radius: 3px;
                color: {C_PRI};
                padding: 5px 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #06344d;
                border-color: {C_PRI};
                color: #ffffff;
            }}
            QPushButton:pressed {{
                background-color: #021a27;
            }}
            QPushButton#btnDanger {{
                background-color: #240a10;
                border: 1px solid {C_ERROR};
                color: {C_ERROR};
            }}
            QPushButton#btnDanger:hover {{
                background-color: {C_ERROR};
                color: #ffffff;
            }}
            QPushButton#btnSuccess {{
                background-color: #082618;
                border: 1px solid {C_SUCCESS};
                color: {C_SUCCESS};
            }}
            QPushButton#btnSuccess:hover {{
                background-color: {C_SUCCESS};
                color: #000000;
            }}
            QTableWidget {{
                background-color: {C_PANEL};
                border: 1px solid {C_BORDER};
                gridline-color: #072535;
                color: {C_TEXT};
                selection-background-color: #083750;
                selection-color: #ffffff;
            }}
            QHeaderView::section {{
                background-color: #021622;
                color: {C_PRI};
                border: 1px solid {C_BORDER};
                padding: 4px 6px;
                font-weight: bold;
            }}
            QProgressBar {{
                background-color: #02121d;
                border: 1px solid {C_BORDER};
                border-radius: 3px;
                text-align: center;
                color: #ffffff;
                font-weight: bold;
            }}
            QProgressBar::chunk {{
                background-color: {C_PRI};
                border-radius: 2px;
            }}
            QScrollBar:vertical {{
                background: {C_PANEL};
                width: 10px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {C_BORDER_BRIGHT};
                min-height: 20px;
                border-radius: 4px;
            }}
        """)

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        root_vbox = QVBoxLayout(central)
        root_vbox.setContentsMargins(12, 10, 12, 10)
        root_vbox.setSpacing(8)

        # Header Banner
        header = QHBoxLayout()
        title_lbl = QLabel("◈ J.A.R.V.I.S. MARK LVI — INTELLIGENCE PLATFORM 1.0")
        title_lbl.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {C_PRI}; letter-spacing: 1px;")
        header.addWidget(title_lbl)

        self._sys_status_badge = QLabel("SYSTEM: VERIFYING...")
        self._sys_status_badge.setStyleSheet(f"color: {C_SUCCESS}; font-weight: bold; padding: 2px 8px; border: 1px solid {C_SUCCESS}; border-radius: 3px;")
        header.addWidget(self._sys_status_badge)
        header.addStretch()

        btn_refresh_all = QPushButton("⟳ REFRESH ALL")
        btn_refresh_all.clicked.connect(self._refresh_all)
        header.addWidget(btn_refresh_all)

        root_vbox.addLayout(header)

        # Central Tabs
        self._tabs = QTabWidget(self)
        self._tabs.addTab(self._build_mission_tab(), "🎯 MISSION CONTROL")
        self._tabs.addTab(self._build_memory_tab(), "🧠 NEURAL MEMORY 2.0")
        self._tabs.addTab(self._build_context_tab(), "👁 CONTEXT AWARENESS")
        self._tabs.addTab(self._build_skills_tab(), "⚡ SKILL BUILDER")
        self._tabs.addTab(self._build_research_tab(), "🔬 RESEARCH STUDIO")
        self._tabs.addTab(self._build_engineering_tab(), "📐 ENGINEERING STUDIO")
        self._tabs.addTab(self._build_reliability_tab(), "🛡 RELIABILITY & AUDIT")

        root_vbox.addWidget(self._tabs, 1)

    # ── Tab 1: Mission Control ────────────────────────────────────────────────

    def _build_mission_tab(self) -> QWidget:
        tab = QWidget()
        vbox = QVBoxLayout(tab)
        vbox.setContentsMargins(8, 8, 8, 8)
        vbox.setSpacing(6)

        # Quick Mission Launch Box
        launch_box = QGroupBox("NEW AUTONOMOUS MISSION DEPLOYMENT")
        launch_layout = QHBoxLayout(launch_box)

        self._inp_mission_title = QLineEdit()
        self._inp_mission_title.setPlaceholderText("Mission Title (e.g. Audit Repository & Run Tests)")
        launch_layout.addWidget(self._inp_mission_title, 2)

        self._inp_mission_obj = QLineEdit()
        self._inp_mission_obj.setPlaceholderText("Detailed Objective (e.g. Inspect codebase, verify tests, generate plan)")
        launch_layout.addWidget(self._inp_mission_obj, 3)

        btn_plan_launch = QPushButton("▶ PLAN & LAUNCH")
        btn_plan_launch.setObjectName("btnSuccess")
        btn_plan_launch.clicked.connect(self._on_launch_mission)
        launch_layout.addWidget(btn_plan_launch, 1)

        vbox.addWidget(launch_box)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Missions List
        left_box = QGroupBox("ACTIVE & COMPLETED MISSIONS")
        left_vbox = QVBoxLayout(left_box)

        self._tbl_missions = QTableWidget(0, 4)
        self._tbl_missions.setHorizontalHeaderLabels(["ID", "Title", "Status", "Created"])
        self._tbl_missions.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._tbl_missions.itemSelectionChanged.connect(self._on_mission_selected)
        left_vbox.addWidget(self._tbl_missions)

        btn_m_row = QHBoxLayout()
        self._btn_m_pause = QPushButton("⏸ PAUSE")
        self._btn_m_pause.clicked.connect(self._on_pause_mission)
        self._btn_m_resume = QPushButton("▶ RESUME")
        self._btn_m_resume.clicked.connect(self._on_resume_mission)
        self._btn_m_cancel = QPushButton("⏹ CANCEL")
        self._btn_m_cancel.setObjectName("btnDanger")
        self._btn_m_cancel.clicked.connect(self._on_cancel_mission)
        btn_m_row.addWidget(self._btn_m_pause)
        btn_m_row.addWidget(self._btn_m_resume)
        btn_m_row.addWidget(self._btn_m_cancel)
        left_vbox.addLayout(btn_m_row)

        splitter.addWidget(left_box)

        # Right: DAG Step Timeline & Details
        right_box = QGroupBox("DAG STEP EXECUTION TIMELINE & EVIDENCE")
        right_vbox = QVBoxLayout(right_box)

        self._mission_prog_bar = QProgressBar()
        self._mission_prog_bar.setRange(0, 100)
        self._mission_prog_bar.setValue(0)
        right_vbox.addWidget(self._mission_prog_bar)

        self._tbl_steps = QTableWidget(0, 5)
        self._tbl_steps.setHorizontalHeaderLabels(["Step", "Description", "Capability", "Status", "Duration"])
        self._tbl_steps.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        right_vbox.addWidget(self._tbl_steps, 2)

        self._txt_mission_report = QTextEdit()
        self._txt_mission_report.setReadOnly(True)
        self._txt_mission_report.setPlaceholderText("Select a mission to view synthesis report...")
        right_vbox.addWidget(self._txt_mission_report, 1)

        splitter.addWidget(right_box)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)

        vbox.addWidget(splitter, 1)
        return tab

    # ── Tab 2: Neural Memory 2.0 ──────────────────────────────────────────────

    def _build_memory_tab(self) -> QWidget:
        tab = QWidget()
        vbox = QVBoxLayout(tab)
        vbox.setContentsMargins(8, 8, 8, 8)
        vbox.setSpacing(6)

        # Filter bar
        filter_box = QHBoxLayout()
        filter_box.addWidget(QLabel("Category:"))
        self._cb_mem_category = QComboBox()
        self._cb_mem_category.addItems(["ALL", "project", "preference", "episodic", "rule"])
        self._cb_mem_category.currentIndexChanged.connect(self._refresh_memories)
        filter_box.addWidget(self._cb_mem_category)

        filter_box.addWidget(QLabel("Search:"))
        self._inp_mem_search = QLineEdit()
        self._inp_mem_search.setPlaceholderText("Filter memories by keyword...")
        self._inp_mem_search.textChanged.connect(self._refresh_memories)
        filter_box.addWidget(self._inp_mem_search, 1)

        btn_add_mem = QPushButton("+ STORE RECORD")
        btn_add_mem.clicked.connect(self._on_add_memory_dialog)
        filter_box.addWidget(btn_add_mem)

        vbox.addLayout(filter_box)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Memory Table
        self._tbl_memories = QTableWidget(0, 5)
        self._tbl_memories.setHorizontalHeaderLabels(["Key", "Category", "Project", "Importance", "Updated"])
        self._tbl_memories.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tbl_memories.itemSelectionChanged.connect(self._on_memory_selected)
        splitter.addWidget(self._tbl_memories)

        # Right: Content Viewer & Actions
        detail_box = QGroupBox("MEMORY RECORD CONTENT")
        detail_vbox = QVBoxLayout(detail_box)

        self._txt_mem_content = QTextEdit()
        self._txt_mem_content.setReadOnly(True)
        detail_vbox.addWidget(self._txt_mem_content)

        btn_forget = QPushButton("🗑 FORGET / REDACT RECORD")
        btn_forget.setObjectName("btnDanger")
        btn_forget.clicked.connect(self._on_forget_memory)
        detail_vbox.addWidget(btn_forget)

        splitter.addWidget(detail_box)
        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 4)

        vbox.addWidget(splitter, 1)
        return tab

    # ── Tab 3: Context Awareness ──────────────────────────────────────────────

    def _build_context_tab(self) -> QWidget:
        tab = QWidget()
        vbox = QVBoxLayout(tab)
        vbox.setContentsMargins(10, 10, 10, 10)
        vbox.setSpacing(10)

        # Security Alert
        sec_banner = QLabel("🛡 DEFENSIVE BOUNDARY: Screen observations, OCR, and external window text are treated as UNTRUSTED DATA. Direct code execution from unverified visual tokens is blocked.")
        sec_banner.setStyleSheet(f"background: #180509; color: {C_ERROR}; border: 1px solid {C_ERROR}; padding: 6px; border-radius: 4px; font-weight: bold;")
        vbox.addWidget(sec_banner)

        # Live State Cards
        grid = QHBoxLayout()

        card_app = QGroupBox("ACTIVE WORKSPACE / APPLICATION")
        app_vbox = QVBoxLayout(card_app)
        self._lbl_ctx_app = QLabel("Application: Detecting...")
        self._lbl_ctx_app.setStyleSheet(f"font-size: 13px; color: {C_PRI}; font-weight: bold;")
        self._lbl_ctx_title = QLabel("Window Title: --")
        self._lbl_ctx_pid = QLabel("PID: -- | Bounds: --")
        app_vbox.addWidget(self._lbl_ctx_app)
        app_vbox.addWidget(self._lbl_ctx_title)
        app_vbox.addWidget(self._lbl_ctx_pid)
        grid.addWidget(card_app, 1)

        card_perm = QGroupBox("ACCESS PERMISSION GATING")
        perm_vbox = QVBoxLayout(card_perm)
        self._lbl_perm_observe = QLabel("Screen Observation: CHECKING")
        self._lbl_perm_control = QLabel("Desktop Control: CHECKING")
        perm_vbox.addWidget(self._lbl_perm_observe)
        perm_vbox.addWidget(self._lbl_perm_control)
        grid.addWidget(card_perm, 1)

        vbox.addLayout(grid)

        # Snapshot Preview
        snap_box = QGroupBox("LIVE CONTEXT SNAPSHOT DATA")
        snap_vbox = QVBoxLayout(snap_box)

        self._txt_ctx_raw = QTextEdit()
        self._txt_ctx_raw.setReadOnly(True)
        snap_vbox.addWidget(self._txt_ctx_raw)

        btn_snap = QPushButton("📸 CAPTURE CONTEXT SNAPSHOT NOW")
        btn_snap.clicked.connect(self._on_capture_context)
        snap_vbox.addWidget(btn_snap)

        vbox.addWidget(snap_box, 1)
        return tab

    # ── Tab 4: Skill Builder ──────────────────────────────────────────────────

    def _build_skills_tab(self) -> QWidget:
        tab = QWidget()
        vbox = QVBoxLayout(tab)
        vbox.setContentsMargins(8, 8, 8, 8)
        vbox.setSpacing(6)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Skill Library
        left_box = QGroupBox("INSTALLED DECLARATIVE SKILLS")
        left_vbox = QVBoxLayout(left_box)

        self._tbl_skills = QTableWidget(0, 3)
        self._tbl_skills.setHorizontalHeaderLabels(["Skill Name", "Intent", "Steps"])
        self._tbl_skills.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tbl_skills.itemSelectionChanged.connect(self._on_skill_selected)
        left_vbox.addWidget(self._tbl_skills)

        splitter.addWidget(left_box)

        # Right: Definition & Dry-Run
        right_box = QGroupBox("SKILL SPECIFICATION & DRY RUN")
        right_vbox = QVBoxLayout(right_box)

        self._txt_skill_spec = QTextEdit()
        self._txt_skill_spec.setReadOnly(True)
        right_vbox.addWidget(self._txt_skill_spec, 2)

        btn_dry_run = QPushButton("⚡ DRY-RUN SKILL WORKFLOW")
        btn_dry_run.setObjectName("btnSuccess")
        btn_dry_run.clicked.connect(self._on_dry_run_skill)
        right_vbox.addWidget(btn_dry_run)

        self._txt_dry_run_out = QTextEdit()
        self._txt_dry_run_out.setReadOnly(True)
        self._txt_dry_run_out.setPlaceholderText("Dry-run execution results will appear here...")
        right_vbox.addWidget(self._txt_dry_run_out, 1)

        splitter.addWidget(right_box)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)

        vbox.addWidget(splitter, 1)
        return tab

    # ── Tab 5: Research Studio ────────────────────────────────────────────────

    def _build_research_tab(self) -> QWidget:
        tab = QWidget()
        vbox = QVBoxLayout(tab)
        vbox.setContentsMargins(8, 8, 8, 8)
        vbox.setSpacing(6)

        ctrl_box = QHBoxLayout()
        self._inp_research_topic = QLineEdit()
        self._inp_research_topic.setPlaceholderText("Enter research topic or technical query (e.g. Buck Converter Efficiency Analysis)...")
        ctrl_box.addWidget(self._inp_research_topic, 1)

        btn_conduct = QPushButton("🔬 CONDUCT INVESTIGATION")
        btn_conduct.setObjectName("btnSuccess")
        btn_conduct.clicked.connect(self._on_conduct_research)
        ctrl_box.addWidget(btn_conduct)

        vbox.addLayout(ctrl_box)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # Claims & Evidence Table
        claims_box = QGroupBox("EXTRACTED CLAIMS & CROSS-SOURCE EVIDENCE VERIFICATION")
        claims_vbox = QVBoxLayout(claims_box)
        self._tbl_claims = QTableWidget(0, 4)
        self._tbl_claims.setHorizontalHeaderLabels(["Claim Statement", "Confidence", "Supporting Sources", "Contradictions"])
        self._tbl_claims.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        claims_vbox.addWidget(self._tbl_claims)
        splitter.addWidget(claims_box)

        # Synthesis Report
        report_box = QGroupBox("SYNTHESIZED EVIDENCE REPORT (MARKDOWN)")
        report_vbox = QVBoxLayout(report_box)
        self._txt_research_report = QTextEdit()
        self._txt_research_report.setReadOnly(True)
        report_vbox.addWidget(self._txt_research_report)
        splitter.addWidget(report_box)

        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)

        vbox.addWidget(splitter, 1)
        return tab

    # ── Tab 6: Engineering Studio ─────────────────────────────────────────────

    def _build_engineering_tab(self) -> QWidget:
        tab = QWidget()
        vbox = QVBoxLayout(tab)
        vbox.setContentsMargins(8, 8, 8, 8)
        vbox.setSpacing(8)

        calc_box = QGroupBox("HARDWARE & ELECTRICAL CALCULATORS")
        calc_layout = QHBoxLayout(calc_box)

        # Voltage divider
        vd_box = QGroupBox("VOLTAGE DIVIDER")
        vd_vbox = QVBoxLayout(vd_box)
        self._inp_vd_vin = QLineEdit("12.0")
        self._inp_vd_vin.setPlaceholderText("Vin (V)")
        self._inp_vd_r1 = QLineEdit("10000.0")
        self._inp_vd_r1.setPlaceholderText("R1 (Ω)")
        self._inp_vd_r2 = QLineEdit("3300.0")
        self._inp_vd_r2.setPlaceholderText("R2 (Ω)")
        btn_calc_vd = QPushButton("Compute Vout")
        btn_calc_vd.clicked.connect(self._on_calc_voltage_divider)
        self._lbl_vd_res = QLabel("Vout: --")
        vd_vbox.addWidget(QLabel("Input Voltage (V):"))
        vd_vbox.addWidget(self._inp_vd_vin)
        vd_vbox.addWidget(QLabel("Resistor R1 (Ω):"))
        vd_vbox.addWidget(self._inp_vd_r1)
        vd_vbox.addWidget(QLabel("Resistor R2 (Ω):"))
        vd_vbox.addWidget(self._inp_vd_r2)
        vd_vbox.addWidget(btn_calc_vd)
        vd_vbox.addWidget(self._lbl_vd_res)
        calc_layout.addWidget(vd_box)

        # Buck Converter
        buck_box = QGroupBox("LM2596 BUCK FEEDBACK")
        buck_vbox = QVBoxLayout(buck_box)
        self._inp_buck_vout = QLineEdit("5.0")
        self._inp_buck_vout.setPlaceholderText("Target Vout (V)")
        self._inp_buck_r1 = QLineEdit("1000.0")
        self._inp_buck_r1.setPlaceholderText("R1 (Ω) [Ref: 1k-3k]")
        btn_calc_buck = QPushButton("Compute R2")
        btn_calc_buck.clicked.connect(self._on_calc_buck)
        self._lbl_buck_res = QLabel("R2: --")
        buck_vbox.addWidget(QLabel("Desired Output (V):"))
        buck_vbox.addWidget(self._inp_buck_vout)
        buck_vbox.addWidget(QLabel("R1 Bottom (Ω):"))
        buck_vbox.addWidget(self._inp_buck_r1)
        buck_vbox.addWidget(btn_calc_buck)
        buck_vbox.addWidget(self._lbl_buck_res)
        calc_layout.addWidget(buck_box)

        # RC Filter
        rc_box = QGroupBox("RC LOW-PASS FILTER")
        rc_vbox = QVBoxLayout(rc_box)
        self._inp_rc_r = QLineEdit("1000.0")
        self._inp_rc_r.setPlaceholderText("Resistance (Ω)")
        self._inp_rc_c = QLineEdit("0.0000001")
        self._inp_rc_c.setPlaceholderText("Capacitance (F) [e.g. 100nF]")
        btn_calc_rc = QPushButton("Compute fc")
        btn_calc_rc.clicked.connect(self._on_calc_rc)
        self._lbl_rc_res = QLabel("Cutoff: --")
        rc_vbox.addWidget(QLabel("Resistance (Ω):"))
        rc_vbox.addWidget(self._inp_rc_r)
        rc_vbox.addWidget(QLabel("Capacitance (F):"))
        rc_vbox.addWidget(self._inp_rc_c)
        rc_vbox.addWidget(btn_calc_rc)
        rc_vbox.addWidget(self._lbl_rc_res)
        calc_layout.addWidget(rc_box)

        vbox.addWidget(calc_box)

        # BOM Viewer
        bom_box = QGroupBox("BILL OF MATERIALS (BOM) & CAD INTEGRATION")
        bom_vbox = QVBoxLayout(bom_box)
        bom_ctrl = QHBoxLayout()
        btn_gen_bom = QPushButton("📋 GENERATE STANDARD REGULATOR BOM")
        btn_gen_bom.clicked.connect(self._on_gen_regulator_bom)
        bom_ctrl.addWidget(btn_gen_bom)
        bom_ctrl.addStretch()
        bom_vbox.addLayout(bom_ctrl)

        self._txt_bom_viewer = QTextEdit()
        self._txt_bom_viewer.setReadOnly(True)
        self._txt_bom_viewer.setPlaceholderText("Generated BOM and engineering reports will be displayed here...")
        bom_vbox.addWidget(self._txt_bom_viewer)

        vbox.addWidget(bom_box, 1)
        return tab

    # ── Tab 7: Reliability & Audit ────────────────────────────────────────────

    def _build_reliability_tab(self) -> QWidget:
        tab = QWidget()
        vbox = QVBoxLayout(tab)
        vbox.setContentsMargins(8, 8, 8, 8)
        vbox.setSpacing(6)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Subsystems Health
        diag_box = QGroupBox("SUBSYSTEM HEALTH STATUS & CIRCUIT BREAKERS")
        diag_vbox = QVBoxLayout(diag_box)

        self._tbl_health = QTableWidget(0, 3)
        self._tbl_health.setHorizontalHeaderLabels(["Subsystem", "Health", "Latency (ms)"])
        self._tbl_health.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        diag_vbox.addWidget(self._tbl_health)

        btn_run_diag = QPushButton("🔬 EXECUTE DEEP DIAGNOSTIC CHECK")
        btn_run_diag.clicked.connect(self._refresh_health)
        diag_vbox.addWidget(btn_run_diag)

        splitter.addWidget(diag_box)

        # Audit Trail
        audit_box = QGroupBox("STRUCTURED AUDIT TRAIL LOG")
        audit_vbox = QVBoxLayout(audit_box)

        self._tbl_audit = QTableWidget(0, 4)
        self._tbl_audit.setHorizontalHeaderLabels(["Time", "Action", "Target", "Outcome"])
        self._tbl_audit.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        audit_vbox.addWidget(self._tbl_audit)

        btn_clear_audit = QPushButton("CLEAR RECENT LOGS")
        btn_clear_audit.setObjectName("btnDanger")
        btn_clear_audit.clicked.connect(self._on_clear_audit_logs)
        audit_vbox.addWidget(btn_clear_audit)

        splitter.addWidget(audit_box)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)

        vbox.addWidget(splitter, 1)
        return tab

    # ── Slots & Logic ────────────────────────────────────────────────────────

    def _refresh_all(self) -> None:
        self._refresh_missions()
        self._refresh_memories()
        self._on_capture_context()
        self._refresh_skills()
        self._refresh_health()

    def _on_periodic_refresh(self) -> None:
        if not self.isVisible():
            return
        # lightweight periodic refresh of active tab
        idx = self._tabs.currentIndex()
        if idx == 0:
            self._refresh_missions()
        elif idx == 2:
            self._on_capture_context()
        elif idx == 6:
            self._refresh_health()

    # Mission Slots
    def _refresh_missions(self) -> None:
        try:
            missions = self._orchestrator.list_missions()
            self._tbl_missions.setRowCount(len(missions))
            for row, m in enumerate(missions):
                item_id = QTableWidgetItem(m.mission_id[:8])
                item_id.setData(Qt.ItemDataRole.UserRole, m.mission_id)
                self._tbl_missions.setItem(row, 0, item_id)
                self._tbl_missions.setItem(row, 1, QTableWidgetItem(m.title))

                status_item = QTableWidgetItem(m.status.value.upper())
                if m.status == MissionStatus.COMPLETED:
                    status_item.setForeground(QColor(C_SUCCESS))
                elif m.status == MissionStatus.FAILED:
                    status_item.setForeground(QColor(C_ERROR))
                elif m.status == MissionStatus.RUNNING:
                    status_item.setForeground(QColor(C_PRI))
                self._tbl_missions.setItem(row, 2, status_item)

                self._tbl_missions.setItem(row, 3, QTableWidgetItem(m.created_at[:19]))
        except Exception as e:
            logger.error(f"Failed to refresh missions: {e}")

    def _on_launch_mission(self) -> None:
        title = self._inp_mission_title.text().strip()
        obj = self._inp_mission_obj.text().strip()
        if not title:
            QMessageBox.warning(self, "Invalid Input", "Please provide a mission title.")
            return

        try:
            mission = self._orchestrator.create_mission(title=title, objective=obj)
            # Execute mission asynchronously in worker or start
            res = self._orchestrator.execute_mission(mission.mission_id)
            self._refresh_missions()
            self._inp_mission_title.clear()
            self._inp_mission_obj.clear()
            self._select_mission_by_id(mission.mission_id)
        except Exception as e:
            QMessageBox.critical(self, "Execution Error", f"Failed to launch mission: {e}")

    def _on_mission_selected(self) -> None:
        items = self._tbl_missions.selectedItems()
        if not items:
            return
        row = items[0].row()
        m_id = self._tbl_missions.item(row, 0).data(Qt.ItemDataRole.UserRole)
        m = self._orchestrator.get_mission(m_id)
        if not m:
            return

        # Render steps
        self._tbl_steps.setRowCount(len(m.steps))
        completed_steps = sum(1 for s in m.steps if s.status == StepStatus.COMPLETED)
        pct = int((completed_steps / max(1, len(m.steps))) * 100)
        self._mission_prog_bar.setValue(pct)

        for r, s in enumerate(m.steps):
            self._tbl_steps.setItem(r, 0, QTableWidgetItem(str(s.step_num)))
            self._tbl_steps.setItem(r, 1, QTableWidgetItem(s.description))
            self._tbl_steps.setItem(r, 2, QTableWidgetItem(s.capability))
            st_item = QTableWidgetItem(s.status.value.upper())
            if s.status == StepStatus.COMPLETED:
                st_item.setForeground(QColor(C_SUCCESS))
            elif s.status == StepStatus.FAILED:
                st_item.setForeground(QColor(C_ERROR))
            self._tbl_steps.setItem(r, 3, st_item)
            dur_str = f"{s.duration_ms:.1f}ms" if s.duration_ms else "--"
            self._tbl_steps.setItem(r, 4, QTableWidgetItem(dur_str))

        # Markdown report preview
        rpt = self._orchestrator.generate_mission_report(m.mission_id)
        self._txt_mission_report.setPlainText(rpt)

    def _select_mission_by_id(self, mission_id: str) -> None:
        for r in range(self._tbl_missions.rowCount()):
            item = self._tbl_missions.item(r, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == mission_id:
                self._tbl_missions.selectRow(r)
                break

    def _on_pause_mission(self) -> None:
        items = self._tbl_missions.selectedItems()
        if not items:
            return
        m_id = self._tbl_missions.item(items[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        self._orchestrator.pause_mission(m_id)
        self._refresh_missions()

    def _on_resume_mission(self) -> None:
        items = self._tbl_missions.selectedItems()
        if not items:
            return
        m_id = self._tbl_missions.item(items[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        self._orchestrator.resume_mission(m_id)
        self._refresh_missions()

    def _on_cancel_mission(self) -> None:
        items = self._tbl_missions.selectedItems()
        if not items:
            return
        m_id = self._tbl_missions.item(items[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        self._orchestrator.cancel_mission(m_id)
        self._refresh_missions()

    # Memory Slots
    def _refresh_memories(self) -> None:
        cat_str = self._cb_mem_category.currentText()
        cat = None if cat_str == "ALL" else MemoryCategory(cat_str)
        q = self._inp_mem_search.text().strip()

        records = self._memory.recall(query=q, category=cat, limit=50)
        self._tbl_memories.setRowCount(len(records))
        for r, rec in enumerate(records):
            item_k = QTableWidgetItem(rec.key)
            item_k.setData(Qt.ItemDataRole.UserRole, rec.key)
            self._tbl_memories.setItem(r, 0, item_k)
            self._tbl_memories.setItem(r, 1, QTableWidgetItem(rec.category.value))
            self._tbl_memories.setItem(r, 2, QTableWidgetItem(rec.project_id or "--"))
            self._tbl_memories.setItem(r, 3, QTableWidgetItem(f"{rec.importance:.2f}"))
            self._tbl_memories.setItem(r, 4, QTableWidgetItem(rec.updated_at[:19]))

    def _on_memory_selected(self) -> None:
        items = self._tbl_memories.selectedItems()
        if not items:
            return
        key = self._tbl_memories.item(items[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        rec = self._storage.get_memory(key)
        if rec:
            self._txt_mem_content.setPlainText(f"KEY: {rec.key}\nCATEGORY: {rec.category.value}\nPROJECT: {rec.project_id}\nIMPORTANCE: {rec.importance}\nTAGS: {', '.join(rec.tags)}\n\nCONTENT:\n{rec.content}")

    def _on_add_memory_dialog(self) -> None:
        # Quick sample record for demonstration
        self._memory.remember(
            key="sys_note_temp",
            content="Workspace verified. Seven integrated intelligence systems operational.",
            category=MemoryCategory.PROJECT,
            project_id="Mark-LVI",
            importance=0.9,
        )
        self._refresh_memories()

    def _on_forget_memory(self) -> None:
        items = self._tbl_memories.selectedItems()
        if not items:
            return
        key = self._tbl_memories.item(items[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        self._memory.forget(key)
        self._txt_mem_content.clear()
        self._refresh_memories()

    # Context Slots
    def _on_capture_context(self) -> None:
        try:
            snap = self._context.capture_snapshot(include_ocr=False)
            self._lbl_ctx_app.setText(f"Application: {snap.active_app}")
            self._lbl_ctx_title.setText(f"Window Title: {snap.window_title}")
            self._lbl_ctx_pid.setText(f"PID: {snap.process_id} | Rect: {snap.bounding_box or 'Fullscreen'}")

            obs_ok = self._context.has_observation_permission()
            self._lbl_perm_observe.setText(f"Screen Observation: {'ALLOWED' if obs_ok else 'RESTRICTED / GATED'}")
            self._lbl_perm_observe.setStyleSheet(f"color: {C_SUCCESS if obs_ok else C_ERROR}; font-weight: bold;")

            ctrl_ok = self._context.has_control_permission()
            self._lbl_perm_control.setText(f"Desktop Control: {'ALLOWED' if ctrl_ok else 'RESTRICTED / GATED'}")
            self._lbl_perm_control.setStyleSheet(f"color: {C_SUCCESS if ctrl_ok else C_ERROR}; font-weight: bold;")

            self._txt_ctx_raw.setPlainText(
                f"Context Snapshot ID: {snap.snapshot_id}\n"
                f"Captured At: {snap.captured_at}\n"
                f"Active Application: {snap.active_app}\n"
                f"Window Title: {snap.window_title}\n"
                f"PID: {snap.process_id}\n"
                f"Gated Permissions: Observation={obs_ok}, Control={ctrl_ok}\n"
                f"Untrusted Screen Text Tokens: {len(snap.screen_text or '')} chars"
            )
        except Exception as e:
            logger.error(f"Context capture failed: {e}")

    # Skill Slots
    def _refresh_skills(self) -> None:
        skills = self._skills.list_skills()
        self._tbl_skills.setRowCount(len(skills))
        for r, s in enumerate(skills):
            item_name = QTableWidgetItem(s.name)
            item_name.setData(Qt.ItemDataRole.UserRole, s.skill_id)
            self._tbl_skills.setItem(r, 0, item_name)
            self._tbl_skills.setItem(r, 1, QTableWidgetItem(s.intent))
            self._tbl_skills.setItem(r, 2, QTableWidgetItem(str(len(s.steps))))

    def _on_skill_selected(self) -> None:
        items = self._tbl_skills.selectedItems()
        if not items:
            return
        skill_id = self._tbl_skills.item(items[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        sk = self._skills.get_skill(skill_id)
        if sk:
            spec_dict = {
                "skill_id": sk.skill_id,
                "name": sk.name,
                "version": sk.version,
                "intent": sk.intent,
                "parameters_schema": sk.parameters_schema,
                "steps": [s.__dict__ for s in sk.steps],
            }
            self._txt_skill_spec.setPlainText(json.dumps(spec_dict, indent=2))

    def _on_dry_run_skill(self) -> None:
        items = self._tbl_skills.selectedItems()
        if not items:
            QMessageBox.information(self, "Select Skill", "Please select a skill from the list to dry run.")
            return
        skill_id = self._tbl_skills.item(items[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        res = self._skills.dry_run(skill_id)
        self._txt_dry_run_out.setPlainText(json.dumps(res, indent=2))

    # Research Slots
    def _on_conduct_research(self) -> None:
        topic = self._inp_research_topic.text().strip()
        if not topic:
            QMessageBox.warning(self, "Missing Topic", "Please specify a research topic.")
            return

        report = self._research.conduct_investigation(topic)
        self._tbl_claims.setRowCount(len(report.claims))
        for r, c in enumerate(report.claims):
            self._tbl_claims.setItem(r, 0, QTableWidgetItem(c.statement))
            self._tbl_claims.setItem(r, 1, QTableWidgetItem(f"{c.confidence * 100:.1f}%"))
            self._tbl_claims.setItem(r, 2, QTableWidgetItem(", ".join(c.sources)))
            self._tbl_claims.setItem(r, 3, QTableWidgetItem(", ".join(c.contradictions) or "None"))

        self._txt_research_report.setPlainText(report.synthesis_markdown)

    # Engineering Slots
    def _on_calc_voltage_divider(self) -> None:
        try:
            vin = float(self._inp_vd_vin.text())
            r1 = float(self._inp_vd_r1.text())
            r2 = float(self._inp_vd_r2.text())
            calc = self._engineering.calculate_voltage_divider(vin, r1, r2)
            vout = calc.results.get("vout_v", 0.0)
            i_ma = calc.results.get("current_ma", 0.0)
            self._lbl_vd_res.setText(f"Vout: {vout:.3f} V | Current: {i_ma:.3f} mA")
            self._lbl_vd_res.setStyleSheet(f"color: {C_SUCCESS}; font-weight: bold;")
        except Exception as e:
            self._lbl_vd_res.setText(f"Error: {e}")
            self._lbl_vd_res.setStyleSheet(f"color: {C_ERROR};")

    def _on_calc_buck(self) -> None:
        try:
            vout = float(self._inp_buck_vout.text())
            r1 = float(self._inp_buck_r1.text())
            calc = self._engineering.calculate_buck_feedback(vout, r1)
            r2 = calc.results.get("r2_ohms", 0.0)
            self._lbl_buck_res.setText(f"R2 Top: {r2:.1f} Ω")
            self._lbl_buck_res.setStyleSheet(f"color: {C_SUCCESS}; font-weight: bold;")
        except Exception as e:
            self._lbl_buck_res.setText(f"Error: {e}")
            self._lbl_buck_res.setStyleSheet(f"color: {C_ERROR};")

    def _on_calc_rc(self) -> None:
        try:
            r = float(self._inp_rc_r.text())
            c = float(self._inp_rc_c.text())
            calc = self._engineering.calculate_rc_cutoff(r, c)
            fc = calc.results.get("cutoff_frequency_hz", 0.0)
            self._lbl_rc_res.setText(f"Cutoff fc: {fc:.2f} Hz")
            self._lbl_rc_res.setStyleSheet(f"color: {C_SUCCESS}; font-weight: bold;")
        except Exception as e:
            self._lbl_rc_res.setText(f"Error: {e}")
            self._lbl_rc_res.setStyleSheet(f"color: {C_ERROR};")

    def _on_gen_regulator_bom(self) -> None:
        items = self._engineering.generate_standard_regulator_bom("Power Module 5V")
        md = self._engineering.format_bom_markdown("Power Module 5V", items)
        self._txt_bom_viewer.setPlainText(md)

    # Reliability Slots
    def _refresh_health(self) -> None:
        try:
            diag = self._reliability.run_full_diagnostics()
            self._tbl_health.setRowCount(len(diag))
            for r, d in enumerate(diag):
                self._tbl_health.setItem(r, 0, QTableWidgetItem(d.subsystem))
                st_item = QTableWidgetItem(d.status.value.upper())
                st_item.setForeground(QColor(C_SUCCESS if d.status.value == "healthy" else C_ERROR))
                self._tbl_health.setItem(r, 1, st_item)
                self._tbl_health.setItem(r, 2, QTableWidgetItem(f"{d.latency_ms:.2f}"))

            summary = self._reliability.get_system_summary()
            overall = summary.get("overall_status", "UNKNOWN")
            self._sys_status_badge.setText(f"SYSTEM: {overall}")
            color = C_SUCCESS if overall == "HEALTHY" else (C_ACCENT if overall == "DEGRADED" else C_ERROR)
            self._sys_status_badge.setStyleSheet(f"color: {color}; font-weight: bold; padding: 2px 8px; border: 1px solid {color}; border-radius: 3px;")

            # Audit logs
            audits = self._storage.get_recent_audit_records(limit=40)
            self._tbl_audit.setRowCount(len(audits))
            for r, a in enumerate(audits):
                self._tbl_audit.setItem(r, 0, QTableWidgetItem(a.timestamp[11:19]))
                self._tbl_audit.setItem(r, 1, QTableWidgetItem(a.action))
                self._tbl_audit.setItem(r, 2, QTableWidgetItem(a.target or "--"))
                self._tbl_audit.setItem(r, 3, QTableWidgetItem(a.outcome or "--"))
        except Exception as e:
            logger.error(f"Health check failed: {e}")

    def _on_clear_audit_logs(self) -> None:
        self._storage.clear_audit_records(older_than_days=0)
        self._refresh_health()

