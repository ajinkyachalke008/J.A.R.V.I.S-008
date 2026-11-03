"""
tests/test_antigravity_integration.py — Verification suite for Antigravity IDE Integration.

Tests:
- Process identification and ancestor separation in appidentity.py
- focus_window implementation in appidentity.py
- AntigravityController window detection and prompt delivery
- Clipboard preservation guarantee (user clipboard restored after injection)
- Submit mode vs insert-only mode
- Error handling when Antigravity IDE is offline or prompt is empty
- actions/antigravity_chat action handler and TOOL schema verification
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from actions.antigravity_chat import antigravity_chat, TOOL
from core import appidentity
from core.integrations.antigravity_controller import (
    AntigravityController,
    get_antigravity_controller,
)


class TestAppIdentityFix:
    def test_own_exes_excludes_external_ides(self):
        """Verify that own_exes only contains python and child processes, not ancestor IDEs."""
        exes = appidentity.own_exes()
        for path in exes:
            path_lower = path.lower()
            assert "antigravity" not in path_lower, f"Antigravity should not be in own_exes: {path}"
            assert "explorer.exe" not in path_lower, f"explorer.exe should not be in own_exes: {path}"

    def test_running_antigravity_not_marked_as_self(self):
        """Verify that running('antigravity') finds running instances without false is_self filtering."""
        matches = appidentity.running("antigravity")
        if matches:
            for m in matches:
                assert not m.is_self, "External Antigravity IDE process must not be flagged is_self=True"

    def test_focus_window_handles_empty_title(self):
        """Verify focus_window gracefully rejects empty string."""
        assert appidentity.focus_window("") is False
        assert appidentity.focus_window("   ") is False


class TestAntigravityController:
    @pytest.fixture
    def controller(self):
        return AntigravityController()

    def test_singleton_accessor(self):
        """Verify get_antigravity_controller returns singleton."""
        c1 = get_antigravity_controller()
        c2 = get_antigravity_controller()
        assert c1 is c2

    def test_deliver_prompt_empty_validation(self, controller):
        """Empty prompt with focus_only=False must return failure."""
        res = controller.deliver_prompt("")
        assert res["success"] is False
        assert "No prompt" in res["error"]

    def test_deliver_prompt_when_offline(self, controller):
        """When IDE is not running, deliver_prompt returns clear error."""
        with patch.object(controller, "is_running", return_value=False):
            res = controller.deliver_prompt("Create a test function")
            assert res["success"] is False
            assert "not running" in res["error"]

    def test_deliver_prompt_insert_only(self, controller):
        """Verify prompt delivery in insert-only mode preserves clipboard and does not send enter."""
        mock_pyperclip = MagicMock()
        mock_pyautogui = MagicMock()
        mock_pyperclip.paste.return_value = "ORIGINAL_USER_CLIPBOARD_DATA"

        with patch.object(controller, "is_running", return_value=True), \
             patch.object(controller, "focus_window", return_value=True), \
             patch.object(controller, "focus_chat_input", return_value=True), \
             patch("core.integrations.antigravity_controller.pyperclip", mock_pyperclip), \
             patch("core.integrations.antigravity_controller.pyautogui", mock_pyautogui):

            res = controller.deliver_prompt("Write a binary search algorithm", submit=False)

            assert res["success"] is True
            assert res["action"] == "deliver_prompt"
            assert res["submitted"] is False
            assert res["chars"] == len("Write a binary search algorithm")

            # Check copy and paste were called
            mock_pyperclip.copy.assert_any_call("Write a binary search algorithm")
            mock_pyautogui.hotkey.assert_any_call("ctrl", "v")

            # Check Enter was NOT pressed in insert-only mode
            enter_calls = [c for c in mock_pyautogui.press.call_args_list if c[0] == ("enter",)]
            assert len(enter_calls) == 0, "Enter must not be pressed when submit=False"

            # Check clipboard restoration
            mock_pyperclip.copy.assert_called_with("ORIGINAL_USER_CLIPBOARD_DATA")

    def test_deliver_prompt_with_submit(self, controller):
        """Verify prompt delivery with submit=True sends enter key."""
        mock_pyperclip = MagicMock()
        mock_pyautogui = MagicMock()
        mock_pyperclip.paste.return_value = "ORIGINAL_DATA"

        with patch.object(controller, "is_running", return_value=True), \
             patch.object(controller, "focus_window", return_value=True), \
             patch.object(controller, "focus_chat_input", return_value=True), \
             patch("core.integrations.antigravity_controller.pyperclip", mock_pyperclip), \
             patch("core.integrations.antigravity_controller.pyautogui", mock_pyautogui):

            res = controller.deliver_prompt("Refactor the auth service", submit=True)

            assert res["success"] is True
            assert res["submitted"] is True
            mock_pyautogui.press.assert_called_with("enter")
            # Verify clipboard restoration
            mock_pyperclip.copy.assert_called_with("ORIGINAL_DATA")

    def test_focus_only_mode(self, controller):
        """Verify focus_only focuses without copying or pasting prompt."""
        mock_pyperclip = MagicMock()
        mock_pyautogui = MagicMock()

        with patch.object(controller, "is_running", return_value=True), \
             patch.object(controller, "focus_window", return_value=True), \
             patch.object(controller, "focus_chat_input", return_value=True), \
             patch("core.integrations.antigravity_controller.pyperclip", mock_pyperclip), \
             patch("core.integrations.antigravity_controller.pyautogui", mock_pyautogui):

            res = controller.deliver_prompt("", focus_only=True)
            assert res["success"] is True
            assert res["action"] == "focus_only"
            assert mock_pyperclip.copy.call_count == 0


class TestAntigravityActionTool:
    def test_tool_declaration_schema(self):
        """Verify TOOL schema complies with LiveConnect / action_loader requirements."""
        assert TOOL["name"] == "antigravity_chat"
        assert "parameters" in TOOL
        assert TOOL["parameters"]["type"] == "OBJECT"
        assert "prompt" in TOOL["parameters"]["properties"]
        assert "submit" in TOOL["parameters"]["properties"]
        assert "focus_only" in TOOL["parameters"]["properties"]
        assert "prompt" in TOOL["parameters"]["required"]
        assert TOOL["tier"] == "core"

    def test_action_handler_execution(self):
        """Verify antigravity_chat handler delegates to controller and returns formatted outcome."""
        mock_ctrl = MagicMock()
        mock_ctrl.deliver_prompt.return_value = {
            "success": True,
            "status": "done",
            "action": "deliver_prompt",
            "chars": 35,
            "submitted": False,
        }

        with patch("actions.antigravity_chat.get_antigravity_controller", return_value=mock_ctrl):
            raw = antigravity_chat({"prompt": "Hello Antigravity IDE", "submit": False})
            assert "status=done" in raw
            assert "action=inserted" in raw
            assert "chars=35" in raw

    def test_action_handler_missing_prompt(self):
        """Verify antigravity_chat handles missing prompt."""
        raw = antigravity_chat({})
        assert "status=failed" in raw
        assert "No prompt was provided" in raw

