"""
actions/multimodal_companion_action.py — Real-time multimodal screen companion action for J.A.R.V.I.S. — 008.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from core import outcome
from core.desktop.multimodal_companion import get_multimodal_companion

logger = logging.getLogger("JARVIS.Action.MultimodalCompanion")


def multimodal_companion_action(
    parameters: dict[str, Any],
    player: Optional[Any] = None,
    speak: Optional[Any] = None,
    session_memory: Optional[Any] = None,
) -> str:
    """Dispatches on-demand screen understanding, before-and-after change analysis, and continuous awareness."""
    params = parameters or {}
    action = str(params.get("action", "look_at_screen")).strip().lower()
    query = str(params.get("query") or params.get("instruction") or "Explain what is on my screen in detail").strip()

    companion = get_multimodal_companion()

    # 1. On-Demand Perception ("Look at my screen", "What am I looking at?")
    if action in ("look_at_screen", "analyze_screen", "inspect_screen", "read_screen"):
        if speak:
            speak("Looking at your screen now, sir.")
        res = companion.analyze_screen(query=query)
        if res.get("status") == "SUCCESS":
            analysis = res.get("analysis", "")
            if player and hasattr(player, "show_content"):
                player.show_content("SCREEN ANALYSIS", analysis)
            return outcome.done(
                "look_at_screen",
                app=res.get("app_name"),
                window=res.get("window_title"),
                analysis=analysis[:120],
                spoken_response=analysis,
            )
        return outcome.failed("look_at_screen", res.get("error", "Failed to capture or analyze screen."))

    # 2. Before-and-After Semantic Change ("Tell me what changed", "What changed?")
    elif action in ("what_changed", "screen_diff", "check_changes"):
        summary = companion.what_changed()
        if player and hasattr(player, "show_content"):
            player.show_content("SCREEN CHANGES", summary)
        return outcome.done("what_changed", change_summary=summary, spoken_response=summary)

    # 3. Mode C — User-Authorized Continuous Awareness ("Watch this screen while I work")
    elif action in ("watch_screen", "start_screen_watch", "continuous_awareness"):
        interval = float(params.get("interval", 6.0))
        return companion.start_continuous_awareness(interval_seconds=interval)

    elif action in ("pause_screen_watch", "pause_awareness"):
        return companion.pause_continuous_awareness()

    elif action in ("stop_screen_watch", "stop_awareness"):
        return companion.stop_continuous_awareness()

    # 4. Diagram & Error Explanation
    elif action in ("explain_diagram", "explain_error", "circuit_analysis"):
        if speak:
            speak("Analyzing the diagram on your screen, sir.")
        specific_query = query if query != "Explain what is on my screen in detail" else "Explain the technical diagram, circuit connections, or error message on screen in detail."
        res = companion.analyze_screen(query=specific_query)
        if res.get("status") == "SUCCESS":
            analysis = res.get("analysis", "")
            if player and hasattr(player, "show_content"):
                player.show_content("DIAGRAM EXPLANATION", analysis)
            return outcome.done("explain_diagram", analysis=analysis[:120], spoken_response=analysis)
        return outcome.failed("explain_diagram", res.get("error", "Diagram analysis failed."))

    return outcome.failed("multimodal_companion", f"Unknown action: '{action}'")


TOOL = {
    "name": "multimodal_companion",
    "description": (
        "Real-time multimodal screen companion. Use when the user asks to look at their screen, "
        "explain what is on screen, check what changed after scrolling, explain a diagram or error, "
        "or watch the screen while working."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "look_at_screen | what_changed | explain_diagram | "
                    "watch_screen | pause_screen_watch | stop_screen_watch"
                ),
            },
            "query": {
                "type": "STRING",
                "description": "Specific question or instruction about the screen, diagram, or error.",
            },
            "interval": {
                "type": "NUMBER",
                "description": "Sampling interval in seconds for continuous awareness (default: 6.0).",
            },
        },
        "required": ["action"],
    },
    "handler": multimodal_companion_action,
    "tier": "core",
}

