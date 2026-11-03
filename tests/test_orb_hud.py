"""
tests/test_orb_hud.py — Unit tests for Iron Man 3D Holographic Orb HUD integration.
"""
import pathlib
import pytest
from PyQt6.QtCore import Qt, QCoreApplication, QTimer
QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
try:
    import PyQt6.QtWebEngineWidgets
except ImportError:
    pass
from PyQt6.QtWidgets import QApplication

from core.hud.orb_bridge import OrbBridge
from memory.config_manager import get_hud_style, save_hud_style, HUD_STYLES


def test_orb_bridge_signals_and_slots(qapp):
    """Verify OrbBridge correctly captures state and audio level, emitting signals."""
    bridge = OrbBridge()

    states_received = []
    levels_received = []

    bridge.stateChanged.connect(lambda s: states_received.append(s))
    bridge.audioLevelChanged.connect(lambda lv: levels_received.append(lv))

    bridge.set_state("LISTENING")
    assert bridge.state == "LISTENING"
    assert states_received == ["LISTENING"]

    # Deduplicate redundant state emission
    bridge.set_state("LISTENING")
    assert len(states_received) == 1

    bridge.set_state("THINKING")
    assert states_received == ["LISTENING", "THINKING"]

    # Audio level clamping
    bridge.set_audio_level(0.75)
    assert abs(bridge.audioLevel - 0.75) < 1e-4
    assert len(levels_received) == 1

    bridge.set_audio_level(1.5)  # Clamps to 1.0
    assert abs(bridge.audioLevel - 1.0) < 1e-4

    bridge.set_audio_level(-0.5)  # Clamps to 0.0
    assert abs(bridge.audioLevel - 0.0) < 1e-4

    # JS logging slot should not raise
    bridge.logFromJs("Test message from WebGL runtime")


def test_orb_asset_bundle_integrity():
    """Verify all local Three.js, shader, style, and HTML assets exist and are non-empty."""
    base = pathlib.Path("assets/orb")
    assert base.exists() and base.is_dir()

    required_files = [
        base / "index.html",
        base / "styles.css",
        base / "app.js",
        base / "scene.js",
        base / "orb_bundle.js",
        base / "vendor" / "three.module.js",
        base / "vendor" / "qwebchannel.js",
        base / "vendor" / "addons" / "controls" / "OrbitControls.js",
        base / "vendor" / "addons" / "postprocessing" / "EffectComposer.js",
        base / "vendor" / "addons" / "postprocessing" / "UnrealBloomPass.js",
    ]

    for f in required_files:
        assert f.exists(), f"Missing required asset: {f}"
        assert f.stat().st_size > 50, f"Asset is unexpectedly empty: {f}"


def test_config_hud_styles():
    """Verify 'orb' is a valid HUD style and is supported by config_manager."""
    assert "orb" in HUD_STYLES
    assert "face" in HUD_STYLES
    assert "core" in HUD_STYLES

    # Test roundtrip
    save_hud_style("orb")
    assert get_hud_style() == "orb"

    save_hud_style("face")
    assert get_hud_style() == "face"

    save_hud_style("core")
    assert get_hud_style() == "core"

    # Restore default
    save_hud_style("orb")
    assert get_hud_style() == "orb"


def test_hud_canvas_with_orb(qapp):
    """Verify HudCanvas instantiates with 'orb' style and mounts WebEngine view cleanly."""
    from ui import HudCanvas

    save_hud_style("orb")
    canvas = HudCanvas(face_path="", assistant_name="JARVIS")

    assert canvas.hud_style == "orb"
    assert canvas._orb_bridge is not None

    if canvas._web_view is not None:
        assert not canvas._web_view.isHidden()

    # Audio level feed should forward to bridge
    canvas.set_audio_level(0.65)
    canvas._step()
    assert canvas._orb_bridge.audioLevel > 0.0

    # Switching to core should hide web view cleanly
    canvas.hud_style = "core"
    if canvas._web_view is not None:
        assert canvas._web_view.isHidden()

    # Restoring orb style shows web view again
    canvas.hud_style = "orb"
    if canvas._web_view is not None:
        assert not canvas._web_view.isHidden()
