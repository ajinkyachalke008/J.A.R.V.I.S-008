"""
core/intelligence — J.A.R.V.I.S. Intelligence Platform 1.0.

Integrates the Seven Intelligence Systems:
1. Mission Control (orchestrator, planner, capability router)
2. Neural Memory 2.0 (project continuity, categorized memory, keyword/relevance retrieval)
3. Context Awareness Engine (active app/window, permission-gated visual grounding)
4. Skill Builder (declarative workflow synthesis, schema validation, dry runner)
5. Research Intelligence (evidence cross-checking, source tracking, markdown report generator)
6. Engineering Intelligence (mathematical calculations, unit validation, BOM generation, CAD/Circuit extension)
7. Reliability & Security Intelligence (health monitoring, audit trail, circuit breakers, safe recovery)
"""
from __future__ import annotations

from .models import (
    AuditRecord,
    BOMItem,
    ContextSnapshot,
    DiagnosticResult,
    EngineeringCalculation,
    EngineeringSpec,
    HealthStatus,
    MemoryCategory,
    MemoryRecord,
    Mission,
    MissionArtifact,
    MissionStatus,
    MissionStep,
    ProjectMemory,
    ResearchClaim,
    ResearchReport,
    ResearchSource,
    SkillDefinition,
    SkillStatus,
    SkillStep,
    StepStatus,
)

__all__ = [
    "AuditRecord",
    "BOMItem",
    "ContextSnapshot",
    "DiagnosticResult",
    "EngineeringCalculation",
    "EngineeringSpec",
    "HealthStatus",
    "MemoryCategory",
    "MemoryRecord",
    "Mission",
    "MissionArtifact",
    "MissionStatus",
    "MissionStep",
    "ProjectMemory",
    "ResearchClaim",
    "ResearchReport",
    "ResearchSource",
    "SkillDefinition",
    "SkillStatus",
    "SkillStep",
    "StepStatus",
]
