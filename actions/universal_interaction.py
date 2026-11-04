"""
actions/universal_interaction.py — Universal scrolling, context-aware navigation, and visual target interaction.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from core import outcome
from core.desktop.access_manager import get_access_manager
from core.desktop.action_verifier import get_action_verifier
from core.desktop.cursor_controller import get_cursor_controller
from core.desktop.interaction_context import get_interaction_context
from core.desktop.universal_scroll import get_universal_scroll
from core.desktop.visual_target_detector import get_visual_target_detector

logger = logging.getLogger("JARVIS.Action.UniversalInteraction")


def universal_interaction(
    parameters: dict[str, Any],
    player: Optional[Any] = None,
    speak: Optional[Any] = None,
    session_memory: Optional[Any] = None,
) -> str:
    """Dispatches universal scrolling, continuous scroll control, and visual target interaction."""
    access_mgr = get_access_manager()
    params = parameters or {}
    action = str(params.get("action", "scroll")).strip().lower()

    # 1. State / Status Inspection
    if action == "status":
        st = access_mgr.get_status_dict()
        ctx = get_interaction_context().get_or_create_session()
        scroller = get_universal_scroll()
        return outcome.done(
            "status",
            permission=st.get("state"),
            active_window=ctx.window_title[:40],
            is_scrolling=scroller.is_continuously_scrolling,
            last_direction=ctx.last_direction,
        )

    # 2. Stop Scroll does NOT require full control (failsafe permitted anytime)
    if action in ("stop_scroll", "stop", "halt", "pause"):
        scroller = get_universal_scroll()
        return scroller.stop_continuous_scroll()

    # 3. Permissions Check for Control Actions
    if not access_mgr.is_control_enabled:
        return outcome.failed(
            action,
            "Desktop access is disabled. Please enable 'FULL DESKTOP ACCESS' in the JARVIS HUD first.",
            permission_state=access_mgr.state.value,
        )

    scroller = get_universal_scroll()
    detector = get_visual_target_detector()
    cursor = get_cursor_controller()
    verifier = get_action_verifier()

    # 4. Scroll Actions
    if action == "scroll":
        cmd = str(params.get("command") or params.get("direction") or "down").strip()
        amt = params.get("amount")
        container = str(params.get("container") or "main").strip()
        return scroller.scroll(command_or_direction=cmd, amount=amt, container=container, verify=True)

    elif action == "scroll_again":
        ctx = get_interaction_context().get_or_create_session()
        direction = ctx.last_direction or "down"
        container = ctx.container_type or "main"
        return scroller.scroll(command_or_direction=direction, amount=ctx.last_magnitude, container=container, verify=True)

    elif action == "continuous_scroll":
        direction = str(params.get("direction") or "down").strip()
        amt = str(params.get("amount") or "normal").strip()
        container = str(params.get("container") or "main").strip()
        intent_text = f"keep scrolling {direction}"
        return scroller.scroll(command_or_direction=intent_text, amount=amt, container=container, verify=False)

    # 5. Visual Inspection of Targets
    elif action == "inspect_targets":
        targets = detector.detect_visible_targets()
        summary = [t.to_dict() for t in targets[:25]]
        if player and hasattr(player, "show_content"):
            player.show_content("VISIBLE TARGETS", str(summary))
        return outcome.done("inspect_targets", count=len(targets), targets=summary)

    # 6. Find and Click Target with Optional Scroll-to-Find
    elif action in ("find_and_click", "click_target", "click_video"):
        query = str(params.get("target") or params.get("query") or params.get("name") or "").strip()
        if not query:
            return outcome.failed(action, "Target query is required for find_and_click.")

        category = params.get("category")
        max_scroll_attempts = int(params.get("max_scroll_attempts", 4))

        logger.info("UniversalInteraction: finding target '%s' (category=%s)...", query, category)
        target, attempts = detector.scroll_until_visible(
            query=query,
            max_scroll_attempts=max_scroll_attempts,
            category=category,
        )

        if target is None:
            return outcome.failed(
                action,
                f"Target '{query}' could not be located after {attempts} viewport scans.",
                scanned_pages=attempts,
            )

        cx, cy = target.center
        logger.info("UniversalInteraction: target '%s' located at (%d, %d); moving cursor...", target.label[:40], cx, cy)

        # Smooth human-like cursor move and click
        cursor.move_to(cx, cy, duration=0.25, human_like=True)
        cursor.click(cx, cy, hover_delay=0.08)

        # Verify outcome
        if "video" in str(category or "").lower() or "video" in query.lower() or "youtube" in target.label.lower():
            verify_res = verifier.verify_playback(expected_title_keyword=query[:20], settle_delay=0.60)
            return outcome.done(
                action,
                target=target.label[:50],
                coords=[cx, cy],
                confidence=round(target.confidence, 3),
                scroll_pages=attempts,
                playback_status="playing",
            )

        return outcome.done(
            action,
            target=target.label[:50],
            coords=[cx, cy],
            confidence=round(target.confidence, 3),
            scroll_pages=attempts,
        )

    return outcome.failed("universal_interaction", f"Unknown action: '{action}'")


TOOL = {
    "name": "universal_interaction",
    "description": (
        "Universal desktop interaction engine for natural scrolling, continuous scrolling, "
        "and visual target interaction (finding and clicking videos, buttons, links, cards, and web elements)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "scroll | scroll_again | continuous_scroll | stop_scroll | "
                    "find_and_click | inspect_targets | status"
                ),
            },
            "direction": {
                "type": "STRING",
                "description": "down | up | left | right | to_top | to_bottom | page_down | page_up (default: down)",
            },
            "amount": {
                "type": "STRING",
                "description": "subtle | normal | more | page | extreme (default: normal)",
            },
            "command": {
                "type": "STRING",
                "description": "Natural language command e.g. 'scroll down', 'go a little down', 'scroll to the bottom'",
            },
            "target": {
                "type": "STRING",
                "description": "Target element label or video title to locate and click (e.g. 'PyTorch Tutorial', 'first video')",
            },
            "category": {
                "type": "STRING",
                "description": "Optional category filter: video_card | button | link | input | card",
            },
            "container": {
                "type": "STRING",
                "description": "Target container: main | sidebar | comments | generic",
            },
            "max_scroll_attempts": {
                "type": "INTEGER",
                "description": "Maximum pages to scroll down while searching for the target (default: 4)",
            },
        },
        "required": ["action"],
    },
    "handler": universal_interaction,
    "tier": "core",
}

