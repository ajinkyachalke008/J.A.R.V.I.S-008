"""
tests/test_multimodal_companion.py — Automated test suite for Real-Time Multimodal Voice Companion,
Semantic Screen Diff, arXiv Research Client, Cross-App Mission Control Recipes, and Skill Builder.
"""
import io
import os
import shutil
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from PIL import Image

from core.desktop.access_manager import get_access_manager
from core.desktop.multimodal_companion import MultimodalCompanion, get_multimodal_companion
from core.desktop.screen_diff import (
    ScreenSnapshot,
    SemanticScreenDiff,
    SemanticScreenDiffEngine,
)
from core.intelligence.mission_control.recipe_runner import (
    CrossAppRecipeRunner,
    WorkflowExecutionReport,
    get_recipe_runner,
)
from core.intelligence.research.arxiv_client import ArxivClient, ArxivPaper
from core.intelligence.skills.skill_recipe_manager import (
    SkillRecipe,
    SkillRecipeManager,
    get_skill_recipe_manager,
)
from actions.multimodal_companion_action import multimodal_companion_action
from actions.mission_recipe_action import mission_recipe_action


@pytest.fixture(autouse=True)
def setup_access():
    mgr = get_access_manager()
    mgr.revoke("fixture_reset")
    mgr.enable_full_control()
    yield
    mgr.revoke("fixture_teardown")


# ── 1. arXiv Research Client Tests ───────────────────────────────────────────

class TestArxivClient:
    def test_atom_xml_parsing(self):
        sample_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <id>http://arxiv.org/abs/2401.99999v1</id>
            <published>2024-01-15T12:00:00Z</published>
            <title>
              Autonomous Multi-Agent Coordination Systems
            </title>
            <summary>
              This paper presents an empirical framework for peer-to-peer autonomous agent communication.
            </summary>
            <author>
              <name>Dr. Jane Doe</name>
            </author>
            <author>
              <name>Dr. John Smith</name>
            </author>
            <category term="cs.AI"/>
          </entry>
        </feed>"""

        client = ArxivClient()
        papers = client._parse_atom_response(sample_xml)
        assert len(papers) == 1
        p = papers[0]
        assert p.title == "Autonomous Multi-Agent Coordination Systems"
        assert p.authors == ["Dr. Jane Doe", "Dr. John Smith"]
        assert "empirical framework" in p.summary
        assert p.arxiv_id == "2401.99999v1"
        assert "Jane Doe et al. (2024)" in p.citation()

    def test_search_handles_network_failure(self):
        client = ArxivClient()
        with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
            res = client.search("quantum computing")
            assert res == []


# ── 2. Semantic Screen Diff Tests ────────────────────────────────────────────

class TestSemanticScreenDiff:
    def test_static_screen_detection(self):
        engine = SemanticScreenDiffEngine()
        snap1 = ScreenSnapshot(
            window_title="Doc - Word",
            app_name="Word",
            visible_texts=["Introduction", "Methods", "Results"],
            visual_hash="hash_123",
        )
        snap2 = ScreenSnapshot(
            window_title="Doc - Word",
            app_name="Word",
            visible_texts=["Introduction", "Methods", "Results"],
            visual_hash="hash_123",
        )
        diff = engine.compute_diff(snap1, snap2)
        assert not diff.has_changed
        assert "No visible screen changes detected" in diff.summary

    def test_scrolled_content_semantic_difference(self):
        engine = SemanticScreenDiffEngine()
        snap_pre = ScreenSnapshot(
            window_title="YouTube",
            app_name="YouTube",
            visible_texts=["Header", "Search", "Video 1: Machine Learning"],
            visible_elements=[{"name": "Video 1: Machine Learning", "type": "card"}],
            visual_hash="hash_aaa",
        )
        snap_post = ScreenSnapshot(
            window_title="YouTube",
            app_name="YouTube",
            visible_texts=["Header", "Search", "Video 4: Deep RL", "Video 5: Transformers"],
            visible_elements=[{"name": "Video 4: Deep RL", "type": "card"}, {"name": "Video 5: Transformers", "type": "card"}],
            visual_hash="hash_bbb",
        )
        diff = engine.compute_diff(snap_pre, snap_post)
        assert diff.has_changed
        assert len(diff.newly_visible_texts) == 2
        assert "Video 4: Deep RL" in diff.newly_visible_texts
        assert len(diff.newly_visible_elements) == 2
        assert "Video 4: Deep RL" in diff.summary


# ── 3. Multimodal Companion Perception Tests ─────────────────────────────────

class TestMultimodalCompanion:
    def test_mode_a_on_demand_screen_analysis(self):
        companion = MultimodalCompanion()
        dummy_img = Image.new("RGB", (640, 480), color=(30, 40, 50))

        mock_gemini_resp = MagicMock()
        mock_gemini_resp.text = "You are currently viewing a technical research paper on autonomous agents, sir."

        with patch("core.desktop.screen_capture.ScreenCaptureService.capture_active_window", return_value=(dummy_img, 0, 0)):
            with patch("core.gemini.call", return_value=mock_gemini_resp):
                res = companion.analyze_screen("What is on my screen?")
                assert res.get("status") == "SUCCESS"
                assert "autonomous agents" in res.get("analysis", "")

    def test_mode_b_action_triggered_diff_and_what_changed(self):
        companion = MultimodalCompanion()
        snap_a = ScreenSnapshot(window_title="Initial", visible_texts=["Item 1"])
        snap_b = ScreenSnapshot(window_title="Updated", visible_texts=["Item 1", "Item 2 (New)"])

        with patch.object(companion._diff_engine, "capture_snapshot", side_effect=[snap_a, snap_b]):
            diff = companion.explain_diff_after_action(lambda: None, action_name="scroll")
            assert diff.has_changed
            assert "Item 2 (New)" in diff.newly_visible_texts

    def test_mode_c_continuous_awareness_session_lifecycle(self):
        companion = MultimodalCompanion()
        dummy_snap = ScreenSnapshot(visual_hash="h1")

        with patch.object(companion._diff_engine, "capture_snapshot", return_value=dummy_snap):
            start_res = companion.start_continuous_awareness(interval_seconds=0.1)
            assert "status=done" in start_res
            assert companion.is_watching_screen

            pause_res = companion.pause_continuous_awareness()
            assert "status=done" in pause_res
            assert not companion.is_watching_screen

            stop_res = companion.stop_continuous_awareness()
            assert "status=done" in stop_res
            assert not companion.is_watching_screen


# ── 4. Cross-App Mission Recipe Runner Tests ─────────────────────────────────

class TestMissionRecipeRunner:
    def test_end_to_end_research_and_prototype_execution(self, tmp_path):
        runner = CrossAppRecipeRunner(base_workspace=tmp_path)

        mock_paper = ArxivPaper(
            title="Efficient Autonomous Planning",
            authors=["Alice Wonder"],
            summary="Novel task decomposition methods for robotics.",
            url="https://arxiv.org/abs/2401.11111",
            published_date="2024-01-01",
            arxiv_id="2401.11111",
        )

        with patch("core.intelligence.research.arxiv_client.ArxivClient.search", return_value=[mock_paper]):
            report = runner.execute_research_and_prototype_mission(
                topic="Autonomous Robotics",
                open_editor=False,
            )

            assert report.status == "COMPLETED"
            assert report.test_exit_code == 0
            assert report.test_passed >= 2
            assert report.test_failed == 0
            assert len(report.files_created) == 2
            assert Path(report.files_created[0]).exists()
            assert Path(report.files_created[1]).exists()
            assert "Alice Wonder" in report.research_summary
            assert "Mission completed" in report.spoken_summary


# ── 5. Skill Builder & Recipe Manager Tests ──────────────────────────────────

class TestSkillRecipeManager:
    def test_save_and_retrieve_skill_from_mission(self, tmp_path):
        recipe_file = tmp_path / "skill_recipes.json"
        mgr = SkillRecipeManager(recipes_file=recipe_file)

        recipe = mgr.save_recipe_from_mission(
            name="Robotics Prototype Skill",
            topic="Robotics Navigation",
            trigger_phrases=["run robotics prototype", "build robotics demo"],
        )

        assert recipe.skill_id == "robotics_prototype_skill"
        assert "run robotics prototype" in recipe.trigger_phrases
        assert recipe.status == "ACTIVE"

        # Match trigger
        match = mgr.find_skill_by_trigger("Jarvis, run robotics prototype for warehouse drones")
        assert match is not None
        matched_recipe, params = match
        assert matched_recipe.skill_id == "robotics_prototype_skill"
        assert params.get("topic") == "warehouse drones"

    def test_execute_saved_skill(self, tmp_path):
        recipe_file = tmp_path / "skill_recipes.json"
        mgr = SkillRecipeManager(recipes_file=recipe_file)

        mock_report = WorkflowExecutionReport(
            mission_id="m123",
            topic="Power Grid AI",
            workspace_path=str(tmp_path),
            test_passed=3,
            test_failed=0,
            status="COMPLETED",
            spoken_summary="Mission completed successfully.",
        )

        with patch("core.intelligence.mission_control.recipe_runner.CrossAppRecipeRunner.execute_research_and_prototype_mission", return_value=mock_report):
            res = mgr.execute_skill("ai_research_and_prototype", inputs={"topic": "Power Grid AI"})
            assert res.get("status") == "SUCCESS"
            assert res.get("topic") == "Power Grid AI"
            assert "Mission completed" in res.get("spoken_summary")


# ── 6. Tool Action Integration Tests ─────────────────────────────────────────

class TestCompanionAndRecipeActions:
    def test_multimodal_companion_action(self):
        mock_analysis = {"status": "SUCCESS", "app_name": "Chrome", "window_title": "Paper", "analysis": "Circuit diagram with 3 logic gates."}
        with patch("core.desktop.multimodal_companion.MultimodalCompanion.analyze_screen", return_value=mock_analysis):
            res = multimodal_companion_action({"action": "look_at_screen"})
            assert "status=done" in res
            assert "Circuit diagram" in res

        # What changed
        with patch("core.desktop.multimodal_companion.MultimodalCompanion.what_changed", return_value="Scrolled down; 2 new cards visible."):
            res_diff = multimodal_companion_action({"action": "what_changed"})
            assert "status=done" in res_diff
            assert "Scrolled down" in res_diff

    def test_mission_recipe_action(self, tmp_path):
        mock_report = WorkflowExecutionReport(
            mission_id="m_voice",
            topic="Deep Learning Agents",
            workspace_path=str(tmp_path),
            test_passed=2,
            test_failed=0,
            status="COMPLETED",
            spoken_summary="Mission completed for Deep Learning Agents.",
        )
        with patch("core.intelligence.mission_control.recipe_runner.CrossAppRecipeRunner.execute_research_and_prototype_mission", return_value=mock_report):
            res = mission_recipe_action({"action": "run_mission", "topic": "Deep Learning Agents", "open_editor": False})
            assert "status=done" in res
            assert "Deep Learning Agents" in res
            assert "passed=2" in res

        # Save as skill
        res_save = mission_recipe_action({"action": "save_as_skill", "name": "AI Agent Builder", "topic": "Deep Learning Agents"})
        assert "status=done" in res_save
        assert "AI Agent Builder" in res_save
