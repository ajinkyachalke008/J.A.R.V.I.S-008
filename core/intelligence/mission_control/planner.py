"""
core/intelligence/mission_control/planner.py — Autonomous Objective Decomposition & DAG Planner.

Deconstructs natural language user objectives into ordered, dependency-linked MissionSteps.
Maps required tasks to registered capabilities and marks risk-sensitive operations.
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from core.intelligence.models import Mission, MissionStatus, MissionStep, StepStatus
from .capability_router import get_capability_router

logger = logging.getLogger("JARVIS.Intelligence.Planner")


class MissionPlanner:
    """Decomposes complex objectives into executable DAG plans."""

    def __init__(self, base_dir: Optional[Any] = None):
        self._router = get_capability_router()

    def plan_objective(
        self,
        objective: str,
        project_id: str = "default",
        original_instruction: Optional[str] = None
    ) -> Mission:
        """
        Deconstructs an objective into an ordered Mission with dependency-linked steps.
        Recognizes common autonomous mission archetypes and constructs targeted plans.
        """
        clean_obj = objective.strip()
        mission = Mission(
            title=self._generate_title(clean_obj),
            objective=clean_obj,
            original_instruction=original_instruction or clean_obj,
            project_id=project_id,
            status=MissionStatus.PLANNED,
        )

        steps = self._decompose(clean_obj, project_id)
        mission.steps = steps
        
        # Check if any step touches high-risk or irreversible capabilities
        for s in steps:
            if s.capability in ("file_deletion", "delete_file", "system_reboot", "format_drive"):
                mission.requires_approval = True
                break

        return mission

    def _generate_title(self, objective: str) -> str:
        words = objective.split()
        if len(words) <= 6:
            return objective.title()
        return " ".join(words[:6]).title() + "..."

    def _decompose(self, objective: str, project_id: str) -> List[MissionStep]:
        lowered = objective.lower()
        steps: List[MissionStep] = []

        # Archetype 1: Repository analysis, testing, and debugging
        if any(k in lowered for k in ["repo", "repository", "bug", "test", "pytest", "audit"]):
            s1 = MissionStep(
                step_id="step_inspect_repo",
                description="Inspect repository status, working tree, and recent commits",
                capability="github_manager",
                parameters={"action": "status", "project_id": project_id},
            )
            s2 = MissionStep(
                step_id="step_run_tests",
                description="Run baseline Pytest verification suite and detect failures",
                capability="run_tests",
                parameters={"command": "pytest -q", "project_id": project_id},
                dependencies=["step_inspect_repo"],
            )
            s3 = MissionStep(
                step_id="step_prepare_report",
                description="Synthesize test diagnostics and compile implementation report",
                capability="report_builder",
                parameters={"topic": "Repository Analysis Report", "project_id": project_id},
                dependencies=["step_run_tests"],
            )
            s4 = MissionStep(
                step_id="step_dispatch_antigravity",
                description="Deliver implementation prompt to Antigravity IDE agent chat",
                capability="antigravity_chat",
                parameters={"prompt": f"Review test diagnostics for project {project_id} and prepare fixes", "submit": False},
                dependencies=["step_prepare_report"],
            )
            steps.extend([s1, s2, s3, s4])

        # Archetype 2: Research, engineering design, and circuit calculation
        elif any(k in lowered for k in ["circuit", "solar", "inverter", "power", "schematic", "cad", "calculate"]):
            s1 = MissionStep(
                step_id="step_research_specs",
                description="Gather technical parameters and component datasheets",
                capability="research_sources",
                parameters={"query": objective, "project_id": project_id},
            )
            s2 = MissionStep(
                step_id="step_calculate_parameters",
                description="Execute engineering calculations and validate electrical units",
                capability="engineering_calculate",
                parameters={"objective": objective, "project_id": project_id},
                dependencies=["step_research_specs"],
            )
            s3 = MissionStep(
                step_id="step_generate_schematic",
                description="Construct structured circuit model and generate Bill of Materials",
                capability="creation_studio",
                parameters={"action": "create_schematic", "domain": "circuit", "project_id": project_id},
                dependencies=["step_calculate_parameters"],
            )
            s4 = MissionStep(
                step_id="step_archive_project_memory",
                description="Store validated design decisions in Neural Memory 2.0",
                capability="neural_memory_store",
                parameters={"project_id": project_id, "importance": 0.9},
                dependencies=["step_generate_schematic"],
            )
            steps.extend([s1, s2, s3, s4])

        # Archetype 3: Multi-source research intelligence
        elif any(k in lowered for k in ["research", "compare", "market", "battery", "technology", "literature"]):
            s1 = MissionStep(
                step_id="step_collect_sources",
                description="Decompose research questions and gather multi-source evidence",
                capability="research_sources",
                parameters={"topic": objective, "project_id": project_id},
            )
            s2 = MissionStep(
                step_id="step_cross_check_evidence",
                description="Cross-check claims, identify contradictions, and score confidence",
                capability="research_cross_check",
                parameters={"project_id": project_id},
                dependencies=["step_collect_sources"],
            )
            s3 = MissionStep(
                step_id="step_generate_research_report",
                description="Synthesize evidence-backed Markdown research report with verified citations",
                capability="report_builder",
                parameters={"topic": objective, "project_id": project_id},
                dependencies=["step_cross_check_evidence"],
            )
            steps.extend([s1, s2, s3])

        # Default: General multi-step execution
        else:
            s1 = MissionStep(
                step_id="step_gather_context",
                description=f"Gather current context for: {objective}",
                capability="context_awareness",
                parameters={"query": objective, "project_id": project_id},
            )
            s2 = MissionStep(
                step_id="step_execute_objective",
                description=f"Execute core task: {objective}",
                capability="desktop_agent",
                parameters={"task": objective, "project_id": project_id},
                dependencies=["step_gather_context"],
            )
            s3 = MissionStep(
                step_id="step_verify_outcome",
                description="Verify results and report observed ground-truth",
                capability="outcome_verifier",
                parameters={"project_id": project_id},
                dependencies=["step_execute_objective"],
            )
            steps.extend([s1, s2, s3])

        return steps

    def decompose_objective(self, objective: str, project_id: str = "default") -> List[MissionStep]:
        m = self.plan_objective(objective, project_id=project_id)
        # Ensure numerical dependencies format if expected by tests
        for i, s in enumerate(m.steps):
            s.step_num = i + 1
            if i > 0:
                s.dependencies = [i]
            else:
                s.dependencies = []
        return m.steps

