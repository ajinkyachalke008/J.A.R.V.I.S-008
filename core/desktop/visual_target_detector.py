"""
core/desktop/visual_target_detector.py — Visual target grounding, semantic fuzzy matching, and scroll-to-find loop.
"""
from __future__ import annotations

import difflib
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from .ocr_engine import get_ocr_engine
from .screen_capture import get_screen_capture
from .ui_automation import UIElement, get_ui_automation

logger = logging.getLogger("JARVIS.VisualTargetDetector")


@dataclass
class VisualTarget:
    """An interactive element identified on screen with spatial coordinates and semantic label."""
    label: str
    category: str  # "video_card", "button", "link", "input", "text", "generic"
    rect: Tuple[int, int, int, int]  # (left, top, width, height)
    confidence: float = 1.0

    @property
    def center(self) -> Tuple[int, int]:
        l, t, w, h = self.rect
        return (l + w // 2, t + h // 2)

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "category": self.category,
            "rect": list(self.rect),
            "center": list(self.center),
            "confidence": round(self.confidence, 3),
        }


# Ordinal words to integer mapping
_ORDINALS = {
    "first": 1, "1st": 1,
    "second": 2, "2nd": 2,
    "third": 3, "3rd": 3,
    "fourth": 4, "4th": 4,
    "fifth": 5, "5th": 5,
    "sixth": 6, "6th": 6,
    "seventh": 7, "7th": 7,
    "eighth": 8, "8th": 8,
    "ninth": 9, "9th": 9,
    "tenth": 10, "10th": 10,
    "next": 1, "top": 1, "last": -1,
}


def _clean_text(s: str) -> str:
    return re.sub(r"[^\w\s]", " ", (s or "").lower()).strip()


def calculate_semantic_similarity(query: str, candidate: str) -> float:
    """Calculates hybrid fuzzy token + sequence similarity between query and candidate text."""
    q_clean = _clean_text(query)
    c_clean = _clean_text(candidate)

    if not q_clean or not c_clean:
        return 0.0

    # 1. Exact or Substring match
    if q_clean == c_clean:
        return 1.0
    if q_clean in c_clean:
        return 0.90
    if c_clean in q_clean:
        return 0.85

    # 2. Token overlap ratio (bag-of-words recall)
    q_words = set(q_clean.split())
    c_words = set(c_clean.split())
    if not q_words:
        return 0.0

    overlap = q_words.intersection(c_words)
    token_score = len(overlap) / float(len(q_words))

    # 3. SequenceMatcher ratio
    seq_score = difflib.SequenceMatcher(None, q_clean, c_clean).ratio()

    # Weighted blend
    return 0.65 * token_score + 0.35 * seq_score


class VisualTargetDetector:
    """Locates on-screen visual targets using UI Automation, OCR, and fuzzy semantic matching."""

    def __init__(self):
        self._ui_automation = get_ui_automation()
        self._ocr = get_ocr_engine()
        self._capture = get_screen_capture()

    def detect_visible_targets(self) -> List[VisualTarget]:
        """Gathers interactive controls and text regions from the active window."""
        targets: List[VisualTarget] = []

        # 1. UI Automation Elements
        try:
            uia_elements = self._ui_automation.get_active_window_elements(max_depth=5, max_elements=60)
            for el in uia_elements:
                if not el.is_visible or el.width <= 4 or el.height <= 4:
                    continue

                cat = "generic"
                ctype = el.control_type.lower()
                if "button" in ctype:
                    cat = "button"
                elif "hyperlink" in ctype or "link" in ctype:
                    cat = "link"
                elif "edit" in ctype:
                    cat = "input"
                elif "listitem" in ctype or "group" in ctype:
                    cat = "video_card" if "video" in el.name.lower() or "watch" in el.name.lower() else "card"

                targets.append(
                    VisualTarget(
                        label=el.name or el.automation_id or el.control_type,
                        category=cat,
                        rect=(el.rect[0], el.rect[1], el.width, el.height),
                        confidence=0.95,
                    )
                )
        except Exception as e:
            logger.debug("UIA target detection error: %s", e)

        # 2. OCR Text Fallback / Supplement
        try:
            img, offset_x, offset_y = self._capture.capture_active_window(compress=False)
            ocr_boxes = self._ocr.detect_text(img, offset=(offset_x, offset_y))
            for box in ocr_boxes:
                if len(box.text.strip()) >= 3:
                    # Skip duplicate boxes if UIA already captured element nearby
                    bx, by, bw, bh = box.rect
                    already_present = any(
                        abs(t.center[0] - (bx + bw // 2)) < 25 and abs(t.center[1] - (by + bh // 2)) < 20
                        for t in targets
                    )
                    if not already_present:
                        targets.append(
                            VisualTarget(
                                label=box.text,
                                category="text",
                                rect=box.rect,
                                confidence=float(box.confidence),
                            )
                        )
        except Exception as e:
            logger.debug("OCR target detection error: %s", e)

        return targets

    def find_target(
        self,
        query: str,
        category: Optional[str] = None,
        min_confidence: float = 0.50,
        targets: Optional[List[VisualTarget]] = None,
    ) -> Optional[VisualTarget]:
        """Find the visual target on screen best matching query or ordinal specification."""
        candidates = targets if targets is not None else self.detect_visible_targets()
        if not candidates:
            return None

        clean_query = query.strip()
        low_query = clean_query.lower()

        # 1. Check for Ordinal Matching ("first video", "second card", "third link")
        ordinal_idx = self._extract_ordinal(low_query)
        if ordinal_idx is not None:
            # Filter candidates by category or vertical position
            filtered = [
                c for c in candidates
                if (not category or c.category == category or "video" in low_query)
                and c.rect[3] > 15  # avoid tiny headers
            ]
            # Sort vertically (top-to-bottom, then left-to-right)
            filtered.sort(key=lambda c: (c.rect[1], c.rect[0]))
            if filtered:
                if ordinal_idx == -1:
                    return filtered[-1]
                idx = ordinal_idx - 1
                if 0 <= idx < len(filtered):
                    return filtered[idx]
                return filtered[0]

        # 2. Semantic Fuzzy Matching across Labels
        scored: List[Tuple[float, VisualTarget]] = []
        for c in candidates:
            score = calculate_semantic_similarity(clean_query, c.label)
            if category and c.category == category:
                score += 0.10  # Category boost
            if score >= min_confidence:
                scored.append((score, c))

        if not scored:
            return None

        # Sort descending by score
        scored.sort(key=lambda item: item[0], reverse=True)
        best_score, best_target = scored[0]
        logger.info(
            "Visual target match: '%s' -> '%s' (score=%.2f, category=%s)",
            clean_query,
            best_target.label[:40],
            best_score,
            best_target.category,
        )
        return VisualTarget(
            label=best_target.label,
            category=best_target.category,
            rect=best_target.rect,
            confidence=best_score,
        )

    def scroll_until_visible(
        self,
        query: str,
        max_scroll_attempts: int = 4,
        category: Optional[str] = None,
    ) -> Tuple[Optional[VisualTarget], int]:
        """Searches for target in current viewport; scrolls down incrementally if not found."""
        from .universal_scroll import get_universal_scroll

        scroller = get_universal_scroll()

        for attempt in range(1, max_scroll_attempts + 1):
            logger.info("Scanning viewport for '%s' (attempt %d/%d)...", query, attempt, max_scroll_attempts)
            target = self.find_target(query, category=category)
            if target is not None and target.confidence >= 0.55:
                return (target, attempt)

            if attempt < max_scroll_attempts:
                # Scroll down one standard page
                logger.info("Target '%s' not visible yet; scrolling down...", query)
                scroller.scroll(command_or_direction="down", amount="page", verify=False)
                time.sleep(0.30)  # Settle delay for web rendering

        # Final check after last scroll
        target = self.find_target(query, category=category)
        return (target, max_scroll_attempts)

    def _extract_ordinal(self, text: str) -> Optional[int]:
        for word, val in _ORDINALS.items():
            if re.search(rf"\b{word}\b", text):
                return val
        return None


_target_detector_instance: Optional[VisualTargetDetector] = None


def get_visual_target_detector() -> VisualTargetDetector:
    global _target_detector_instance
    if _target_detector_instance is None:
        _target_detector_instance = VisualTargetDetector()
    return _target_detector_instance

