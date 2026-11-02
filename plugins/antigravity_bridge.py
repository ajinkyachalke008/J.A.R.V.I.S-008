"""
plugins/antigravity_bridge.py — Antigravity IDE Direct Input & Command Bridge for JARVIS.

Allows JARVIS to:
  1. Insert prompts directly into the user input field of Antigravity IDE's active chat window.
  2. Execute commands programmatically in Antigravity IDE's built-in integrated terminal.
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from core import outcome

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


def handle(args: Dict[str, Any], context: Any = None) -> outcome.Outcome:
    """Handles tool execution for Antigravity IDE direct input."""
    if antigravity_ide_api is None:
        return outcome.error(
            "The antigravity_ide_api module is not available in the current environment."
        )

    action = (args.get("action") or "").lower().strip()
    text = (args.get("text") or "").strip()
    submit = args.get("submit", True)

    if not text:
        return outcome.error("No text was provided for Antigravity IDE bridge action.")

    if action in ("insert_prompt", "chat", "prompt", "send_chat"):
        success = antigravity_ide_api.insert_prompt_to_chat(text, submit=submit)
        if success:
            action_desc = "inserted and submitted" if submit else "inserted into input field"
            return outcome.success(
                f"Successfully {action_desc} prompt to Antigravity IDE chat: '{text[:80]}...'"
            )
        else:
            return outcome.error(
                "Failed to insert prompt into Antigravity IDE. Ensure the IDE window is open."
            )

    elif action in ("execute_command", "terminal", "command", "run_terminal"):
        success = antigravity_ide_api.execute_terminal_command(text, submit=submit)
        if success:
            action_desc = "executed" if submit else "inserted"
            return outcome.success(
                f"Successfully {action_desc} command in Antigravity IDE terminal: '{text}'"
            )
        else:
            return outcome.error(
                "Failed to send command to Antigravity IDE terminal. Ensure the IDE window is open."
            )
    else:
        return outcome.error(
            f"Unknown action '{action}'. Valid actions are 'insert_prompt' and 'execute_command'."
        )
