"""
tests/test_intelligence_platform.py — Test suite for J.A.R.V.I.S. Intelligence Platform 1.0.

Covers all 7 integrated intelligence systems:
- Mission Control (Orchestrator, DAG Planner, Capability Router, Model Tool Action)
- Neural Memory 2.0 (Continuity, multi-tier categories, secret scrubbing, prompt injection)
- Context Awareness (Active window, permission gating, untrusted data boundary)
- Skill Builder (Declarative synthesis, parameter validation, dry-runner)
- Research Intelligence (Evidence gathering, cross-verification, citations)
- Engineering Intelligence (Circuit & mechanical formulas, BOM synthesis)
- Reliability & Security (Subsystem diagnostics, audit logs, Dynamic Island ticker)
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path
import pytest

from core.intelligence.models import (
    ContextSnapshot,
    MemoryCategory,
    MemoryRecord,
    MissionStatus,
    StepStatus,
)
from core.intelligence.storage import IntelligenceStorage
from core.intelligence.mission_control.capability_router import CapabilityRouter
from core.intelligence.mission_control.planner import MissionPlanner
from core.intelligence.mission_control.orchestrator import MissionOrchestrator
from actions.mission_control_action import mission_control
from core.intelligence.memory.neural_memory import NeuralMemoryEngine
from core.intelligence.context.context_engine import ContextEngine
from core.intelligence.skills.skill_builder import SkillBuilder
from core.intelligence.research.research_manager import ResearchManager
from core.intelligence.engineering.engineering_intelligence import EngineeringIntelligence
from core.intelligence.reliability.health_monitor import HealthMonitor


@pytest.fixture
def temp_dir(tmp_path):
    return tmp_path


class TestStorageAndModels:
    def test_storage_crud_and_redaction(self, temp_dir):
        db_path = temp_dir / "test_intel.db"
        storage = IntelligenceStorage(db_path)

        # Store with API key
        rec = MemoryRecord(
            key="test_key_1",
            content="Sensitive key is sk-proj-1234567890abcdef1234567890 and password=mysecret",
            category=MemoryCategory.PROJECT,
            project_id="Mark-LVI",
            importance=0.85,
        )
        storage.save_memory(rec)

        loaded = storage.get_memory("test_key_1")
        assert loaded is not None
        assert "[REDACTED_API_KEY]" in loaded.content
        assert "sk-proj-1234567890" not in loaded.content
        assert loaded.importance == 0.85

        # Search
        results = storage.search_memories(query="Sensitive key", category=MemoryCategory.PROJECT)
        assert len(results) == 1
        assert results[0].key == "test_key_1"

        # Delete
        assert storage.delete_memory("test_key_1") is True
        assert storage.get_memory("test_key_1") is None

    def test_audit_logging_and_clearing(self, temp_dir):
        db_path = temp_dir / "test_audit.db"
        storage = IntelligenceStorage(db_path)

        storage.record_audit(action="TEST_ACTION", target="test_target", outcome="SUCCESS", details={"code": 0})
        records = storage.get_recent_audit_records(limit=10)
        assert len(records) >= 1
        assert records[0].action == "TEST_ACTION"
        assert records[0].target == "test_target"

        deleted_count = storage.clear_audit_records(older_than_days=0)
        assert deleted_count >= 1
        assert len(storage.get_recent_audit_records()) == 0


class TestMissionControl:
    def test_planner_dag_creation(self, temp_dir):
        planner = MissionPlanner(temp_dir)
        steps = planner.decompose_objective("Audit repository, run test suite, and generate engineering report")
        assert len(steps) >= 3
        # Check DAG step ordering and dependencies
        assert steps[0].step_num == 1
        assert steps[0].dependencies == []
        assert 1 in steps[1].dependencies

    def test_capability_router_dispatch(self, temp_dir):
        router = CapabilityRouter(base_dir=temp_dir)
        # Internal echo handler
        res = router.dispatch("internal.echo", {"text": "JARVIS online"})
        assert res.get("status") == "success"
        assert res.get("echo") == "JARVIS online"

        # System health handler
        health_res = router.dispatch("internal.system_health")
        assert health_res.get("status") == "healthy"

    def test_orchestrator_execution_lifecycle(self, temp_dir):
        from core.intelligence.mission_control.capability_router import get_capability_router
        get_capability_router().register_handler("desktop_agent", lambda p: {"status": "success", "executed": True})
        orch = MissionOrchestrator(base_dir=temp_dir, db_path=temp_dir / "orch.db")
        mission = orch.create_mission(
            title="Automated Unit Mission",
            objective="Inspect system and verify health",
        )
        assert mission.status == MissionStatus.PENDING
        assert len(mission.steps) >= 2

        # Execute
        result = orch.execute_mission(mission.mission_id)
        assert result.status == MissionStatus.COMPLETED
        assert result.completed_at is not None
        assert all(s.status == StepStatus.COMPLETED for s in result.steps)

        # Markdown report
        report = orch.generate_mission_report(mission.mission_id)
        assert "# Mission Report:" in report
        assert "Automated Unit Mission" in report

    def test_mission_control_action_tool(self, temp_dir):
        # Test start
        res_start = mission_control({"action": "start", "objective": "Run automated test mission"})
        assert "done" in res_start
        assert "status=started" in res_start
        assert "mission_id=" in res_start

        # Extract mission_id
        match = re.search(r"mission_id=(\S+)", res_start)
        assert match is not None
        m_id = match.group(1).strip("'\"")

        # Test status
        res_stat = mission_control({"action": "status", "mission_id": m_id})
        assert "done" in res_stat
        assert f"mission_id={m_id}" in res_stat

        # Test pause & resume
        res_pause = mission_control({"action": "pause", "mission_id": m_id})
        assert "done" in res_pause or "paused" in res_pause
        res_resume = mission_control({"action": "resume", "mission_id": m_id})
        assert "done" in res_resume or "resumed" in res_resume


class TestNeuralMemory2:
    def test_remember_recall_and_formatting(self, temp_dir):
        mem = NeuralMemoryEngine(base_dir=temp_dir, db_path=temp_dir / "neural.db")
        mem.remember(
            key="arch_rule",
            content="Always enforce strict separation of concerns.",
            category=MemoryCategory.RULE,
            importance=0.95,
        )
        mem.remember(
            key="user_style",
            content="User prefers concise stark HUD responses.",
            category=MemoryCategory.PREFERENCE,
            importance=0.8,
        )

        # Recall
        rules = mem.recall(category=MemoryCategory.RULE)
        assert len(rules) == 1
        assert "separation of concerns" in rules[0].content

        # Prompt formatting
        prompt_block = mem.format_for_prompt(project_id=None, query="stark HUD")
        assert "[NEURAL MEMORY 2.0 CONTEXT]" in prompt_block
        assert "User prefers concise stark HUD responses" in prompt_block


class TestContextAwareness:
    def test_context_engine_gating(self, temp_dir):
        engine = ContextEngine(base_dir=temp_dir)
        snap = engine.capture_snapshot(include_ocr=False)
        assert isinstance(snap, ContextSnapshot)
        assert snap.active_app is not None
        assert snap.window_title is not None

        # Check defensive boundary
        tokens = engine.get_sanitized_visual_tokens(snap)
        assert isinstance(tokens, list)
        for t in tokens:
            # Dangerous shell tokens must be sanitized
            assert "&&" not in t
            assert ";" not in t


class TestSkillBuilder:
    def test_skill_registration_and_dry_run(self, temp_dir):
        builder = SkillBuilder(base_dir=temp_dir)
        sample_spec = {
            "skill_id": "test_echo_skill",
            "name": "Test Echo Skill",
            "version": "1.0",
            "intent": "Echo message for test verification",
            "parameters_schema": {
                "type": "object",
                "properties": {"msg": {"type": "string"}},
                "required": ["msg"],
            },
            "steps": [
                {
                    "step_id": "s1",
                    "capability": "internal.echo",
                    "parameters": {"text": "Executing dry-run echo"},
                }
            ],
        }
        skill = builder.create_skill_from_dict(sample_spec)
        assert skill.skill_id == "test_echo_skill"

        # Dry run
        dry_res = builder.dry_run("test_echo_skill")
        assert dry_res.get("status") == "DRY_RUN_PASSED"
        assert len(dry_res.get("simulated_steps", [])) == 1


class TestResearchIntelligence:
    def test_investigation_and_claim_extraction(self, temp_dir):
        res_mgr = ResearchManager(base_dir=temp_dir)
        report = res_mgr.conduct_investigation("Efficiency of DC-DC Buck Converters")
        assert report.topic == "Efficiency of DC-DC Buck Converters"
        assert len(report.claims) >= 1
        assert len(report.sources) >= 1
        assert "# Research Intelligence Report:" in report.synthesis_markdown
        assert "## Verified Claims & Cross-Checking" in report.synthesis_markdown


class TestEngineeringIntelligence:
    def test_calculators_and_bom(self, temp_dir):
        eng = EngineeringIntelligence(base_dir=temp_dir)

        # Voltage divider: 12V with 10k and 3.3k -> 12 * 3.3 / 13.3 = 2.9774 V
        vd = eng.calculate_voltage_divider(12.0, 10000.0, 3300.0)
        assert 2.97 < vd.results["vout_v"] < 2.99
        assert vd.results["current_ma"] > 0

        # Buck regulator: 5V target with R1=1000 -> R2 = 1000*(5/1.23 - 1) = 3065 ohms
        buck = eng.calculate_buck_feedback(5.0, 1000.0)
        assert 3060.0 < buck.results["r2_ohms"] < 3070.0

        # RC Cutoff: 1k ohm, 100nF -> fc = 1 / (2*pi*1000*1e-7) = 1591.55 Hz
        rc = eng.calculate_rc_cutoff(1000.0, 1e-7)
        assert 1585.0 < rc.results["cutoff_frequency_hz"] < 1595.0

        # Bolt Circle
        bc = eng.calculate_bolt_circle(pcd_mm=100.0, num_holes=4, bolt_size="M6")
        assert len(bc.results["hole_coordinates"]) == 4

        # BOM Generation
        items = eng.generate_standard_regulator_bom("Power Module")
        assert len(items) >= 5
        bom_md = eng.format_bom_markdown("Power Module", items)
        assert "LM2596" in bom_md
        assert "**Total**" in bom_md


class TestReliabilityAndDiagnostics:
    def test_subsystem_health_and_summary(self, temp_dir):
        monitor = HealthMonitor(base_dir=temp_dir)
        results = monitor.run_full_diagnostics()
        assert len(results) >= 5

        summary = monitor.get_system_summary()
        assert summary["overall_status"] in ("HEALTHY", "DEGRADED", "UNHEALTHY")
        assert summary["total_subsystems"] >= 5
