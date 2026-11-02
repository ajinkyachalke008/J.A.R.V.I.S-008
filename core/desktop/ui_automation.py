"""
core/desktop/ui_automation.py — Native Windows UI Automation inspection engine for JARVIS MARK LVI.
"""
from __future__ import annotations

import logging
import platform
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from .access_manager import PermissionScope, get_access_manager

logger = logging.getLogger("JARVIS.UIAutomation")

_UIA_AVAILABLE = False
if platform.system() == "Windows":
    try:
        import pywinauto
        from pywinauto import Desktop
        _UIA_AVAILABLE = True
    except Exception as e:
        logger.warning("pywinauto UIA backend unavailable: %s", e)


@dataclass
class UIElement:
    name: str
    control_type: str
    automation_id: str
    rect: Tuple[int, int, int, int]  # (left, top, right, bottom)
    is_enabled: bool = True
    is_visible: bool = True
    has_focus: bool = False
    handle: Optional[int] = None

    @property
    def center(self) -> Tuple[int, int]:
        l, t, r, b = self.rect
        return (l + (r - l) // 2, t + (b - t) // 2)

    @property
    def width(self) -> int:
        return self.rect[2] - self.rect[0]

    @property
    def height(self) -> int:
        return self.rect[3] - self.rect[1]

    def contains(self, x: int, y: int) -> bool:
        l, t, r, b = self.rect
        return l <= x <= r and t <= y <= b

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.control_type,
            "automation_id": self.automation_id,
            "rect": list(self.rect),
            "center": list(self.center),
            "enabled": self.is_enabled,
        }


class UIAutomationEngine:
    """Discovers and inspects interactive controls in running applications via UI Automation."""

    def __init__(self):
        self._access_mgr = get_access_manager()

    def get_active_window_elements(self, max_depth: int = 4, max_elements: int = 50) -> List[UIElement]:
        """Extract interactive UI elements belonging to the current foreground window."""
        if not _UIA_AVAILABLE:
            return []

        if not self._access_mgr.check_permission(PermissionScope.UI_AUTOMATION_READ):
            if not self._access_mgr.is_observe_enabled:
                logger.warning("UI Automation read denied: Permission not granted.")
                return []

        elements: List[UIElement] = []
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return []

            from pywinauto import Application
            app = Application(backend="uia").connect(handle=hwnd)
            win = app.window(handle=hwnd)

            def _traverse(wrapper, depth: int):
                if depth > max_depth or len(elements) >= max_elements:
                    return

                try:
                    elem_type = wrapper.element_info.control_type or "Unknown"
                    name = wrapper.element_info.name or ""
                    auto_id = wrapper.element_info.automation_id or ""
                    r = wrapper.rectangle()
                    rect = (r.left, r.top, r.right, r.bottom)

                    # Filter out zero-size or off-screen elements
                    if (r.right > r.left) and (r.bottom > r.top):
                        # Filter to interactive or landmark controls
                        interactive_types = {
                            "Button", "Edit", "CheckBox", "RadioButton", "ComboBox",
                            "MenuItem", "TabItem", "Hyperlink", "ListItem", "TreeItem",
                            "ToolBar", "Window", "Document"
                        }
                        if elem_type in interactive_types or name:
                            elements.append(
                                UIElement(
                                    name=name.strip(),
                                    control_type=elem_type,
                                    automation_id=auto_id,
                                    rect=rect,
                                    is_enabled=wrapper.is_enabled(),
                                    is_visible=wrapper.is_visible(),
                                    has_focus=wrapper.has_keyboard_focus(),
                                    handle=wrapper.handle,
                                )
                            )

                    for child in wrapper.children():
                        _traverse(child, depth + 1)
                except Exception:
                    pass

            _traverse(win, 0)
        except Exception as e:
            logger.debug("Active window UIA inspection error: %s", e)

        return elements

    def find_element_by_name(self, target_name: str, elements: Optional[List[UIElement]] = None) -> Optional[UIElement]:
        """Find the element whose name or automation_id most closely matches target_name."""
        elems = elements or self.get_active_window_elements()
        query = target_name.strip().lower()

        # 1. Exact match
        for el in elems:
            if el.name.lower() == query or el.automation_id.lower() == query:
                return el

        # 2. Substring match
        for el in elems:
            if query in el.name.lower() or query in el.automation_id.lower():
                return el

        return None

    def get_element_at(self, x: int, y: int, elements: Optional[List[UIElement]] = None) -> Optional[UIElement]:
        """Hit test: returns the smallest UI element containing (x, y)."""
        elems = elements or self.get_active_window_elements()
        candidates = [el for el in elems if el.contains(x, y)]
        if not candidates:
            return None
        # Return smallest candidate (most specific child widget)
        candidates.sort(key=lambda el: el.width * el.height)
        return candidates[0]

    def format_tree_summary(self, max_elements: int = 35) -> str:
        """Produces a clean text representation of active controls for LLM prompt context."""
        elems = self.get_active_window_elements(max_elements=max_elements)
        if not elems:
            return "No UI Automation elements detected for active window."

        lines = ["ACTIVE WINDOW CONTROLS:"]
        for el in elems:
            if el.name or el.control_type in ("Button", "Edit", "MenuItem"):
                cx, cy = el.center
                lines.append(f"- [{el.control_type}] \"{el.name}\" center=({cx},{cy}) id=\"{el.automation_id}\"")
        return "\n".join(lines)


_ui_automation_instance: Optional[UIAutomationEngine] = None


def get_ui_automation() -> UIAutomationEngine:
    global _ui_automation_instance
    if _ui_automation_instance is None:
        _ui_automation_instance = UIAutomationEngine()
    return _ui_automation_instance
