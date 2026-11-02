"""
core/desktop/task_planner.py — Multi-step task decomposition and autonomous execution loop.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from core import outcome
from .access_manager import DesktopAccessState, PermissionScope, get_access_manager
from .action_verifier import get_action_verifier
from .cursor_controller import get_cursor_controller
from .screen_capture import get_screen_capture
from .ui_automation import get_ui_automation
from .visual_grounding import get_visual_grounding

logger = logging.getLogger("JARVIS.TaskPlanner")


class DesktopTaskPlanner:
    """Executes multi-step desktop automation tasks with observation-action-verification loops."""

    def __init__(self):
        self._access_mgr = get_access_manager()
        self._cursor = get_cursor_controller()
        self._verifier = get_action_verifier()
        self._ui_automation = get_ui_automation()
        self._grounding = get_visual_grounding()
        self._capture = get_screen_capture()
        self._aborted = False

        # Register canceller with access manager
        self._access_mgr.set_task_canceller(self.abort)

    def abort(self) -> None:
        self._aborted = True
        logger.info("DesktopTaskPlanner: Task aborted.")

    def execute_atomic_action(self, action: str, params: dict[str, Any]) -> str:
        """Executes a single verified atomic desktop action."""
        if not self._access_mgr.is_control_enabled:
            return outcome.failed(
                action,
                "Desktop access is disabled. User must enable Full Desktop Access first.",
                required_state="control_enabled",
            )

        act = action.lower().strip()

        if act == "click_element":
            target = params.get("target") or params.get("name") or ""
            elem = self._ui_automation.find_element_by_name(target)
            if not elem:
                return outcome.failed("click_element", f"Element '{target}' not found in active window.")

            cx, cy = elem.center
            return self._verifier.verify_action(
                "click_element",
                target_desc=f"{elem.name} ({elem.control_type})",
                action_callable=lambda: self._cursor.click(cx, cy),
                region=(elem.rect[0], elem.rect[1], elem.width, elem.height),
            )

        elif act in ("click_coord", "click"):
            x = int(params.get("x", 0))
            y = int(params.get("y", 0))
            # Snap to element if near one
            sx, sy, elem = self._grounding.snap_to_element(x, y)
            desc = f"({sx}, {sy})" + (f" on {elem.name}" if elem else "")
            return self._verifier.verify_action(
                "click_coord",
                target_desc=desc,
                action_callable=lambda: self._cursor.click(sx, sy),
            )

        elif act == "double_click":
            x = int(params.get("x", 0)) if "x" in params else None
            y = int(params.get("y", 0)) if "y" in params else None
            return self._verifier.verify_action(
                "double_click",
                target_desc=f"({x}, {y})",
                action_callable=lambda: self._cursor.double_click(x, y),
            )

        elif act == "right_click":
            x = int(params.get("x", 0)) if "x" in params else None
            y = int(params.get("y", 0)) if "y" in params else None
            return self._verifier.verify_action(
                "right_click",
                target_desc=f"({x}, {y})",
                action_callable=lambda: self._cursor.right_click(x, y),
            )

        elif act in ("type", "type_text"):
            text = str(params.get("text", ""))
            clear_first = bool(params.get("clear_first", False))
            ok = self._cursor.type_text(text, clear_first=clear_first)
            return outcome.done("type_text", length=len(text)) if ok else outcome.failed("type_text", "Typing failed")

        elif act in ("hotkey", "shortcut"):
            keys = params.get("keys", "")
            if isinstance(keys, str):
                key_list = [k.strip().lower() for k in keys.split("+")]
            else:
                key_list = list(keys)
            ok = self._cursor.hotkey(*key_list)
            return outcome.done("hotkey", keys="+".join(key_list)) if ok else outcome.failed("hotkey", "Hotkey failed")

        elif act == "wait":
            secs = float(params.get("seconds", 1.0))
            time.sleep(min(10.0, max(0.1, secs)))
            return outcome.done("wait", seconds=secs)

        elif act == "focus_window":
            title = str(params.get("title", ""))
            from core import appidentity
            return self._verifier.verify_action(
                "focus_window",
                target_desc=title,
                action_callable=lambda: appidentity.focus_window(title),
                expected_focus_change=True,
            )

        return outcome.failed(action, f"Unknown action: {action}")

    def run_multi_step_task(
        self,
        task_description: str,
        steps: List[Dict[str, Any]],
        max_steps: int = 10,
    ) -> str:
        """Executes a planned sequence of verified steps with loop and safety detection."""
        self._aborted = False
        if not self._access_mgr.is_control_enabled:
            return outcome.failed(
                "run_multi_step_task",
                "Desktop access is disabled. Enable Full Desktop Access mode to execute tasks.",
            )

        executed_count = 0
        step_results = []

        for i, step in enumerate(steps[:max_steps], start=1):
            if self._aborted:
                return outcome.failed("run_multi_step_task", "Task was aborted by user or emergency stop.")

            act = step.get("action", "")
            logger.info("Executing task step %d/%d: %s (%s)", i, len(steps), act, step)
            res = self.execute_atomic_action(act, step)
            step_results.append(f"Step {i} ({act}): {res}")
            executed_count += 1

            # Check for failure
            if "status=failed" in res:
                return outcome.failed(
                    "run_multi_step_task",
                    f"Step {i} failed: {res}",
                    completed_steps=executed_count,
                    total_steps=len(steps),
                )

        return outcome.done(
            "run_multi_step_task",
            task=task_description[:60],
            steps_completed=executed_count,
        )


_planner_instance: Optional[DesktopTaskPlanner] = None


def get_task_planner() -> DesktopTaskPlanner:
    global _planner_instance
    if _planner_instance is None:
        _planner_instance = DesktopTaskPlanner()
    return _planner_instance
