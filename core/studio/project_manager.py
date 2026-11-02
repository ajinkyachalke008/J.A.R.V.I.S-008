"""
core/studio/project_manager.py — Project lifecycle, element mutation, and undo/redo history.
"""
from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Callable, List, Optional

from .models import Element, Layer, StudioProject
from .validator import ProjectValidator

logger = logging.getLogger("JARVIS.Studio.ProjectManager")


class ProjectManager:
    """Maintains active project state, mutation operations, and undo/redo stacks."""

    def __init__(self):
        self._project = StudioProject()
        self._undo_stack: List[str] = []
        self._redo_stack: List[str] = []
        self._change_listeners: List[Callable[[StudioProject], None]] = []

    @property
    def project(self) -> StudioProject:
        return self._project

    def set_project(self, project: StudioProject) -> None:
        self._record_undo()
        self._project = project
        self._redo_stack.clear()
        self._notify_change()

    def new_project(self, title: str = "New Project", domain: str = "cad", units: str = "mm") -> StudioProject:
        self._record_undo()
        self._project = StudioProject(title=title, domain=domain)
        self._project.canvas.units = units
        self._redo_stack.clear()
        self._notify_change()
        return self._project

    def add_element(self, element: Element) -> None:
        self._record_undo()
        self._project.elements.append(element)
        self._notify_change()

    def remove_element(self, element_id: str) -> bool:
        self._record_undo()
        init_len = len(self._project.elements)
        self._project.elements = [el for el in self._project.elements if el.id != element_id]
        if len(self._project.elements) < init_len:
            self._notify_change()
            return True
        return False

    def clear(self) -> None:
        self._record_undo()
        self._project.elements.clear()
        self._notify_change()

    def _record_undo(self) -> None:
        if len(self._undo_stack) >= 30:
            self._undo_stack.pop(0)
        self._undo_stack.append(self._project.to_json())

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        self._redo_stack.append(self._project.to_json())
        prev_json = self._undo_stack.pop()
        self._project = StudioProject.from_json(prev_json)
        self._notify_change()
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        self._undo_stack.append(self._project.to_json())
        next_json = self._redo_stack.pop()
        self._project = StudioProject.from_json(next_json)
        self._notify_change()
        return True

    def save_to_file(self, path: Path | str) -> bool:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self._project.to_json(), encoding="utf-8")
        logger.info("Project saved to %s", p)
        return True

    def load_from_file(self, path: Path | str) -> StudioProject:
        p = Path(path)
        content = p.read_text(encoding="utf-8")
        proj = StudioProject.from_json(content)
        is_valid, errors = ProjectValidator.validate(proj)
        if not is_valid:
            logger.warning("Loaded project has validation warnings: %s", errors)
        self.set_project(proj)
        return proj

    def register_change_listener(self, cb: Callable[[StudioProject], None]) -> None:
        if cb not in self._change_listeners:
            self._change_listeners.append(cb)

    def _notify_change(self) -> None:
        for cb in list(self._change_listeners):
            try:
                cb(self._project)
            except Exception as e:
                logger.error("Error in project change listener: %s", e)


_project_mgr_instance: Optional[ProjectManager] = None


def get_project_manager() -> ProjectManager:
    global _project_mgr_instance
    if _project_mgr_instance is None:
        _project_mgr_instance = ProjectManager()
    return _project_mgr_instance
