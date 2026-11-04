"""
actions/mission_recipe_action.py — Cross-application Mission Control recipes and reusable skills action.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from core import outcome
from core.intelligence.mission_control.recipe_runner import get_recipe_runner
from core.intelligence.skills.skill_recipe_manager import get_skill_recipe_manager

logger = logging.getLogger("JARVIS.Action.MissionRecipe")


def mission_recipe_action(
    parameters: dict[str, Any],
    player: Optional[Any] = None,
    speak: Optional[Any] = None,
    session_memory: Optional[Any] = None,
) -> str:
    """Coordinates autonomous cross-application workflows and saves them as reusable skills."""
    params = parameters or {}
    action = str(params.get("action", "run_mission")).strip().lower()
    topic = str(params.get("topic") or "Autonomous AI Agents").strip()

    runner = get_recipe_runner()
    recipe_mgr = get_skill_recipe_manager()

    # 1. Execute Cross-App Mission ("Research on arXiv, open VS Code, create demo, run pytest")
    if action in ("run_mission", "execute_recipe", "research_and_prototype"):
        if speak:
            speak(f"Starting mission for {topic}. Conducting arXiv research now, sir.")
        open_editor = bool(params.get("open_editor", True))
        report = runner.execute_research_and_prototype_mission(topic=topic, open_editor=open_editor)

        if player and hasattr(player, "show_content"):
            player.show_content("MISSION REPORT", report.spoken_summary + "\n\n" + report.test_stdout)

        return outcome.done(
            "run_mission",
            mission_id=report.mission_id,
            topic=report.topic,
            status=report.status,
            passed=report.test_passed,
            failed=report.test_failed,
            workspace=report.workspace_path,
            spoken_response=report.spoken_summary,
        )

    # 2. Save Workflow as Reusable Skill ("Save this workflow as my AI research and prototype skill")
    elif action in ("save_as_skill", "save_skill", "create_skill"):
        skill_name = str(params.get("name") or "AI Research and Prototype").strip()
        recipe = recipe_mgr.save_recipe_from_mission(name=skill_name, topic=topic)
        msg = f"Workflow successfully saved as reusable skill '{recipe.name}'. You can invoke it anytime by saying 'run {recipe.name.lower()}'."
        if speak:
            speak(msg)
        return outcome.done("save_as_skill", skill_id=recipe.skill_id, name=recipe.name, spoken_response=msg)

    # 3. Run Saved Reusable Skill ("Run my AI Research and Prototype skill for autonomous vehicles")
    elif action in ("run_skill", "execute_skill"):
        skill_id = str(params.get("skill_id") or "ai_research_and_prototype").strip()
        custom_topic = str(params.get("topic") or topic).strip()
        if speak:
            speak(f"Invoking skill {skill_id} for {custom_topic}, sir.")
        res = recipe_mgr.execute_skill(skill_id, inputs={"topic": custom_topic})
        if res.get("status") == "SUCCESS":
            summary = res.get("spoken_summary", "")
            return outcome.done("run_skill", skill_id=skill_id, topic=custom_topic, spoken_response=summary)
        return outcome.failed("run_skill", res.get("error", "Skill execution failed."))

    # 4. List Registered Skills
    elif action in ("list_skills", "show_skills"):
        skills = recipe_mgr.list_recipes()
        if player and hasattr(player, "show_content"):
            player.show_content("REGISTERED SKILLS", str(skills))
        return outcome.done("list_skills", count=len(skills), skills=skills)

    return outcome.failed("mission_recipe", f"Unknown action: '{action}'")


TOOL = {
    "name": "mission_recipe",
    "description": (
        "Autonomous cross-application Mission Control recipes and reusable skill builder. "
        "Use to research technical topics on arXiv, open VS Code, create prototype code and tests, "
        "execute pytest, and save the workflow as a reusable skill."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "run_mission | save_as_skill | run_skill | list_skills",
            },
            "topic": {
                "type": "STRING",
                "description": "Research and prototype topic (e.g. 'Autonomous AI Agents', 'Power System Optimization').",
            },
            "name": {
                "type": "STRING",
                "description": "Skill name when saving a workflow (e.g. 'AI Research and Prototype').",
            },
            "skill_id": {
                "type": "STRING",
                "description": "Identifier of the saved skill to execute (default: 'ai_research_and_prototype').",
            },
            "open_editor": {
                "type": "BOOLEAN",
                "description": "Whether to launch the development environment (default: true).",
            },
        },
        "required": ["action"],
    },
    "handler": mission_recipe_action,
    "tier": "core",
}

