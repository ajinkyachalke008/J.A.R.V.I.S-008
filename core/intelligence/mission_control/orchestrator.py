"""
core/intelligence/mission_control/orchestrator.py — Mission Control Execution Orchestrator.

Manages the full lifecycle of autonomous missions: state machine transitions, dependency
resolution, capability execution, checkpoint persistence, pause/resume, and final reporting.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Dict, List, Optional

from core import confirm, outcome
from core.intelligence.models import (
    AuditRecord,
    Mission,
    MissionArtifact,
    MissionStatus,
    MissionStep,
    StepStatus,
)
from core.intelligence.storage import IntelligenceStorage, get_intelligence_storage
from .capability_router import get_capability_router
from .planner import MissionPlanner

logger = logging.getLogger("JARVIS.Intelligence.Orchestrator")


class MissionOrchestrator:
    """Coordinates autonomous multi-step missions across all registered capabilities."""

    def __init__(self, base_dir: Optional[Any] = None, db_path: Optional[Any] = None):
        if db_path is not None:
            self._storage = IntelligenceStorage(db_path)
        else:
            self._storage = get_intelligence_storage()
        self._router = get_capability_router()
        self._planner = MissionPlanner()
        self._lock = threading.RLock()
        self._active_mission_id: Optional[str] = None
        self._stop_requested = False
        self._pause_requested = False
        self._status_listeners: List[Callable[[Mission], None]] = []

    def add_status_listener(self, listener: Callable[[Mission], None]) -> None:
        self._status_listeners.append(listener)

    def _notify(self, mission: Mission) -> None:
        for cb in self._status_listeners:
            try:
                cb(mission)
            except Exception as e:
                logger.warning(f"Error in mission listener: {e}")

    @property
    def active_mission_id(self) -> Optional[str]:
        return self._active_mission_id

    def create_mission(self, objective: str = "", project_id: str = "default", title: Optional[str] = None, **kwargs) -> Mission:
        if not objective and "title" in kwargs:
            objective = kwargs.get("objective", kwargs.get("title", ""))
        elif not objective and title:
            objective = title
        """Deconstructs objective into a planned mission and saves it."""
        with self._lock:
            mission = self._planner.plan_objective(objective, project_id=project_id)
            if title:
                mission.title = title
            elif "title" in kwargs and kwargs["title"]:
                mission.title = kwargs["title"]
            self._storage.save_mission(mission)
            self._storage.log_audit(
                AuditRecord(
                    event_type="mission_created",
                    component="MissionControl",
                    action=f"Created mission {mission.mission_id}: {mission.title}",
                    details={"objective": objective, "steps_count": len(mission.steps)},
                )
            )
            self._notify(mission)
            return mission

    def start_mission(self, mission_id: str, background: bool = True) -> Mission:
        """Starts executing a planned mission."""
        with self._lock:
            mission = self._storage.get_mission(mission_id)
            if not mission:
                raise ValueError(f"Mission '{mission_id}' not found.")
            if mission.status == MissionStatus.RUNNING:
                return mission

            mission.status = MissionStatus.RUNNING
            self._storage.save_mission(mission)
            self._active_mission_id = mission.mission_id
            self._stop_requested = False
            self._pause_requested = False
            self._notify(mission)

            if background:
                t = threading.Thread(target=self._run_loop, args=(mission,), daemon=True)
                t.start()
            else:
                self._run_loop(mission)
            return mission

    def pause_mission(self, mission_id: str) -> Optional[Mission]:
        """Pauses a running mission at the next step boundary."""
        with self._lock:
            mission = self._storage.get_mission(mission_id)
            if not mission:
                return None
            self._pause_requested = True
            mission.status = MissionStatus.PAUSED
            self._storage.save_mission(mission)
            self._storage.log_audit(
                AuditRecord(
                    event_type="mission_paused",
                    component="MissionControl",
                    action=f"Paused mission {mission_id}",
                    details={"current_step": mission.current_step_index},
                )
            )
            self._notify(mission)
            return mission

    def resume_mission(self, mission_id: str) -> Optional[Mission]:
        """Resumes a paused mission from its last checkpoint."""
        return self.start_mission(mission_id, background=True)

    def cancel_mission(self, mission_id: str) -> Optional[Mission]:
        """Halts and cancels a mission immediately."""
        with self._lock:
            mission = self._storage.get_mission(mission_id)
            if not mission:
                return None
            self._stop_requested = True
            mission.status = MissionStatus.CANCELLED
            for step in mission.steps:
                if step.status in (StepStatus.PENDING, StepStatus.RUNNING):
                    step.status = StepStatus.CANCELLED
            self._storage.save_mission(mission)
            self._storage.log_audit(
                AuditRecord(
                    event_type="mission_cancelled",
                    component="MissionControl",
                    action=f"Cancelled mission {mission_id}",
                )
            )
            if self._active_mission_id == mission_id:
                self._active_mission_id = None
            self._notify(mission)
            return mission

    def get_mission(self, mission_id: str) -> Optional[Mission]:
        return self._storage.get_mission(mission_id)

    def list_missions(self, limit: int = 50) -> List[Mission]:
        return self._storage.list_missions(limit=limit)

    def _run_loop(self, mission: Mission) -> None:
        """Autonomous step-by-step execution loop."""
        logger.info(f"Starting execution loop for mission {mission.mission_id}: {mission.title}")

        try:
            while mission.current_step_index < len(mission.steps):
                if self._stop_requested:
                    mission.status = MissionStatus.CANCELLED
                    break
                if self._pause_requested:
                    mission.status = MissionStatus.PAUSED
                    break

                step = mission.steps[mission.current_step_index]
                
                # Check dependencies
                dep_failed = False
                for dep_id in step.dependencies:
                    dep_step = next((s for s in mission.steps if s.step_id == dep_id), None)
                    if dep_step and dep_step.status != StepStatus.COMPLETED:
                        dep_failed = True
                        break

                if dep_failed:
                    step.status = StepStatus.AWAITING_DEPENDENCY
                    mission.errors.append(f"Step '{step.description}' blocked by unfulfilled dependencies.")
                    mission.status = MissionStatus.FAILED
                    break

                # Execute step
                step.status = StepStatus.RUNNING
                step.started_at = time.time()
                self._storage.save_mission(mission)
                self._notify(mission)

                status, output, error = self._router.execute(step.capability, step.parameters)
                step.completed_at = time.time()
                step.status = status
                step.output = output if isinstance(output, dict) else {"result": str(output)}
                step.error = error

                if status == StepStatus.FAILED:
                    if step.retry_count < step.max_retries and step.idempotent:
                        step.retry_count += 1
                        logger.warning(f"Step {step.step_id} failed. Retrying ({step.retry_count}/{step.max_retries})...")
                        continue  # retry step
                    else:
                        mission.errors.append(f"Step '{step.description}' failed: {error}")
                        mission.status = MissionStatus.FAILED
                        break

                mission.current_step_index += 1
                self._storage.save_mission(mission)
                self._notify(mission)

            # Post-loop status determination
            if mission.status == MissionStatus.RUNNING:
                if all(s.status == StepStatus.COMPLETED for s in mission.steps):
                    mission.status = MissionStatus.COMPLETED
                elif any(s.status == StepStatus.COMPLETED for s in mission.steps):
                    mission.status = MissionStatus.PARTIALLY_COMPLETED
                else:
                    mission.status = MissionStatus.FAILED

            mission.completed_at = time.time()
            # Compile final report
            mission.final_report = self._compile_report(mission)
            self._storage.save_mission(mission)
            self._storage.log_audit(
                AuditRecord(
                    event_type="mission_completed",
                    component="MissionControl",
                    action=f"Mission {mission.mission_id} finished with status {mission.status.value}",
                    details={"steps_completed": mission.current_step_index, "total_steps": len(mission.steps)},
                )
            )

        except Exception as e:
            logger.error(f"Fatal error in mission run loop: {e}", exc_info=True)
            mission.status = MissionStatus.FAILED
            mission.errors.append(f"Internal orchestrator error: {str(e)}")
            self._storage.save_mission(mission)

        finally:
            if self._active_mission_id == mission.mission_id:
                self._active_mission_id = None
            self._notify(mission)

    def _compile_report(self, mission: Mission) -> str:
        lines = [
            f"# Mission Report: {mission.title}",
            f"**Mission ID:** `{mission.mission_id}` | **Status:** `{mission.status.value}`",
            f"**Objective:** {mission.objective}",
            "",
            "## Execution Timeline",
        ]
        for idx, s in enumerate(mission.steps, 1):
            icon = "✅" if s.status == StepStatus.COMPLETED else ("❌" if s.status == StepStatus.FAILED else "⏳")
            duration = f"({s.completed_at - s.started_at:.2f}s)" if s.started_at and s.completed_at else ""
            lines.append(f"{idx}. {icon} **{s.description}** `{s.capability}` {duration}")
            if s.error:
                lines.append(f"   - *Error:* {s.error}")
            elif s.output and "result" in s.output:
                lines.append(f"   - *Output:* {str(s.output['result'])[:160]}")
        
        if mission.errors:
            lines.extend(["", "## Diagnostics & Errors"])
            for err in mission.errors:
                lines.append(f"- ⚠️ {err}")

        return "\n".join(lines)


    def execute_mission(self, mission_id: str) -> Mission:
        return self.start_mission(mission_id, background=False)

    def generate_mission_report(self, mission_id: str) -> str:
        m = self._storage.get_mission(mission_id)
        if not m:
            return f"# Mission Report: {mission_id} (Not Found)"
        return self._compile_report(m)

    @classmethod
    def get_instance(cls, base_dir=None) -> "MissionOrchestrator":
        return get_mission_orchestrator()


# Global Singleton accessor
_orchestrator_instance: Optional[MissionOrchestrator] = None

def get_mission_orchestrator() -> MissionOrchestrator:
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = MissionOrchestrator()
    return _orchestrator_instance
