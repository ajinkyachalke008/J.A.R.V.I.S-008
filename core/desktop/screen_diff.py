"""
core/desktop/screen_diff.py — Semantic before-and-after screen change detection engine.
"""
from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from core.desktop.interaction_context import get_interaction_context
from core.desktop.ocr_engine import get_ocr_engine
from core.desktop.screen_capture import get_screen_capture
from core.desktop.ui_automation import get_ui_automation

logger = logging.getLogger("JARVIS.ScreenDiff")


@dataclass
class ScreenSnapshot:
    """A semantic and visual representation of the screen state at a specific point in time."""
    timestamp: float = field(default_factory=time.time)
    window_title: str = ""
    app_name: str = ""
    rect: Tuple[int, int, int, int] = (0, 0, 1920, 1080)
    visible_texts: List[str] = field(default_factory=list)
    visible_elements: List[Dict[str, Any]] = field(default_factory=list)
    visual_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "window_title": self.window_title,
            "app_name": self.app_name,
            "rect": list(self.rect),
            "visible_texts_count": len(self.visible_texts),
            "visible_elements_count": len(self.visible_elements),
            "visual_hash": self.visual_hash,
        }


@dataclass
class SemanticScreenDiff:
    """The computed difference between two screen snapshots with natural-language explanation."""
    has_changed: bool
    title_changed: bool
    newly_visible_texts: List[str]
    removed_texts: List[str]
    newly_visible_elements: List[Dict[str, Any]]
    summary: str

    def to_dict(self) -> dict:
        return {
            "has_changed": self.has_changed,
            "title_changed": self.title_changed,
            "newly_visible_count": len(self.newly_visible_texts),
            "removed_count": len(self.removed_texts),
            "new_elements_count": len(self.newly_visible_elements),
            "summary": self.summary,
        }


class SemanticScreenDiffEngine:
    """Captures baseline snapshots and generates semantic before-and-after change analysis."""

    def __init__(self):
        self._capture = get_screen_capture()
        self._ocr = get_ocr_engine()
        self._uia = get_ui_automation()
        self._context_mgr = get_interaction_context()

    def capture_snapshot(self, include_ocr: bool = True) -> ScreenSnapshot:
        """Captures a full semantic snapshot of the active window and viewport."""
        hwnd, title, rect = self._context_mgr.get_active_window_info()
        session = self._context_mgr.get_or_create_session()

        # 1. Gather interactive UI elements
        visible_elements: List[Dict[str, Any]] = []
        try:
            uia_elems = self._uia.get_active_window_elements(max_depth=4, max_elements=40)
            for el in uia_elems:
                if el.name and el.is_visible:
                    visible_elements.append({
                        "name": el.name.strip(),
                        "type": el.control_type,
                        "rect": list(el.rect),
                    })
        except Exception as e:
            logger.debug("UIA capture error during snapshot: %s", e)

        # 2. Gather visible texts (OCR or UIA fallback)
        visible_texts: List[str] = []
        visual_hash = ""
        try:
            img, ox, oy = self._capture.capture_active_window(compress=False)
            # Compute quick image content hash
            import numpy as np
            arr = np.array(img)
            # Sample downsampled thumbnail for robust fast hashing
            thumb = arr[::8, ::8, :3] if arr.ndim == 3 else arr[::8, ::8]
            visual_hash = hashlib.md5(thumb.tobytes()).hexdigest()

            if include_ocr:
                boxes = self._ocr.detect_text(img, offset=(ox, oy))
                for b in boxes:
                    t = b.text.strip()
                    if len(t) >= 3 and t not in visible_texts:
                        visible_texts.append(t)
        except Exception as e:
            logger.debug("Image/OCR capture error during snapshot: %s", e)

        # Supplement visible_texts with UIA element names if OCR didn't catch them
        for el in visible_elements:
            nm = el["name"]
            if nm and nm not in visible_texts:
                visible_texts.append(nm)

        return ScreenSnapshot(
            timestamp=time.time(),
            window_title=title,
            app_name=session.app_name,
            rect=rect,
            visible_texts=visible_texts,
            visible_elements=visible_elements,
            visual_hash=visual_hash,
        )

    def compute_diff(self, pre: ScreenSnapshot, post: ScreenSnapshot) -> SemanticScreenDiff:
        """Calculates differences between pre- and post-action snapshots and generates spoken summary."""
        title_changed = (pre.window_title != post.window_title)

        pre_set: Set[str] = {t.lower() for t in pre.visible_texts}
        post_set: Set[str] = {t.lower() for t in post.visible_texts}

        new_texts = [t for t in post.visible_texts if t.lower() not in pre_set]
        removed_texts = [t for t in pre.visible_texts if t.lower() not in post_set]

        # Check new UI elements
        pre_elem_names: Set[str] = {e["name"].lower() for e in pre.visible_elements}
        new_elements = [e for e in post.visible_elements if e["name"].lower() not in pre_elem_names]

        hash_changed = (pre.visual_hash != post.visual_hash and bool(pre.visual_hash and post.visual_hash))
        has_changed = bool(title_changed or new_texts or removed_texts or new_elements or hash_changed)

        summary = self._generate_summary(pre, post, new_texts, removed_texts, new_elements, title_changed, has_changed)

        return SemanticScreenDiff(
            has_changed=has_changed,
            title_changed=title_changed,
            newly_visible_texts=new_texts,
            removed_texts=removed_texts,
            newly_visible_elements=new_elements,
            summary=summary,
        )

    def _generate_summary(
        self,
        pre: ScreenSnapshot,
        post: ScreenSnapshot,
        new_texts: List[str],
        removed_texts: List[str],
        new_elements: List[Dict[str, Any]],
        title_changed: bool,
        has_changed: bool,
    ) -> str:
        if not has_changed:
            return "No visible screen changes detected. The viewport appears static."

        parts = []
        if title_changed:
            parts.append(f"Window title changed to '{post.window_title}'.")

        if new_elements:
            elem_names = [e['name'] for e in new_elements[:3]]
            sample_str = ", ".join(f"'{nm}'" for nm in elem_names)
            parts.append(f"{len(new_elements)} new interactive element(s) appeared, including {sample_str}.")
        elif new_texts:
            sample_str = ", ".join(f"'{t}'" for t in new_texts[:3])
            parts.append(f"You are viewing a new section with {len(new_texts)} new item(s), including {sample_str}.")

        if not parts:
            parts.append("The viewport moved and new content is visible.")

        return " ".join(parts)


_screen_diff_instance: Optional[SemanticScreenDiffEngine] = None


def get_screen_diff_engine() -> SemanticScreenDiffEngine:
    global _screen_diff_instance
    if _screen_diff_instance is None:
        _screen_diff_instance = SemanticScreenDiffEngine()
    return _screen_diff_instance

