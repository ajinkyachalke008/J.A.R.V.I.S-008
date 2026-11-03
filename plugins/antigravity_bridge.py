"""
plugins/antigravity_bridge.py — Antigravity IDE Direct Input & Command Bridge for JARVIS.

Allows JARVIS to:
  1. Insert prompts directly into the user input field of Antigravity IDE's active chat window.
  2. Execute commands programmatically in Antigravity IDE's built-in integrated terminal.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

try:
    import antigravity_ide_api
except ImportError:
    antigravity_ide_api = None

logger = logging.getLogger("AntigravityBridgePlugin")

PLUGIN = {
    "name": "antigravity_bridge",
    "description": (
        "Controls Google Antigravity IDE directly. Allows JARVIS to insert prompts into "
        "the active Antigravity chat window or execute terminal commands in the built-in terminal. "
        "Use for voice commands like 'ask Antigravity to write unit tests', 'send prompt to Antigravity', "
        "or 'run git status in Antigravity terminal'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action to perform: 'insert_prompt' (chat) or 'execute_command' (terminal).",
            },
            "text": {
                "type": "STRING",
                "description": "The prompt string to submit to chat or command line string to run in terminal.",
            },
            "submit": {
                "type": "BOOLEAN",
                "description": "Whether to simulate pressing Enter immediately (defaults to true).",
            },
        },
        "required": ["action", "text"],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    """
    Standard J.A.R.V.I.S. — 008 plugin entrypoint.
    Executes the requested action and returns a spoken response string for JARVIS.
    """
    if antigravity_ide_api is None:
        return "I couldn't access the Antigravity IDE API module. Please verify the environment installation."

    action = (parameters.get("action") or "").lower().strip()
    text = (parameters.get("text") or "").strip()
    submit = parameters.get("submit", True)

    if not text:
        return "No text or command was provided for Antigravity IDE."

    if player and hasattr(player, "say"):
        try:
            player.say("Interfacing with Antigravity IDE...")
        except Exception:
            pass

    if action in ("insert_prompt", "chat", "prompt", "send_chat"):
        success = antigravity_ide_api.insert_prompt_to_chat(text, submit=submit)
        if success:
            action_desc = "submitted" if submit else "inserted"
            return f"Prompt successfully {action_desc} into Antigravity IDE chat."
        else:
            return "Failed to insert prompt into Antigravity IDE. Please ensure the IDE window is open."

    elif action in ("execute_command", "terminal", "command", "run_terminal"):
        success = antigravity_ide_api.execute_terminal_command(text, submit=submit)
        if success:
            action_desc = "executed" if submit else "inserted"
            return f"Command '{text}' successfully {action_desc} in Antigravity IDE terminal."
        else:
            return "Failed to send command to Antigravity IDE terminal. Please ensure the IDE window is open."

    return f"Unknown Antigravity action '{action}'. Valid actions are 'insert_prompt' and 'execute_command'."


def handle(args: Dict[str, Any], context: Any = None) -> Any:
    """Legacy compatibility handler."""
    return run(args)
