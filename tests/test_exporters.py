"""
Unit tests for DXF, SVG, PNG, and JSON exporters.
"""
from pathlib import Path
import tempfile
from core.studio.cad_engine import CADEngine
from core.studio.exporters import DXFExporter, JSONExporter, PNGExporter, SVGExporter


def test_dxf_export():
    proj = CADEngine.create_mounting_plate_demonstrator()
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "test_plate.dxf"
        content = DXFExporter.export(proj, out_path)

        assert out_path.exists()
        assert out_path.stat().st_size > 500
        # Check standard DXF tags
        assert "SECTION" in content
        assert "HEADER" in content
        assert "$ACADVER" in content
        assert "AC1009" in content
        assert "TABLES" in content
        assert "ENTITIES" in content
        assert "EOF" in content
        assert "CIRCLE" in content
        assert "LINE" in content


def test_svg_export():
    proj = CADEngine.create_mounting_plate_demonstrator()
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "test_plate.svg"
        content = SVGExporter.export(proj, out_path)

        assert out_path.exists()
        assert "<svg" in content
        assert "</svg>" in content
        assert 'xmlns="http://www.w3.org/2000/svg"' in content
        assert "<rect" in content
        assert "<circle" in content


def test_json_roundtrip():
    proj = CADEngine.create_mounting_plate_demonstrator()
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "test_plate.json"
        JSONExporter.export(proj, out_path)

        assert out_path.exists()
        reloaded = proj.from_json(out_path.read_text(encoding="utf-8"))
        assert reloaded.domain == proj.domain
        assert len(reloaded.elements) == len(proj.elements)
        assert reloaded.title == proj.title

