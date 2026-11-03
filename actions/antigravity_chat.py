"""
actions/antigravity_chat.py — Direct Agent Chat input delivery for Google Antigravity IDE.

Allows J.A.R.V.I.S. — 008 to insert or submit prompts, instructions, code, or queries
directly into the Google Antigravity IDE agent conversation interface.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from core import outcome
from core.integrations.antigravity_controller import get_antigravity_controller

logger = logging.getLogger("JARVIS.Action.AntigravityChat")


def antigravity_chat(
    parameters: dict[str, Any],
    player: Optional[Any] = None,
    session_memory: Optional[Any] = None,
) -> str:
    """
    Delivers a prompt into the Google Antigravity IDE agent chat input.

    Parameters:
    - prompt (str): The prompt text to deliver.
    - submit (bool, default False): If True, submits the prompt (presses Enter).
      If False, only inserts the prompt and leaves it in the input box for user review.
    - focus_only (bool, default False): If True, focuses Antigravity and the chat input
      without pasting any text.
    """
    controller = get_antigravity_controller()

    prompt = str(parameters.get("prompt", "") or parameters.get("text", "")).strip()
    submit = bool(parameters.get("submit", False))
    focus_only = bool(parameters.get("focus_only", False))

    if not prompt and not focus_only:
        return outcome.failed(
            "antigravity_chat",
            "No prompt was provided to send to Antigravity IDE.",
        )

    res = controller.deliver_prompt(prompt=prompt, submit=submit, focus_only=focus_only)

    if not res.get("success", False):
        err_msg = res.get("error", "Failed to deliver prompt to Antigravity.")
        if player and hasattr(player, "write_log"):
            player.write_log(f"ERR: Antigravity - {err_msg}")
        return outcome.failed("antigravity_chat", err_msg)

    # Success feedback
    action_type = "submitted" if submit else "inserted"
    char_count = res.get("chars", len(prompt))
    summary = f"Prompt ({char_count} chars) {action_type} into Antigravity chat."

    if player and hasattr(player, "write_log"):
        player.write_log(f"JARVIS: {summary}")

    return outcome.done(
        "antigravity_chat",
        action=action_type,
        chars=char_count,
        submitted=submit,
        message=summary,
    )


TOOL = {
    "name": "antigravity_chat",
    "description": (
        "Send, insert, or submit prompts directly into the Google Antigravity IDE agent chat interface. "
        "Use this whenever the user asks to send a prompt to Antigravity, put text in the Antigravity chat, "
        "or submit an instruction to Antigravity. "
        "By default, prompt text is safely inserted into the chat input field without submitting (insert-only). "
        "Set submit=true only if the user explicitly asks to 'submit', 'send and run', or 'execute' the prompt."
    ),
    "brief": (
        "Inserts or submits prompts into Google Antigravity IDE agent chat. Set submit=true to press Enter."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "prompt": {
                "type": "STRING",
                "description": (
                    "The text, code, query, or instruction to insert into the Antigravity IDE agent chat input."
                ),
            },
            "submit": {
                "type": "BOOLEAN",
                "description": (
                    "Whether to automatically submit the prompt by pressing Enter after inserting (default: false). "
                    "When false, leaves the prompt in the input field for user inspection."
                ),
            },
            "focus_only": {
                "type": "BOOLEAN",
                "description": (
                    "If true, only focuses the Antigravity window and chat input without pasting text (default: false)."
                ),
            },
        },
        "required": ["prompt"],
    },
    "handler": antigravity_chat,
    "tier": "core",
}

