"""
core/studio — Universal Creation Studio for 2D CAD, Circuit Schematics, and Workflows.
"""
from __future__ import annotations

from .models import CanvasMetadata, Element, Layer, Pin, StudioProject
from .project_manager import ProjectManager, get_project_manager

__all__ = [
    "CanvasMetadata",
    "Layer",
    "Pin",
    "Element",
    "StudioProject",
    "ProjectManager",
    "get_project_manager",
]
