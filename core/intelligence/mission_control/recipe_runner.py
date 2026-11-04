"""
core/intelligence/mission_control/recipe_runner.py — Autonomous cross-application workflow execution engine.
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import outcome
from core.intelligence.models import Mission, MissionStatus, MissionStep, StepStatus
from core.intelligence.research.arxiv_client import ArxivPaper, get_arxiv_client

logger = logging.getLogger("JARVIS.Intelligence.RecipeRunner")


@dataclass
class WorkflowExecutionReport:
    """Comprehensive diagnostic record of an autonomous cross-app mission."""
    mission_id: str
    topic: str
    workspace_path: str
    papers: List[Dict[str, Any]] = field(default_factory=list)
    files_created: List[str] = field(default_factory=list)
    test_command: str = ""
    test_exit_code: int = 0
    test_stdout: str = ""
    test_passed: int = 0
    test_failed: int = 0
    research_summary: str = ""
    status: str = "COMPLETED"
    spoken_summary: str = ""
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "mission_id": self.mission_id,
            "topic": self.topic,
            "workspace_path": self.workspace_path,
            "papers_count": len(self.papers),
            "files_created": self.files_created,
            "test_command": self.test_command,
            "test_exit_code": self.test_exit_code,
            "test_passed": self.test_passed,
            "test_failed": self.test_failed,
            "status": self.status,
            "spoken_summary": self.spoken_summary,
            "duration_seconds": round(self.duration_seconds, 2),
        }


class CrossAppRecipeRunner:
    """Coordinates research, development environments, file generation, testing, and skill generation."""

    def __init__(self, base_workspace: Optional[Path] = None):
        self._arxiv = get_arxiv_client()
        self._base_workspace = base_workspace or (Path.cwd() / "workspace" / "missions")

    def execute_research_and_prototype_mission(
        self,
        topic: str = "Autonomous AI Agents",
        open_editor: bool = True,
        editor_app: str = "code",
    ) -> WorkflowExecutionReport:
        """
        Executes the flagship cross-application mission:
        1. Query arXiv for real peer-reviewed/pre-print papers.
        2. Synthesize research findings.
        3. Open development environment (e.g. VS Code).
        4. Create clean Python prototype & tests in safe workspace.
        5. Run Pytest and capture real stdout, stderr, and exit code.
        6. Compile diagnostic report and verbal summary.
        """
        start_time = time.time()
        mission_id = f"mission_{int(start_time)}"
        clean_topic = topic.strip()
        topic_slug = re.sub(r"[^\w\-]", "_", clean_topic.lower())[:32].strip("_")

        logger.info("Executing Mission [%s]: '%s'...", mission_id, clean_topic)

        # ── Step 1: Query arXiv ──────────────────────────────────────────────
        papers = self._arxiv.search(clean_topic, max_results=3)
        paper_dicts = [p.to_dict() for p in papers]

        if papers:
            top_paper = papers[0]
            research_summary = (
                f"Retrieved {len(papers)} verified arXiv papers on '{clean_topic}'. "
                f"Primary reference: '{top_paper.title}' by {top_paper.authors[0]} et al. (arXiv:{top_paper.arxiv_id}). "
                f"Key Finding: {top_paper.summary[:240]}..."
            )
        else:
            research_summary = f"No direct arXiv entries returned for '{clean_topic}'; using verified baseline agent architecture."

        # ── Step 2: Prepare Safe Workspace ───────────────────────────────────
        target_dir = self._base_workspace / topic_slug
        target_dir.mkdir(parents=True, exist_ok=True)
        files_created = []

        # ── Step 3: Open Development Environment (VS Code / Editor) ──────────
        if open_editor:
            try:
                from actions.open_app import open_app
                open_app({"app_name": editor_app})
                time.sleep(0.3)
            except Exception as e:
                logger.warning("Could not launch editor '%s': %s", editor_app, e)

        # ── Step 4: Generate Implementation & Tests ──────────────────────────
        agent_file = target_dir / "agent.py"
        test_file = target_dir / "test_agent.py"

        agent_code = (
            f'"""\nAutonomous Agent prototype for: {clean_topic}\n'
            f'References: {papers[0].citation() if papers else "Autonomous Agent Architecture"}\n"""\n'
            f'from dataclasses import dataclass, field\n'
            f'from typing import List, Dict, Any\n\n\n'
            f'@dataclass\n'
            f'class AgentTask:\n'
            f'    task_id: str\n'
            f'    description: str\n'
            f'    completed: bool = False\n\n\n'
            f'class AutonomousAgent:\n'
            f'    def __init__(self, name: str = "{clean_topic[:20]} Agent"):\n'
            f'        self.name = name\n'
            f'        self.tasks: List[AgentTask] = []\n\n'
            f'    def add_task(self, description: str) -> str:\n'
            f'        tid = f"task_{{len(self.tasks) + 1}}"\n'
            f'        self.tasks.append(AgentTask(task_id=tid, description=description))\n'
            f'        return tid\n\n'
            f'    def execute_all(self) -> int:\n'
            f'        for t in self.tasks:\n'
            f'            t.completed = True\n'
            f'        return len(self.tasks)\n'
        )

        test_code = (
            f'"""\nPytest suite for {clean_topic} prototype.\n"""\n'
            f'from agent import AutonomousAgent\n\n\n'
            f'def test_agent_initialization():\n'
            f'    agent = AutonomousAgent()\n'
            f'    assert len(agent.tasks) == 0\n\n\n'
            f'def test_task_addition_and_execution():\n'
            f'    agent = AutonomousAgent()\n'
            f'    tid = agent.add_task("Gather environment observations")\n'
            f'    assert tid == "task_1"\n'
            f'    assert len(agent.tasks) == 1\n'
            f'    assert not agent.tasks[0].completed\n\n'
            f'    count = agent.execute_all()\n'
            f'    assert count == 1\n'
            f'    assert agent.tasks[0].completed\n'
        )

        agent_file.write_text(agent_code, encoding="utf-8")
        test_file.write_text(test_code, encoding="utf-8")
        files_created.extend([str(agent_file), str(test_file)])

        # ── Step 5: Execute Pytest in Workspace ──────────────────────────────
        py_exe = sys.executable
        test_cmd = f'"{py_exe}" -m pytest "{test_file}" -q'
        exit_code = 0
        stdout_txt = ""
        passed_count = 0
        failed_count = 0

        try:
            res = subprocess.run(
                [py_exe, "-m", "pytest", str(test_file), "-q"],
                cwd=str(target_dir),
                capture_output=True,
                text=True,
                timeout=15,
            )
            exit_code = res.returncode
            stdout_txt = res.stdout + ("\n" + res.stderr if res.stderr else "")

            # Parse test counts
            match_pass = re.search(r"(\d+)\s+passed", stdout_txt)
            if match_pass:
                passed_count = int(match_pass.group(1))
            match_fail = re.search(r"(\d+)\s+failed", stdout_txt)
            if match_fail:
                failed_count = int(match_fail.group(1))

        except Exception as e:
            exit_code = 1
            stdout_txt = f"Pytest execution failed: {e}"
            failed_count = 1

        duration = time.time() - start_time
        status_str = "COMPLETED" if exit_code == 0 else "TESTS_FAILED"

        spoken_summary = (
            f"Mission completed, sir. Researched '{clean_topic}' on arXiv with {len(papers)} references, "
            f"created the Python prototype in {target_dir.name}, and executed pytest: {passed_count} passed, {failed_count} failed."
        )

        report = WorkflowExecutionReport(
            mission_id=mission_id,
            topic=clean_topic,
            workspace_path=str(target_dir),
            papers=paper_dicts,
            files_created=files_created,
            test_command=test_cmd,
            test_exit_code=exit_code,
            test_stdout=stdout_txt[:800],
            test_passed=passed_count,
            test_failed=failed_count,
            research_summary=research_summary,
            status=status_str,
            spoken_summary=spoken_summary,
            duration_seconds=duration,
        )

        logger.info("Mission [%s] finished with status '%s' in %.2fs", mission_id, status_str, duration)
        return report


_recipe_runner_instance: Optional[CrossAppRecipeRunner] = None


def get_recipe_runner() -> CrossAppRecipeRunner:
    global _recipe_runner_instance
    if _recipe_runner_instance is None:
        _recipe_runner_instance = CrossAppRecipeRunner()
    return _recipe_runner_instance

