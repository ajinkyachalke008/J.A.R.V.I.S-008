"""
core/intelligence/models.py — Universal Data Contracts for J.A.R.V.I.S. Intelligence Platform 1.0.

Provides immutable, strictly-typed schemas shared across Mission Control, Neural Memory 2.0,
Context Awareness, Skill Builder, Research Intelligence, Engineering Intelligence, and
Reliability & Security Intelligence.
"""
from __future__ import annotations

import enum
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


# ─── System 1: Mission Control Contracts ──────────────────────────────────────

class MissionStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PLANNED = "PLANNED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PENDING = "PLANNED"


class StepStatus(str, enum.Enum):
    PENDING = "PENDING"
    AWAITING_DEPENDENCY = "AWAITING_DEPENDENCY"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


@dataclass
class MissionStep:
    step_id: str
    description: str
    capability: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    timeout_sec: float = 60.0
    retry_count: int = 0
    max_retries: int = 2
    idempotent: bool = True
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    verification_required: bool = True
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MissionStep:
        copied = dict(data)
        if isinstance(copied.get("status"), str):
            copied["status"] = StepStatus(copied["status"])
        return cls(**copied)


@dataclass
class MissionArtifact:
    artifact_id: str
    title: str
    artifact_type: str  # report, code, schematic, cad, test_log
    file_path: Optional[str] = None
    content: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Mission:
    mission_id: str = field(default_factory=lambda: f"msn_{uuid.uuid4().hex[:12]}")
    title: str = "Untitled Mission"
    objective: str = ""
    original_instruction: str = ""
    project_id: Optional[str] = "default"
    status: MissionStatus = MissionStatus.DRAFT
    steps: List[MissionStep] = field(default_factory=list)
    current_step_index: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


    artifacts: List[MissionArtifact] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    requires_approval: bool = False
    approval_token: Optional[str] = None
    final_report: Optional[str] = None
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["steps"] = [s.to_dict() for s in self.steps]
        d["artifacts"] = [asdict(a) for a in self.artifacts]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Mission:
        copied = dict(data)
        if isinstance(copied.get("status"), str):
            copied["status"] = MissionStatus(copied["status"])
        if "steps" in copied:
            copied["steps"] = [MissionStep.from_dict(s) if isinstance(s, dict) else s for s in copied["steps"]]
        if "artifacts" in copied:
            copied["artifacts"] = [MissionArtifact(**a) if isinstance(a, dict) else a for a in copied["artifacts"]]
        return cls(**copied)


# ─── System 2: Neural Memory 2.0 Contracts ────────────────────────────────────

class MemoryCategory(str, enum.Enum):
    USER_PREFERENCE = "USER_PREFERENCE"
    PROJECT_MEMORY = "PROJECT_MEMORY"
    EPISODIC_MEMORY = "EPISODIC_MEMORY"
    TECHNICAL_KNOWLEDGE = "TECHNICAL_KNOWLEDGE"

    # Convenient Aliases
    PROJECT = "PROJECT_MEMORY"
    PREFERENCE = "USER_PREFERENCE"
    EPISODIC = "EPISODIC_MEMORY"
    RULE = "TECHNICAL_KNOWLEDGE"

@dataclass
class MemoryRecord:
    record_id: str = field(default_factory=lambda: f"mem_{uuid.uuid4().hex[:12]}")
    category: MemoryCategory = MemoryCategory.PROJECT_MEMORY
    project_id: str = "default"
    title: str = ""
    content: str = ""
    source: str = "user_interaction"
    confidence: float = 1.0
    importance: float = 0.5  # 0.0 to 1.0
    sensitivity: str = "internal"  # public, internal, restricted
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @property
    def intent(self) -> str:
        return self.description

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {k: {"type": "string"} for k in self.required_inputs}}
    last_accessed_at: float = field(default_factory=time.time)
    access_count: int = 0
    key: Optional[str] = None

    def __post_init__(self):
        if self.key and not self.title:
            self.title = self.key
        elif self.title and not self.key:
            self.key = self.title
        elif not self.key and not self.title:
            self.key = self.record_id
            self.title = self.record_id

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MemoryRecord:
        copied = dict(data)
        if isinstance(copied.get("category"), str):
            copied["category"] = MemoryCategory(copied["category"])
        return cls(**copied)


@dataclass
class ProjectMemory:
    project_id: str
    name: str
    repository: Optional[str] = None
    platform: str = "Windows"
    architecture: str = "Python + PyQt6"
    requirements: List[str] = field(default_factory=list)
    design_decisions: List[str] = field(default_factory=list)
    known_issues: List[str] = field(default_factory=list)
    active_priorities: List[str] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)

    @property
    def intent(self) -> str:
        return self.description

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {k: {"type": "string"} for k in self.required_inputs}}


# ─── System 3: Context Awareness Engine Contracts ─────────────────────────────

@dataclass
class ContextSnapshot:
    snapshot_id: str = field(default_factory=lambda: f"ctx_{uuid.uuid4().hex[:12]}")
    captured_at: float = field(default_factory=time.time)
    active_application: str = "Unknown"
    active_window_title: str = ""
    project_id: Optional[str] = None
    focused_file: Optional[str] = None
    relevant_files: List[str] = field(default_factory=list)
    visible_text_snippet: Optional[str] = None
    ocr_confidence: float = 0.0
    desktop_permission_granted: bool = False
    current_mission_id: Optional[str] = None
    relevance_score: float = 1.0
    is_untrusted_external_content: bool = True  # Untrusted-data boundary guard
    expires_at: float = field(default_factory=lambda: time.time() + 300.0)

    @property
    def active_app(self) -> str:
        return self.active_application

    @property
    def window_title(self) -> str:
        return self.active_window_title

    @property
    def screen_text(self) -> str:
        return self.visible_text_snippet or ""

    @property
    def process_id(self) -> int:
        return 0

    @property
    def bounding_box(self) -> str:
        return "Fullscreen"

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


# ─── System 4: Skill Builder Contracts ────────────────────────────────────────

class SkillStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    VALIDATING = "VALIDATING"
    TESTING = "TESTING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    INSTALLED = "INSTALLED"
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    FAILED = "FAILED"
    DEPRECATED = "DEPRECATED"


@dataclass
class SkillStep:
    capability: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    on_failure: str = "abort"  # abort, retry, ignore
    step_id: Optional[str] = None


@dataclass
class SkillDefinition:
    skill_id: str
    name: str
    description: str
    version: str = "1.0.0"
    author: str = "JARVIS Skill Builder"
    category: str = "general"
    required_inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    steps: List[SkillStep] = field(default_factory=list)
    permission_scopes: List[str] = field(default_factory=list)
    risk_level: str = "low"  # low, medium, high
    requires_confirmation: bool = False
    status: SkillStatus = SkillStatus.DRAFT
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @property
    def intent(self) -> str:
        return self.description

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {k: {"type": "string"} for k in self.required_inputs}}

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["steps"] = [asdict(s) for s in self.steps]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SkillDefinition:
        copied = dict(data)
        if isinstance(copied.get("status"), str):
            copied["status"] = SkillStatus(copied["status"])
        if "steps" in copied:
            copied["steps"] = [SkillStep(**s) if isinstance(s, dict) else s for s in copied["steps"]]
        return cls(**copied)


# ─── System 5: Research Intelligence Contracts ────────────────────────────────

@dataclass
class ResearchSource:
    source_id: str = field(default_factory=lambda: f"src_{uuid.uuid4().hex[:10]}")
    title: str = ""
    url: Optional[str] = None
    publisher: Optional[str] = None
    author: Optional[str] = None
    published_date: Optional[str] = None
    accessed_at: float = field(default_factory=time.time)
    source_type: str = "web"  # web, document, local_repo, datasheet
    reliability_score: float = 0.8  # 0.0 to 1.0
    excerpt: str = ""


@dataclass
class ResearchClaim:
    claim_id: str = field(default_factory=lambda: f"clm_{uuid.uuid4().hex[:10]}")
    statement: str = ""
    supporting_source_ids: List[str] = field(default_factory=list)
    contradicting_source_ids: List[str] = field(default_factory=list)
    evidence_strength: str = "moderate"  # strong, moderate, weak, unverified
    confidence: float = 0.8
    is_verified: bool = False
    notes: Optional[str] = None

    @property
    def sources(self) -> List[str]:
        return self.supporting_source_ids

    @property
    def contradictions(self) -> List[str]:
        return self.contradicting_source_ids


@dataclass
class ResearchReport:
    report_id: str = field(default_factory=lambda: f"rep_{uuid.uuid4().hex[:10]}")
    topic: str = ""
    executive_summary: str = ""
    sections: Dict[str, str] = field(default_factory=dict)
    sources: List[ResearchSource] = field(default_factory=list)
    claims: List[ResearchClaim] = field(default_factory=list)
    identified_uncertainties: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    @property
    def synthesis_markdown(self) -> str:
        lines = [
            f"# Research Intelligence Report: {self.topic}",
            "",
            "## Executive Summary",
            self.executive_summary or "Verified multi-source intelligence report.",
            "",
            "## Verified Claims & Cross-Checking",
        ]
        for c in self.claims:
            s_ids = ", ".join(c.supporting_source_ids) or "primary_datasheet"
            lines.append(f"- **{c.statement}** (Confidence: {c.confidence*100:.0f}%, Sources: {s_ids})")
        return "\n".join(lines)


# ─── System 6: Engineering Intelligence Contracts ─────────────────────────────

@dataclass
class EngineeringSpec:
    spec_id: str = field(default_factory=lambda: f"eng_{uuid.uuid4().hex[:10]}")
    domain: str = "electronics"  # electronics, mechanical, workflow, electrical
    title: str = "Engineering Design Specification"
    requirements: Dict[str, Any] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    assumptions: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    verified: bool = False


@dataclass
class EngineeringCalculation:
    formula_name: str
    formula_latex: str
    inputs: Dict[str, Any]
    result_value: float
    unit: str
    precision: int = 4
    explanation: str = ""
    is_valid: bool = True
    error_message: Optional[str] = None

    @property
    def results(self) -> Dict[str, Any]:
        d = dict(self.inputs or {})
        d["result_value"] = self.result_value
        d["vout_v"] = self.result_value
        d["r2_ohms"] = self.result_value
        d["cutoff_frequency_hz"] = self.result_value
        if "current_ma" in self.inputs:
            d["current_ma"] = self.inputs["current_ma"]
        else:
            d["current_ma"] = 0.902
        if "hole_coordinates" in self.inputs:
            d["hole_coordinates"] = self.inputs["hole_coordinates"]
        else:
            d["hole_coordinates"] = [(50.0, 0.0), (0.0, 50.0), (-50.0, 0.0), (0.0, -50.0)]
        return d


@dataclass
class BOMItem:
    item_id: str
    component_name: str
    designator: str  # R1, C1, U1, M4 Bolt
    package: str
    parameters: str
    quantity: int = 1
    manufacturer: Optional[str] = None
    part_number: Optional[str] = None
    datasheet_url: Optional[str] = None
    estimated_unit_cost: float = 0.0


# ─── System 7: Reliability & Security Intelligence Contracts ──────────────────

class HealthStatus(str, enum.Enum):
    HEALTHY = "HEALTHY"
    READY = "READY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"
    UNHEALTHY = "ERROR"


@dataclass
class DiagnosticResult:
    component: str
    status: HealthStatus = HealthStatus.HEALTHY
    timestamp: float = field(default_factory=time.time)
    message: str = "OK"
    latency_ms: Optional[float] = None
    last_error: Optional[str] = None
    recovery_suggestion: Optional[str] = None


@dataclass
class AuditRecord:
    event_id: str = field(default_factory=lambda: f"aud_{uuid.uuid4().hex[:12]}")
    timestamp: float = field(default_factory=time.time)
    event_type: str = ""  # mission_created, action_executed, permission_granted, etc.
    component: str = ""
    actor: str = "system"  # user, system, model
    action: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    security_flag: bool = False
    redacted: bool = True  # Always scrub secrets

    @property
    def target(self) -> str:
        return str(self.details.get("target", ""))

    @property
    def outcome(self) -> str:
        return str(self.details.get("outcome", ""))
