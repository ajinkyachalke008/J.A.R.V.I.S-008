"""
tests/test_universal_interaction.py — Comprehensive test suite for Universal Scroll,
Context-Aware Navigation, and Visual Target Interaction in J.A.R.V.I.S. — 008.
"""
import threading
import time
from unittest.mock import MagicMock, patch
import pytest

from core.desktop.access_manager import DesktopAccessManager, DesktopAccessState, get_access_manager
from core.desktop.action_verifier import ActionVerifier
from core.desktop.emergency_stop import get_emergency_stop
from core.desktop.interaction_context import InteractionContextManager, InteractionSession
from core.desktop.scroll_intent import (
    ContainerTarget,
    ScrollDirection,
    ScrollIntent,
    ScrollMagnitude,
    parse_scroll_intent,
)
from core.desktop.universal_scroll import (
    UniversalScrollEngine,
    WHEEL_DELTA,
    _DELTA_MAP,
)
from core.desktop.visual_target_detector import (
    VisualTarget,
    VisualTargetDetector,
    calculate_semantic_similarity,
)
from actions.universal_interaction import universal_interaction
from actions.desktop_agent import desktop_agent


@pytest.fixture(autouse=True)
def setup_access_state():
    mgr = get_access_manager()
    es = get_emergency_stop()
    es.stop_watchdog()
    mgr.revoke("fixture_reset")
    mgr.enable_full_control()
    # Prevent physical hardware mouse corner from tripping watchdog during unit testing
    with patch.object(es, "start_watchdog"):
        with patch("pyautogui.position", return_value=(960, 540)):
            yield
    es.stop_watchdog()
    mgr.revoke("fixture_teardown")


# ── 1. Intent Parser Tests ───────────────────────────────────────────────────

class TestScrollIntentParser:
    def test_downward_natural_language(self):
        cases = [
            ("scroll down", ScrollDirection.DOWN, ScrollMagnitude.NORMAL),
            ("scroll down again", ScrollDirection.DOWN, ScrollMagnitude.NORMAL),
            ("go a little down", ScrollDirection.DOWN, ScrollMagnitude.SUBTLE),
            ("move down", ScrollDirection.DOWN, ScrollMagnitude.NORMAL),
            ("scroll further", ScrollDirection.DOWN, ScrollMagnitude.MORE),
            ("go to the bottom", ScrollDirection.TO_BOTTOM, ScrollMagnitude.EXTREME),
            ("scroll to the next section", ScrollDirection.PAGE_DOWN, ScrollMagnitude.PAGE),
            ("move down a little more", ScrollDirection.DOWN, ScrollMagnitude.SUBTLE),
        ]
        for cmd, exp_dir, exp_mag in cases:
            intent = parse_scroll_intent(cmd)
            assert intent.direction == exp_dir, f"Failed direction for '{cmd}' (got {intent.direction})"
            assert intent.magnitude == exp_mag, f"Failed magnitude for '{cmd}' (got {intent.magnitude})"
            assert not intent.is_stop

    def test_upward_natural_language(self):
        cases = [
            ("scroll up", ScrollDirection.UP, ScrollMagnitude.NORMAL),
            ("go back up", ScrollDirection.UP, ScrollMagnitude.NORMAL),
            ("move slightly up", ScrollDirection.UP, ScrollMagnitude.SUBTLE),
            ("scroll to the top", ScrollDirection.TO_TOP, ScrollMagnitude.EXTREME),
            ("show me the previous section", ScrollDirection.PAGE_UP, ScrollMagnitude.PAGE),
        ]
        for cmd, exp_dir, exp_mag in cases:
            intent = parse_scroll_intent(cmd)
            assert intent.direction == exp_dir, f"Failed direction for '{cmd}' (got {intent.direction})"
            assert intent.magnitude == exp_mag, f"Failed magnitude for '{cmd}' (got {intent.magnitude})"

    def test_magnitude_and_continuous_modes(self):
        # Continuous
        intent_cont = parse_scroll_intent("keep scrolling down")
        assert intent_cont.is_continuous
        assert intent_cont.direction == ScrollDirection.DOWN

        intent_until_stop = parse_scroll_intent("scroll slowly until I tell you to stop")
        assert intent_until_stop.is_continuous
        assert intent_until_stop.magnitude == ScrollMagnitude.SUBTLE

        # Stop
        intent_stop1 = parse_scroll_intent("stop scrolling")
        assert intent_stop1.is_stop

        intent_stop2 = parse_scroll_intent("halt")
        assert intent_stop2.is_stop

        # Repetition
        intent_rep = parse_scroll_intent("scroll down again")
        assert intent_rep.is_repeat

    def test_container_targeting(self):
        intent_sidebar = parse_scroll_intent("scroll down the left sidebar")
        assert intent_sidebar.container == ContainerTarget.SIDEBAR

        intent_comments = parse_scroll_intent("scroll the comments")
        assert intent_comments.container == ContainerTarget.COMMENTS

        intent_main = parse_scroll_intent("scroll down the main feed")
        assert intent_main.container == ContainerTarget.MAIN


# ── 2. Interaction Context Tests ─────────────────────────────────────────────

class TestInteractionContext:
    def test_session_lifecycle_and_invalidation(self):
        mgr = InteractionContextManager()
        # Mock active window info: HWND 12345, "YouTube - Google Chrome"
        with patch.object(mgr, "get_active_window_info", return_value=(12345, "YouTube - Google Chrome", (100, 100, 1380, 820))):
            sess1 = mgr.get_or_create_session()
            assert sess1.active_hwnd == 12345
            assert sess1.app_name == "YouTube"
            assert sess1.is_valid()

            # Second call in same window reuses session
            sess2 = mgr.get_or_create_session()
            assert sess2 is sess1

        # Switching window invalidates context
        with patch.object(mgr, "get_active_window_info", return_value=(99999, "Untitled - Notepad", (200, 200, 800, 600))):
            sess3 = mgr.get_or_create_session()
            assert sess3.active_hwnd == 99999
            assert sess3.app_name == "DesktopApp"
            assert sess3 is not sess1

    def test_centroid_resolution(self):
        mgr = InteractionContextManager()
        # Window bounds: left=0, top=0, right=1000, bottom=800 -> w=1000, h=800
        with patch.object(mgr, "get_active_window_info", return_value=(111, "Test Browser", (0, 0, 1000, 800))):
            # Main viewport centroid: X ~50%, Y ~55% (to avoid headers)
            cx, cy = mgr.get_target_centroid("main")
            assert cx == 500
            assert cy == 440

            # Sidebar centroid: X ~12%, Y ~50%
            sx, sy = mgr.get_target_centroid("sidebar")
            assert sx == 120
            assert sy == 400

            # Comments centroid: X ~80%, Y ~50%
            comm_x, comm_y = mgr.get_target_centroid("comments")
            assert comm_x == 800
            assert comm_y == 400

    def test_repeated_scroll_chaining(self):
        mgr = InteractionContextManager()
        with patch.object(mgr, "get_active_window_info", return_value=(111, "Feed", (0, 0, 1000, 800))):
            mgr.update_scroll_state(direction="up", magnitude="subtle", container_type="sidebar")
            sess = mgr.get_or_create_session()
            assert sess.last_direction == "up"
            assert sess.last_magnitude == "subtle"
            assert sess.container_type == "sidebar"


# ── 3. Universal Scroll Engine Tests ─────────────────────────────────────────

class TestUniversalScrollEngine:
    def test_wheel_delta_calibration(self):
        assert WHEEL_DELTA == 120
        assert _DELTA_MAP[ScrollMagnitude.SUBTLE] >= 120
        assert _DELTA_MAP[ScrollMagnitude.NORMAL] == 600  # 5 notches
        assert _DELTA_MAP[ScrollMagnitude.MORE] == 1200   # 10 notches
        assert _DELTA_MAP[ScrollMagnitude.PAGE] == 1800   # 15 notches

    def test_permission_guard(self):
        engine = UniversalScrollEngine()
        # Force disabled state
        engine._access_mgr.revoke("test")
        res = engine.scroll(command_or_direction="down")
        assert "status=failed" in res
        assert "Desktop access is disabled" in res

    def test_continuous_scroll_lifecycle_and_stop(self):
        engine = UniversalScrollEngine()
        engine._access_mgr.enable_full_control()

        # Stop when idle returns status=idle
        idle_res = engine.stop_continuous_scroll()
        assert "status=idle" in idle_res

        # Start continuous scroll
        with patch.object(engine, "_dispatch_scroll_event", return_value=True):
            with patch.object(engine, "_ensure_cursor_positioned"):
                start_res = engine.scroll(command_or_direction="keep scrolling down", verify=False)
                assert "status=scrolling" in start_res
                assert engine.is_continuously_scrolling

                time.sleep(0.12)
                # Halt continuous scroll
                stop_res = engine.stop_continuous_scroll()
                assert "status=halted" in stop_res
                assert not engine.is_continuously_scrolling


# ── 4. Visual Target Grounding Tests ─────────────────────────────────────────

class TestVisualTargetGrounding:
    def test_semantic_similarity_matching(self):
        # Exact match
        assert calculate_semantic_similarity("Subscribe", "Subscribe") == 1.0

        # Substring / partial
        sim_sub = calculate_semantic_similarity("PyTorch neural networks", "PyTorch Neural Networks Tutorial 2026")
        assert sim_sub >= 0.70

        # Disjoint strings
        sim_low = calculate_semantic_similarity("Cooking recipe lasagna", "How to install Arch Linux")
        assert sim_low < 0.25

    def test_ordinal_video_card_selection(self):
        detector = VisualTargetDetector()
        mock_targets = [
            VisualTarget(label="Video A: Intro to AI", category="video_card", rect=(100, 100, 300, 200)),
            VisualTarget(label="Video B: Deep Learning", category="video_card", rect=(100, 350, 300, 200)),
            VisualTarget(label="Video C: Transformers", category="video_card", rect=(100, 600, 300, 200)),
        ]

        # First video
        t1 = detector.find_target("first video", targets=mock_targets)
        assert t1 is not None
        assert t1.label == "Video A: Intro to AI"

        # Second video
        t2 = detector.find_target("second video", targets=mock_targets)
        assert t2 is not None
        assert t2.label == "Video B: Deep Learning"

        # 3rd video
        t3 = detector.find_target("3rd video", targets=mock_targets)
        assert t3 is not None
        assert t3.label == "Video C: Transformers"

    def test_scroll_until_visible_loop(self):
        detector = VisualTargetDetector()
        mock_target = VisualTarget(label="PyTorch Tutorial", category="video_card", rect=(200, 300, 400, 220))

        # Scenario: target appears on the 2nd attempt
        attempts_counter = 0

        def _mock_find(query, category=None, min_confidence=0.5, targets=None):
            nonlocal attempts_counter
            attempts_counter += 1
            if attempts_counter >= 2:
                return mock_target
            return None

        with patch.object(detector, "find_target", side_effect=_mock_find):
            with patch("core.desktop.universal_scroll.UniversalScrollEngine.scroll", return_value="done"):
                target, attempts = detector.scroll_until_visible("PyTorch Tutorial", max_scroll_attempts=4)
                assert target is not None
                assert target.label == "PyTorch Tutorial"
                assert attempts == 2


# ── 5. Action Verifier Tests ─────────────────────────────────────────────────

class TestActionVerifier:
    def test_scroll_boundary_detection(self):
        verifier = ActionVerifier()
        # Mock window snapshot unchanging
        with patch.object(verifier, "get_window_snapshot", return_value={"hwnd": 1, "title": "Static Page"}):
            # Callable that does not change anything
            res = verifier.verify_action(
                action_name="scroll_down",
                target_desc="Static Page (main)",
                action_callable=lambda: True,
                region=None,
            )
            # Boundary or static reached
            assert "possible_edge" in res or "status=unverified" in res

    def test_youtube_playback_verification(self):
        verifier = ActionVerifier()
        with patch.object(verifier, "get_window_snapshot", return_value={"hwnd": 1, "title": "PyTorch Tutorial - YouTube"}):
            res = verifier.verify_playback(expected_title_keyword="PyTorch")
            assert "status=playing" in res


# ── 6. Tool Integration & End-to-End Action Execution ────────────────────────

class TestUniversalInteractionTool:
    def test_status_action(self):
        mgr = get_access_manager()
        mgr.enable_full_control()
        res = universal_interaction({"action": "status"})
        assert "status=done" in res
        assert "action=status" in res

    def test_stop_scroll_available_without_full_control(self):
        # stop_scroll is an immediate failsafe allowed anytime
        res = universal_interaction({"action": "stop_scroll"})
        assert "status=done" in res
        assert "status=idle" in res or "status=halted" in res

    def test_find_and_click_execution(self):
        access_mgr = get_access_manager()
        access_mgr.enable_full_control()

        mock_target = VisualTarget(label="Subscribe Button", category="button", rect=(500, 300, 120, 40), confidence=0.92)

        with patch("core.desktop.visual_target_detector.VisualTargetDetector.scroll_until_visible", return_value=(mock_target, 1)):
            with patch("core.desktop.cursor_controller.CursorController.move_to", return_value=True):
                with patch("core.desktop.cursor_controller.CursorController.click", return_value=True):
                    with patch("core.desktop.action_verifier.ActionVerifier.verify_playback", return_value="done"):
                        res = universal_interaction({
                            "action": "find_and_click",
                            "target": "Subscribe",
                            "category": "button",
                        })
                        assert "status=done" in res
                        assert "Subscribe Button" in res
                        assert "[560, 320]" in res  # centroid of (500, 300, 120, 40)

    def test_desktop_agent_integration(self):
        access_mgr = get_access_manager()
        access_mgr.enable_full_control()

        with patch("core.desktop.universal_scroll.UniversalScrollEngine.scroll", return_value="status=done action=\"scroll_down\""):
            res = desktop_agent({"action": "scroll", "direction": "down"})
            assert "status=done" in res
