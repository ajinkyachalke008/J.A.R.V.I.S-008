"""
core/studio/exporters/json_exporter.py — Project JSON serializer.
"""
from __future__ import annotations

import json
from pathlib import Path
from ..models import StudioProject


class JSONExporter:
    """Exports StudioProject models into native serialized JSON format."""

    @classmethod
    def export(cls, project: StudioProject, output_path: Path | str, indent: int = 2) -> str:
        content = project.to_json(indent=indent)
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(content, encoding="utf-8")
        return content

