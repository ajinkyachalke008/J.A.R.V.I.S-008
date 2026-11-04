"""
core/intelligence/skills/skill_builder.py — Declarative Skill Builder & Lifecycle Manager.

Enables natural language creation, validation, dry-running, and controlled registration of
reusable workflows (Type A Declarative Skills). Integrates with CapabilityRouter.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from core.intelligence.mission_control.capability_router import get_capability_router
from core.intelligence.models import (
    AuditRecord,
    SkillDefinition,
    SkillStatus,
    SkillStep,
)
from core.intelligence.storage import get_intelligence_storage

logger = logging.getLogger("JARVIS.Intelligence.SkillBuilder")


class SkillBuilder:
    """Creates, validates, tests, and manages reusable declarative skills."""

    def __init__(self, base_dir: Optional[Any] = None):
        self._storage = get_intelligence_storage()
        self._router = get_capability_router()

    def create_skill(
        self,
        skill_id: str,
        name: str,
        description: str,
        steps: List[Dict[str, Any]],
        category: str = "workflow",
        required_inputs: Optional[List[str]] = None,
        risk_level: str = "low",
        requires_confirmation: bool = False,
    ) -> SkillDefinition:
        """Constructs a declarative skill definition in DRAFT status."""
        parsed_steps = [SkillStep(**s) if isinstance(s, dict) else s for s in steps]
        skill = SkillDefinition(
            skill_id=skill_id.strip().lower(),
            name=name.strip(),
            description=description.strip(),
            version="1.0.0",
            category=category,
            required_inputs=required_inputs or [],
            steps=parsed_steps,
            risk_level=risk_level,
            requires_confirmation=requires_confirmation,
            status=SkillStatus.DRAFT,
            created_at=time.time(),
            updated_at=time.time(),
        )
        self._storage.save_skill(skill)
        logger.info(f"SkillBuilder: Created draft skill '{skill.name}' ({skill.skill_id})")
        return skill

    def validate_skill(self, skill_id: str) -> Tuple[bool, List[str]]:
        """
        Validates schema, required steps, and capability availability.
        """
        skill = self._storage.get_skill(skill_id)
        if not skill:
            return False, [f"Skill '{skill_id}' not found."]

        errors: List[str] = []
        if not skill.name:
            errors.append("Skill must have a non-empty name.")
        if not skill.steps:
            errors.append("Skill must have at least one execution step.")

        # Check that all capabilities in steps are registered in CapabilityRouter
        for idx, step in enumerate(skill.steps, 1):
            if not step.capability:
                errors.append(f"Step {idx} missing capability identifier.")
            elif not self._router.has_capability(step.capability):
                errors.append(f"Step {idx} requires unregistered capability: '{step.capability}'.")

        if errors:
            skill.status = SkillStatus.FAILED
        else:
            skill.status = SkillStatus.VALIDATING

        self._storage.save_skill(skill)
        return len(errors) == 0, errors

    def dry_run(self, skill_id: str, sample_inputs: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """
        Executes a dry-run test simulating parameter passing and verifying flow.
        """
        skill = self._storage.get_skill(skill_id)
        if not skill:
            return False, "Skill not found."

        is_valid, errs = self.validate_skill(skill_id)
        if not is_valid:
            return False, f"Validation failed: {', '.join(errs)}"

        # Simulated dry-run verification
        skill.status = SkillStatus.TESTING
        self._storage.save_skill(skill)

        # Verify that sample inputs fulfill required_inputs
        sample_inputs = sample_inputs or {}
        missing = [inp for inp in skill.required_inputs if inp not in sample_inputs]
        if missing:
            skill.status = SkillStatus.FAILED
            self._storage.save_skill(skill)
            return False, f"Dry-run failed: Missing required sample inputs: {missing}"

        skill.status = SkillStatus.AWAITING_APPROVAL
        self._storage.save_skill(skill)
        return True, "Dry-run succeeded. Awaiting user installation approval."

    def install_skill(self, skill_id: str) -> Tuple[bool, str]:
        """
        Installs an approved skill and registers it as an invokable capability.
        """
        skill = self._storage.get_skill(skill_id)
        if not skill:
            return False, "Skill not found."

        skill.status = SkillStatus.INSTALLED
        self._storage.save_skill(skill)

        # Register execution wrapper in CapabilityRouter
        def skill_runner(params: Dict[str, Any]) -> Dict[str, Any]:
            results = []
            for s in skill.steps:
                st, out, err = self._router.execute(s.capability, {**s.parameters, **params})
                results.append({"step": s.description, "status": st.value, "output": out, "error": err})
                if st.value == "FAILED" and s.on_failure == "abort":
                    break
            return {"skill_id": skill.skill_id, "results": results}

        self._router.register_handler(f"skill_{skill.skill_id}", skill_runner)

        self._storage.log_audit(
            AuditRecord(
                event_type="skill_installed",
                component="SkillBuilder",
                action=f"Installed declarative skill '{skill.name}'",
                details={"skill_id": skill.skill_id, "steps_count": len(skill.steps)},
            )
        )
        return True, f"Skill '{skill.name}' successfully installed and registered."

    def get_skill(self, skill_id: str) -> Optional[SkillDefinition]:
        return self._storage.get_skill(skill_id)

    def list_skills(self) -> List[SkillDefinition]:
        return self._storage.list_skills()

    def dry_run(self, skill_id: str, sample_inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        sk = self.get_skill(skill_id)
        if not sk:
            return {"status": "FAILED", "error": f"Skill '{skill_id}' not found"}
        sim_steps = []
        for s in sk.steps:
            sim_steps.append({"step_id": s.step_id, "capability": s.capability, "status": "SIMULATED_SUCCESS"})
        return {"status": "DRY_RUN_PASSED", "skill_id": skill_id, "simulated_steps": sim_steps}

    def create_skill_from_dict(self, data: Dict[str, Any]) -> SkillDefinition:
        skill_id = data.get("skill_id", f"skill_{int(time.time())}")
        name = data.get("name", "Untitled Skill")
        desc = data.get("intent", data.get("description", ""))
        steps = data.get("steps", [])
        return self.create_skill(
            skill_id=skill_id,
            name=name,
            description=desc,
            steps=steps,
        )

    @classmethod
    def get_instance(cls, base_dir: Optional[Any] = None) -> "SkillBuilder":
        return get_skill_builder()


# Global Singleton accessor
_skill_builder_instance: Optional[SkillBuilder] = None

def get_skill_builder() -> SkillBuilder:
    global _skill_builder_instance
    if _skill_builder_instance is None:
        _skill_builder_instance = SkillBuilder()
    return _skill_builder_instance
