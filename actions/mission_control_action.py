"""
actions/mission_control_action.py — Model-callable Mission Control dispatch for J.A.R.V.I.S.

Discovered automatically by core/action_loader.py. Enables Gemini Live and local providers
to autonomously start, pause, resume, cancel, or inspect multi-step missions via voice or text.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from core import outcome
from core.intelligence.mission_control import get_mission_orchestrator
from core.intelligence.models import MissionStatus

logger = logging.getLogger("JARVIS.Actions.MissionControl")


def mission_control(parameters: Dict[str, Any], **kwargs) -> str:
    """Executes mission control operations (start, pause, resume, cancel, status)."""
    action = str(parameters.get("action", "start")).lower().strip()
    objective = str(parameters.get("objective", "")).strip()
    mission_id = str(parameters.get("mission_id", "")).strip()
    project_id = str(parameters.get("project_id", "default")).strip()

    orchestrator = get_mission_orchestrator()

    if action in ("start", "create", "launch"):
        if not objective:
            return outcome.failed("mission_control", "Missing required 'objective' parameter.")
        mission = orchestrator.create_mission(objective, project_id=project_id)
        orchestrator.start_mission(mission.mission_id, background=True)
        return outcome.done(
            "mission_control",
            status="started",
            mission_id=mission.mission_id,
            title=mission.title,
            steps_count=len(mission.steps),
        )

    elif action == "pause":
        if not mission_id:
            mission_id = orchestrator.active_mission_id or ""
        if not mission_id:
            return outcome.failed("mission_control", "No active mission to pause.")
        mission = orchestrator.pause_mission(mission_id)
        if not mission:
            return outcome.failed("mission_control", f"Mission '{mission_id}' not found.")
        return outcome.done("mission_control", status="paused", mission_id=mission_id)

    elif action in ("resume", "continue"):
        if not mission_id:
            missions = orchestrator.list_missions(limit=5)
            paused = next((m for m in missions if m.status == MissionStatus.PAUSED), None)
            if paused:
                mission_id = paused.mission_id
        if not mission_id:
            return outcome.failed("mission_control", "No paused mission found to resume.")
        mission = orchestrator.resume_mission(mission_id)
        return outcome.done("mission_control", status="resumed", mission_id=mission_id)

    elif action in ("cancel", "abort", "stop"):
        if not mission_id:
            mission_id = orchestrator.active_mission_id or ""
        if not mission_id:
            return outcome.failed("mission_control", "No active mission to cancel.")
        mission = orchestrator.cancel_mission(mission_id)
        return outcome.done("mission_control", status="cancelled", mission_id=mission_id)

    elif action in ("status", "inspect", "report"):
        if not mission_id:
            mission_id = orchestrator.active_mission_id or ""
        if not mission_id:
            missions = orchestrator.list_missions(limit=1)
            if missions:
                mission_id = missions[0].mission_id
        if not mission_id:
            return outcome.done("mission_control", status="idle", active_mission="none")
        mission = orchestrator.get_mission(mission_id)
        if not mission:
            return outcome.failed("mission_control", f"Mission '{mission_id}' not found.")
        return outcome.done(
            "mission_control",
            mission_id=mission.mission_id,
            status=mission.status.value,
            current_step=mission.current_step_index + 1,
            total_steps=len(mission.steps),
            title=mission.title,
        )

    return outcome.failed("mission_control", f"Unknown mission_control action '{action}'.")


TOOL = {
    "name": "mission_control",
    "description": (
        "Decompose and coordinate complex, multi-step autonomous missions across J.A.R.V.I.S. "
        "Actions include 'start' (with objective), 'pause', 'resume', 'cancel', and 'status'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Operation to perform: 'start', 'pause', 'resume', 'cancel', or 'status'.",
            },
            "objective": {
                "type": "STRING",
                "description": "Natural language description of the mission to execute (required for 'start').",
            },
            "mission_id": {
                "type": "STRING",
                "description": "Optional unique mission identifier. Defaults to active mission if omitted.",
            },
            "project_id": {
                "type": "STRING",
                "description": "Optional project identifier to associate with the mission.",
            },
        },
        "required": ["action"],
    },
    "handler": mission_control,
}
