import sys
import pytest
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtCore import Qt

from core.hud.island_state import IslandPresentationModel, IslandState
from core.hud.dynamic_island import DynamicIsland, MirroredWaveformWidget
from ui import _apply_windows_taskbar_icon


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_mirrored_waveform_idle_stop(qapp):
    """MirroredWaveformWidget should stop timer when hidden and restart when shown."""
    widget = MirroredWaveformWidget(None, bar_count=9)
    widget.show()
    assert widget._timer.isActive()

    # When hidden, calling step or hideEvent stops timer to prevent CPU waste
    widget.hide()
    widget._step()
    assert not widget._timer.isActive()

    widget.show()
    widget.start()
    assert widget._timer.isActive()
    widget.stop()
    assert not widget._timer.isActive()


def test_dynamic_island_expanded_waveform_gated(qapp):
    """DynamicIsland expanded waveform timer must not run while collapsed."""
    model = IslandPresentationModel()
    island = DynamicIsland(parent=None, model=model)
    island.show()

    # Initially collapsed: expanded waveform timer must be stopped
    assert not island._is_expanded
    assert not island._expanded_waveform._timer.isActive()

    # Expand: expanded waveform timer starts
    island.set_expanded(True)
    assert island._is_expanded
    assert island._expanded_waveform._timer.isActive()

    # Collapse: expanded waveform timer stops immediately
    island.set_expanded(False)
    assert not island._is_expanded
    assert not island._expanded_waveform._timer.isActive()

    island.close()


def test_dynamic_island_adaptive_glow_interval(qapp):
    """DynamicIsland glow timer must throttle to 50ms when idle to eliminate lag."""
    model = IslandPresentationModel()
    island = DynamicIsland(parent=None, model=model)
    island.show()

    # IDLE state
    model.set_state(IslandState.IDLE)
    island._step_glow()
    assert island._glow_timer.interval() == 50

    # Active state (SPEAKING)
    model.set_state(IslandState.SPEAKING)
    island._step_glow()
    assert island._glow_timer.interval() == 33

    island.close()


def test_dynamic_island_stop_button_and_quit_wiring(qapp):
    """DynamicIsland expanded bar must have a Stop button wired to quit_jarvis."""
    model = IslandPresentationModel()
    island = DynamicIsland(parent=None, model=model)
    
    quit_called = []
    def on_quit():
        quit_called.append(True)

    island._on_quit_cb = on_quit
    assert hasattr(island, "_btn_quit")
    assert island._btn_quit.text() == "❌ Stop"

    # Trigger quit
    island._btn_quit.click()
    assert len(quit_called) == 1

    island.close()


def test_presentation_model_notify_quit(qapp):
    """IslandPresentationModel must support quit_requested notification."""
    model = IslandPresentationModel()
    signal_received = []

    model.quit_requested.connect(lambda: signal_received.append(True))
    model.notify_quit()
    assert len(signal_received) == 1


def test_taskbar_icon_helper(qapp):
    """_apply_windows_taskbar_icon runs without error on valid or invalid paths."""
    from ui import CONFIG_DIR
    ico_path = CONFIG_DIR / "jarvis.ico"
    # Even with dummy HWND or real widget, it should gracefully execute
    dummy_widget = MirroredWaveformWidget(None)
    dummy_widget.show()
    _apply_windows_taskbar_icon(int(dummy_widget.winId()), ico_path)
    _apply_windows_taskbar_icon(int(dummy_widget.winId()), Path("nonexistent.ico"))
    dummy_widget.close()

