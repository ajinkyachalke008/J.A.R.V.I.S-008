"""
core/studio/models.py — Data structures and serialization for the Universal Creation Studio.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CanvasMetadata:
    units: str = "mm"  # "mm", "px", "inch"
    width: float = 200.0
    height: float = 150.0
    grid_spacing: float = 10.0
    snap_to_grid: bool = True
    background_color: str = "#010d14"


@dataclass
class Layer:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Default"
    visible: bool = True
    locked: bool = False
    color: str = "#00d4ff"


@dataclass
class Pin:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "1"
    x: float = 0.0
    y: float = 0.0
    net: str = ""


@dataclass
class Element:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: str = "rect"  # line, rect, circle, arc, text, dimension, component, wire, node
    layer_id: str = "default"
    geometry: Dict[str, Any] = field(default_factory=dict)
    style: Dict[str, Any] = field(default_factory=lambda: {
        "stroke": "#00d4ff",
        "stroke_width": 1.5,
        "fill": "none",
        "stroke_style": "solid",  # solid, dashed, dotted
    })
    properties: Dict[str, Any] = field(default_factory=dict)
    pins: List[Pin] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> Element:
        pins = [Pin(**p) if isinstance(p, dict) else p for p in data.get("pins", [])]
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            type=data.get("type", "rect"),
            layer_id=data.get("layer_id", "default"),
            geometry=data.get("geometry", {}),
            style=data.get("style", {}),
            properties=data.get("properties", {}),
            pins=pins,
        )


@dataclass
class StudioProject:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "Untitled Creation"
    domain: str = "cad"  # "cad", "circuit", "workflow", "diagram"
    canvas: CanvasMetadata = field(default_factory=CanvasMetadata)
    layers: List[Layer] = field(default_factory=lambda: [Layer(id="default", name="Outline", color="#00d4ff")])
    elements: List[Element] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "domain": self.domain,
            "canvas": asdict(self.canvas),
            "layers": [asdict(l) for l in self.layers],
            "elements": [
                {
                    "id": el.id,
                    "type": el.type,
                    "layer_id": el.layer_id,
                    "geometry": el.geometry,
                    "style": el.style,
                    "properties": el.properties,
                    "pins": [asdict(p) for p in el.pins],
                }
                for el in self.elements
            ],
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict) -> StudioProject:
        canvas = CanvasMetadata(**data.get("canvas", {}))
        layers = [Layer(**l) if isinstance(l, dict) else l for l in data.get("layers", [])]
        elements = [Element.from_dict(el) if isinstance(el, dict) else el for el in data.get("elements", [])]
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            title=data.get("title", "Untitled Project"),
            domain=data.get("domain", "cad"),
            canvas=canvas,
            layers=layers if layers else [Layer(id="default", name="Outline")],
            elements=elements,
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_json(cls, json_str: str) -> StudioProject:
        return cls.from_dict(json.loads(json_str))
