"""
core/intelligence/skills/skill_recipe_manager.py — Reusable parameterized skill recipe engine.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.intelligence.models import SkillStatus
from core.intelligence.storage import get_intelligence_storage

logger = logging.getLogger("JARVIS.Intelligence.SkillRecipe")


@dataclass
class SkillRecipe:
    """Declarative, parameterized reusable workflow recipe for Mission Control."""
    skill_id: str
    name: str
    description: str
    trigger_phrases: List[str]
    parameters: Dict[str, Dict[str, Any]]  # name -> {type, default, required}
    steps: List[Dict[str, Any]]
    category: str = "mission_recipe"
    status: str = "ACTIVE"  # DRAFT, VALIDATING, ACTIVE, DISABLED, ARCHIVED
    execution_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_executed_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "trigger_phrases": self.trigger_phrases,
            "parameters": self.parameters,
            "steps": self.steps,
            "category": self.category,
            "status": self.status,
            "execution_count": self.execution_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "created_at": self.created_at,
            "last_executed_at": self.last_executed_at,
        }


class SkillRecipeManager:
    """Creates, registers, validates, and parameterizes reusable mission recipes."""

    def __init__(self, recipes_file: Optional[Path] = None):
        self._recipes_file = recipes_file or (Path.cwd() / "config" / "skill_recipes.json")
        self._recipes: Dict[str, SkillRecipe] = {}
        self._load_recipes()

    def _load_recipes(self) -> None:
        if not self._recipes_file.exists():
            # Seed default flagship recipe: AI Research and Prototype
            default_recipe = SkillRecipe(
                skill_id="ai_research_and_prototype",
                name="AI Research and Prototype",
                description="Researches technical topics on arXiv, prepares workspace, implements code, and verifies with pytest.",
                trigger_phrases=[
                    "run ai research and prototype",
                    "research and build a prototype",
                    "research and prototype",
                ],
                parameters={
                    "topic": {"type": "string", "default": "Autonomous AI Agents", "required": True},
                    "research_source": {"type": "string", "default": "arxiv", "required": False},
                    "language": {"type": "string", "default": "python", "required": False},
                    "test_framework": {"type": "string", "default": "pytest", "required": False},
                },
                steps=[
                    {"id": "research", "action": "arxiv_search", "inputs": {"topic": "{{topic}}"}},
                    {"id": "open_editor", "action": "open_app", "inputs": {"app_name": "code"}},
                    {"id": "generate_prototype", "action": "create_files", "inputs": {"topic": "{{topic}}"}},
                    {"id": "run_tests", "action": "run_pytest", "inputs": {"framework": "pytest"}},
                ],
                status="ACTIVE",
            )
            self._recipes[default_recipe.skill_id] = default_recipe
            self._save_recipes()
            return

        try:
            data = json.loads(self._recipes_file.read_text(encoding="utf-8"))
            for sid, rdict in data.items():
                self._recipes[sid] = SkillRecipe(**rdict)
        except Exception as e:
            logger.error("Failed to load skill recipes: %s", e)

    def _save_recipes(self) -> None:
        try:
            self._recipes_file.parent.mkdir(parents=True, exist_ok=True)
            serializable = {sid: r.to_dict() for sid, r in self._recipes.items()}
            self._recipes_file.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error("Failed to save skill recipes: %s", e)

    def save_recipe_from_mission(
        self,
        name: str,
        topic: str = "Autonomous AI Agents",
        trigger_phrases: Optional[List[str]] = None,
        skill_id: Optional[str] = None,
    ) -> SkillRecipe:
        """Converts a successful workflow into a parameterized, reusable voice skill."""
        clean_name = name.strip()
        sid = skill_id or re.sub(r"[^\w\-]", "_", clean_name.lower()).strip("_")
        triggers = trigger_phrases or [
            f"run {clean_name.lower()}",
            f"execute {clean_name.lower()}",
        ]

        recipe = SkillRecipe(
            skill_id=sid,
            name=clean_name,
            description=f"Autonomous workflow skill generated from mission for: {topic}",
            trigger_phrases=triggers,
            parameters={
                "topic": {"type": "string", "default": topic, "required": True},
                "research_source": {"type": "string", "default": "arxiv", "required": False},
                "test_framework": {"type": "string", "default": "pytest", "required": False},
            },
            steps=[
                {"id": "research", "action": "arxiv_search", "inputs": {"topic": "{{topic}}"}},
                {"id": "open_editor", "action": "open_app", "inputs": {"app_name": "code"}},
                {"id": "generate_prototype", "action": "create_files", "inputs": {"topic": "{{topic}}"}},
                {"id": "run_tests", "action": "run_pytest", "inputs": {"framework": "{{test_framework}}"}},
            ],
            status="ACTIVE",
        )

        self._recipes[sid] = recipe
        self._save_recipes()
        logger.info("Saved reusable skill recipe '%s' (id=%s)", clean_name, sid)
        return recipe

    def find_skill_by_trigger(self, utterance: str) -> Optional[Tuple[SkillRecipe, Dict[str, Any]]]:
        """Matches a natural voice command against registered skill trigger phrases."""
        low = utterance.lower().strip()
        for recipe in self._recipes.values():
            if recipe.status != "ACTIVE":
                continue
            for trigger in recipe.trigger_phrases:
                if trigger in low or low in trigger:
                    # Extract any custom topic mentioned after the trigger
                    topic_val = recipe.parameters.get("topic", {}).get("default", "Autonomous Agents")
                    match_for = re.search(r"\bfor\s+(.+)$", low)
                    if match_for:
                        topic_val = match_for.group(1).strip()
                    return recipe, {"topic": topic_val}
        return None

    def execute_skill(self, skill_id: str, inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Executes a saved skill with fresh parameters and records execution stats."""
        from core.intelligence.mission_control.recipe_runner import get_recipe_runner

        recipe = self._recipes.get(skill_id)
        if not recipe:
            return {"status": "FAILED", "error": f"Skill '{skill_id}' not found."}

        if recipe.status != "ACTIVE":
            return {"status": "DISABLED", "error": f"Skill '{skill_id}' is currently {recipe.status}."}

        bound_inputs = inputs or {}
        topic = bound_inputs.get("topic") or recipe.parameters.get("topic", {}).get("default", "Autonomous AI Agents")

        runner = get_recipe_runner()
        report = runner.execute_research_and_prototype_mission(topic=topic)

        recipe.execution_count += 1
        recipe.last_executed_at = time.time()
        if report.status == "COMPLETED":
            recipe.success_count += 1
        else:
            recipe.failure_count += 1
        self._save_recipes()

        return {
            "status": "SUCCESS" if report.status == "COMPLETED" else "FAILED",
            "skill_id": skill_id,
            "skill_name": recipe.name,
            "mission_id": report.mission_id,
            "topic": topic,
            "spoken_summary": report.spoken_summary,
            "report": report.to_dict(),
        }

    def list_recipes(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._recipes.values()]

    def set_status(self, skill_id: str, status: str) -> bool:
        if skill_id in self._recipes:
            self._recipes[skill_id].status = status.upper()
            self._save_recipes()
            return True
        return False


_skill_recipe_instance: Optional[SkillRecipeManager] = None


def get_skill_recipe_manager() -> SkillRecipeManager:
    global _skill_recipe_instance
    if _skill_recipe_instance is None:
        _skill_recipe_instance = SkillRecipeManager()
    return _skill_recipe_instance

