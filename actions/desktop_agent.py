"""
actions/desktop_agent.py — Autonomous multi-step desktop automation agent for J.A.R.V.I.S. — 008.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from core import outcome
from core.desktop.access_manager import get_access_manager
from core.desktop.task_planner import get_task_planner
from core.desktop.ui_automation import get_ui_automation

logger = logging.getLogger("JARVIS.Action.DesktopAgent")


def desktop_agent(
    parameters: dict[str, Any],
    player: Optional[Any] = None,
    speak: Optional[Any] = None,
    session_memory: Optional[Any] = None,
) -> str:
    """Dispatches atomic or planned multi-step desktop interactions."""
    access_mgr = get_access_manager()
    action = str(parameters.get("action", "")).strip().lower()
    task = str(parameters.get("task", "")).strip()

    # 1. State / Permission inspection
    if action == "status":
        st = access_mgr.get_status_dict()
        return outcome.done("status", **st)

    if action == "inspect_controls":
        uia = get_ui_automation()
        summary = uia.format_tree_summary()
        if player and hasattr(player, "show_content"):
            player.show_content("ACTIVE UI CONTROLS", summary)
        return outcome.done("inspect_controls", count=len(summary.splitlines()) - 1)

    # 2. Execution actions require control permission
    if not access_mgr.is_control_enabled:
        return outcome.failed(
            action or "desktop_task",
            "Desktop access is disabled. Please enable 'FULL DESKTOP ACCESS' in the JARVIS HUD first.",
            permission_state=access_mgr.state.value,
        )

    planner = get_task_planner()

    # 3. Composite or atomic execution
    if action in ("click_element", "click_coord", "click", "double_click", "right_click", "type", "type_text", "hotkey", "wait", "focus_window"):
        return planner.execute_atomic_action(action, parameters)

    if task:
        # If a list of steps is provided
        steps = parameters.get("steps") or [{"action": action, **parameters}] if action else []
        if steps:
            return planner.run_multi_step_task(task, steps)
        return outcome.done("desktop_task", task=task[:50], status="planned")

    return outcome.failed("desktop_agent", "No valid action or task provided.")


TOOL = {
    "name": "desktop_agent",
    "description": (
        "Autonomous desktop agent that plans and executes multi-step desktop tasks such as "
        "clicking buttons, filling forms, finding UI controls, typing text, and navigating Windows applications."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "status | inspect_controls | click_element | click_coord | "
                    "double_click | right_click | type_text | hotkey | wait | focus_window"
                ),
            },
            "task": {
                "type": "STRING",
                "description": "High-level description of the desktop task to perform.",
            },
            "target": {
                "type": "STRING",
                "description": "Name or accessible label of the button or UI element to click.",
            },
            "text": {
                "type": "STRING",
                "description": "Text to type into the focused field.",
            },
            "clear_first": {
                "type": "BOOLEAN",
                "description": "Whether to select all and clear existing text before typing (default: false).",
            },
            "x": {
                "type": "INTEGER",
                "description": "Horizontal pixel coordinate for click.",
            },
            "y": {
                "type": "INTEGER",
                "description": "Vertical pixel coordinate for click.",
            },
            "keys": {
                "type": "STRING",
                "description": "Key shortcut e.g. 'ctrl+s', 'alt+tab', 'enter'.",
            },
            "title": {
                "type": "STRING",
                "description": "Window title to focus for focus_window.",
            },
            "seconds": {
                "type": "NUMBER",
                "description": "Seconds to wait.",
            },
        },
        "required": ["action"],
    },
    "handler": desktop_agent,
    "tier": "core",
}
