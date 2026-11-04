"""
core/desktop/scroll_intent.py — Natural-language intent parser for universal scrolling.
"""
from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from typing import Optional


class ScrollDirection(str, enum.Enum):
    DOWN = "down"
    UP = "up"
    LEFT = "left"
    RIGHT = "right"
    PAGE_DOWN = "page_down"
    PAGE_UP = "page_up"
    TO_TOP = "to_top"
    TO_BOTTOM = "to_bottom"


class ScrollMagnitude(str, enum.Enum):
    SUBTLE = "subtle"      # a little, slightly, slowly (~120-240 delta / 1-2 notches)
    NORMAL = "normal"      # standard scroll (~480-720 delta / 4-6 notches)
    MORE = "more"          # more, further, a lot (~960-1200 delta / 8-10 notches)
    PAGE = "page"          # one page (~1440 delta or PageDown/PageUp key)
    EXTREME = "extreme"    # to the top / to the bottom (Home/End or extreme delta)


class ContainerTarget(str, enum.Enum):
    MAIN = "main"          # main feed, page, content area
    SIDEBAR = "sidebar"    # left/right sidebar, navigation pane
    COMMENTS = "comments"  # comments section, chat pane
    GENERIC = "generic"    # active focused control / viewport


@dataclass(frozen=True)
class ScrollIntent:
    direction: ScrollDirection = ScrollDirection.DOWN
    magnitude: ScrollMagnitude = ScrollMagnitude.NORMAL
    is_repeat: bool = False
    is_continuous: bool = False
    is_stop: bool = False
    container: ContainerTarget = ContainerTarget.MAIN
    raw_command: str = ""

    def to_dict(self) -> dict:
        return {
            "direction": self.direction.value,
            "magnitude": self.magnitude.value,
            "is_repeat": self.is_repeat,
            "is_continuous": self.is_continuous,
            "is_stop": self.is_stop,
            "container": self.container.value,
            "raw_command": self.raw_command,
        }


# Regex matchers for parsing
_STOP_PATTERN = re.compile(
    r"\b(stop|halt|pause|hold|freeze|cancel|quit|enough)\b",
    re.IGNORECASE,
)
_CONTINUOUS_PATTERN = re.compile(
    r"\b(keep scrolling|continue scrolling|keep going|continuously|until i (tell you to )?stop)\b",
    re.IGNORECASE,
)
_REPEAT_PATTERN = re.compile(
    r"\b(again|once more|one more time|repeat|further|more)\b",
    re.IGNORECASE,
)
_TO_BOTTOM_PATTERN = re.compile(
    r"\b(to (the )?bottom|all the way down|end of (the )?page|reach the end)\b",
    re.IGNORECASE,
)
_TO_TOP_PATTERN = re.compile(
    r"\b(to (the )?(top|beginning)|all the way up|back to top)\b",
    re.IGNORECASE,
)
_PAGE_DOWN_PATTERN = re.compile(
    r"\b(one page down|page down|next (page|section))\b",
    re.IGNORECASE,
)
_PAGE_UP_PATTERN = re.compile(
    r"\b(one page up|page up|previous (page|section))\b",
    re.IGNORECASE,
)
_UP_PATTERN = re.compile(
    r"\b(up|upwards|back up|higher)\b",
    re.IGNORECASE,
)
_DOWN_PATTERN = re.compile(
    r"\b(down|downwards|lower)\b",
    re.IGNORECASE,
)
_LEFT_PATTERN = re.compile(
    r"\b(left|leftwards)\b",
    re.IGNORECASE,
)
_RIGHT_PATTERN = re.compile(
    r"\b(right|rightwards)\b",
    re.IGNORECASE,
)

# Magnitude patterns
_SUBTLE_PATTERN = re.compile(
    r"\b(a little( bit)?|little more|slightly|slowly|tiny bit|gentle|a bit|softly)\b",
    re.IGNORECASE,
)
_MORE_PATTERN = re.compile(
    r"\b(more|further|faster|a lot|faster|deeply)\b",
    re.IGNORECASE,
)
_PAGE_MAG_PATTERN = re.compile(
    r"\b(one page|whole page|full page|halfway)\b",
    re.IGNORECASE,
)

# Container target patterns
_SIDEBAR_PATTERN = re.compile(
    r"\b(sidebar|left side|side panel|navigation panel|drawer)\b",
    re.IGNORECASE,
)
_COMMENTS_PATTERN = re.compile(
    r"\b(comments?|chat|discussion)\b",
    re.IGNORECASE,
)


def parse_scroll_intent(command: str) -> ScrollIntent:
    """Parse natural language command into structured ScrollIntent."""
    raw = (command or "").strip()
    low = raw.lower()

    # 1. Check for Continuous Mode first (e.g. "scroll slowly until I tell you to stop", "keep scrolling")
    is_continuous = bool(_CONTINUOUS_PATTERN.search(low))

    # 2. Check for Stop / Abort (only when NOT a continuous instruction)
    if not is_continuous and _STOP_PATTERN.search(low) and ("scroll" in low or len(low.split()) <= 3):
        return ScrollIntent(
            direction=ScrollDirection.DOWN,
            magnitude=ScrollMagnitude.NORMAL,
            is_stop=True,
            raw_command=raw,
        )

    # 3. Check for Repeat
    is_repeat = bool(_REPEAT_PATTERN.search(low))

    # 4. Resolve Direction
    if _TO_BOTTOM_PATTERN.search(low):
        direction = ScrollDirection.TO_BOTTOM
        magnitude = ScrollMagnitude.EXTREME
    elif _TO_TOP_PATTERN.search(low):
        direction = ScrollDirection.TO_TOP
        magnitude = ScrollMagnitude.EXTREME
    elif _PAGE_DOWN_PATTERN.search(low):
        direction = ScrollDirection.PAGE_DOWN
        magnitude = ScrollMagnitude.PAGE
    elif _PAGE_UP_PATTERN.search(low):
        direction = ScrollDirection.PAGE_UP
        magnitude = ScrollMagnitude.PAGE
    elif _UP_PATTERN.search(low):
        direction = ScrollDirection.UP
        magnitude = ScrollMagnitude.NORMAL
    elif _LEFT_PATTERN.search(low):
        direction = ScrollDirection.LEFT
        magnitude = ScrollMagnitude.NORMAL
    elif _RIGHT_PATTERN.search(low):
        direction = ScrollDirection.RIGHT
        magnitude = ScrollMagnitude.NORMAL
    elif _DOWN_PATTERN.search(low):
        direction = ScrollDirection.DOWN
        magnitude = ScrollMagnitude.NORMAL
    else:
        # Default direction is DOWN if unspecified
        direction = ScrollDirection.DOWN
        magnitude = ScrollMagnitude.NORMAL

    # 5. Resolve Magnitude (unless already EXTREME or PAGE)
    if magnitude not in (ScrollMagnitude.EXTREME, ScrollMagnitude.PAGE):
        if _SUBTLE_PATTERN.search(low):
            magnitude = ScrollMagnitude.SUBTLE
        elif _PAGE_MAG_PATTERN.search(low):
            magnitude = ScrollMagnitude.PAGE
        elif _MORE_PATTERN.search(low):
            magnitude = ScrollMagnitude.MORE

    # 6. Resolve Target Container
    if _SIDEBAR_PATTERN.search(low):
        container = ContainerTarget.SIDEBAR
    elif _COMMENTS_PATTERN.search(low):
        container = ContainerTarget.COMMENTS
    else:
        container = ContainerTarget.MAIN

    return ScrollIntent(
        direction=direction,
        magnitude=magnitude,
        is_repeat=is_repeat,
        is_continuous=is_continuous,
        is_stop=False,
        container=container,
        raw_command=raw,
    )
