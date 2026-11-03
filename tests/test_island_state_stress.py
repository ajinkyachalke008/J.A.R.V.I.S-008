"""
tests/test_island_state_stress.py — Adversarial Stress Testing & Empirical Verification
for IslandPresentationModel (core/hud/island_state.py).

Verifies:
1. Audio level boundary injection (extreme values, nan, inf, rapid oscillating bursts, 10,000 steps).
2. Filter decay convergence (exponential decay rate, exact zero convergence, numerical stability).
3. Arbitrary state string fuzzing (empty, whitespace, case variations, non-ASCII, invalid tokens, types).
4. Thread safety (concurrent audio ingestion, filter stepping, state switching, and readers).
"""
from __future__ import annotations

import math
import os
import random
import sys
import threading
import time
from typing import Any, List

import pytest
from PyQt6.QtCore import QCoreApplication

# Ensure workspace root is in sys.path for direct CLI execution
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from core.hud.island_state import IslandPresentationModel, IslandState, STATE_THEMES, PALETTE


def get_or_create_qapp() -> QCoreApplication:
    """Ensure a QCoreApplication exists for QObject signal/slot handling."""
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication(sys.argv)
    return app


# ── 1. Audio Level Boundary Injection ────────────────────────────────────────

def test_audio_level_extreme_boundary_injection():
    """Verify extreme audio level injections are safely clamped or rejected."""
    _ = get_or_create_qapp()
    model = IslandPresentationModel()

    # Extreme negatives -> clamped to 0.0
    negatives = [-1e30, -999999.0, -1.0, -0.1, -1e-12, -0.0]
    for neg in negatives:
        model.reset_audio()
        model.set_audio_level(neg)
        assert model._live_amp == 0.0, f"Negative value {neg} did not clamp to 0.0"

    # Extreme positives (>1.0) -> clamped to 1.0
    positives = [1.000001, 1.5, 2.0, 100.0, 999999.0, 1e30, float("inf")]
    for pos in positives:
        model.reset_audio()
        model.set_audio_level(pos)
        assert model._live_amp == 1.0, f"Positive overflow value {pos} did not clamp to 1.0"

    # Special float: NaN
    model.reset_audio()
    model.set_audio_level(float("nan"))
    # In Python, max(0.0, min(1.0, nan)) evaluates to 1.0; verify it doesn't propagate NaN
    assert not math.isnan(model._live_amp), "NaN was improperly propagated into live_amp"
    assert model._live_amp == 1.0, f"Expected 1.0 peak for NaN, got {model._live_amp}"

    # Special float: -inf
    model.reset_audio()
    model.set_audio_level(float("-inf"))
    assert model._live_amp == 0.0, f"Expected 0.0 for -inf, got {model._live_amp}"

    # Invalid non-numeric types -> safely ignored without exception
    invalid_inputs: List[Any] = [None, "loud", "not_a_number", [], {}, object(), (1, 2)]
    for inv in invalid_inputs:
        model.reset_audio()
        model.set_audio_level(inv)  # Must not raise
        assert model._live_amp == 0.0, f"Invalid type {type(inv)} altered live_amp"


def test_audio_level_oscillating_bursts_and_10k_steps():
    """Verify numerical stability and [0.0, 1.0] bounds over 10,000 extreme steps."""
    _ = get_or_create_qapp()
    model = IslandPresentationModel()

    emitted_levels: List[float] = []
    model.audio_level_changed.connect(emitted_levels.append)

    boundary_pool = [
        -1e20, -100.0, -1.0, -0.0, 0.0,
        0.0001, 0.5, 0.9999, 1.0,
        1.0001, 2.0, 100.0, 1e20,
        float("inf"), float("-inf"), float("nan"),
        None, "bad_input", [],
    ]

    for step in range(10000):
        # Alternating patterns: rapid bursts, random values, boundary inputs
        if step % 3 == 0:
            # Alternating square wave 0.0 <-> 1.0
            model.set_audio_level(1.0 if (step % 2 == 0) else 0.0)
        elif step % 3 == 1:
            # Random continuous amplitude
            model.set_audio_level(random.random())
        else:
            # Adversarial boundary injection
            inp = random.choice(boundary_pool)
            model.set_audio_level(inp)

        disp = model.step_audio_filter()

        # Invariant checks
        assert not math.isnan(disp), f"Display amplitude became NaN at step {step}"
        assert not math.isinf(disp), f"Display amplitude became Inf at step {step}"
        assert 0.0 <= disp <= 1.0, f"Display amplitude {disp} out of bounds [0.0, 1.0] at step {step}"
        assert 0.0 <= model._live_amp <= 1.0, f"Live amp {model._live_amp} out of bounds at step {step}"

    assert len(emitted_levels) == 10000
    for level in emitted_levels:
        assert 0.0 <= level <= 1.0


# ── 2. Filter Decay Convergence & Numerical Stability ────────────────────────

def test_filter_decay_convergence_exact_rate():
    """Verify exponential decay rate and finite convergence to exact zero."""
    _ = get_or_create_qapp()
    model = IslandPresentationModel()

    # Inject 1.0 impulse
    model.reset_audio()
    model.set_audio_level(1.0)
    assert model._live_amp == 1.0
    assert model.get_display_amplitude() == 0.0

    # Step 1:
    # live = 1.0 * 0.86 = 0.86
    # disp = 0.0 + (0.86 - 0.0) * 0.45 = 0.387
    s1 = model.step_audio_filter()
    assert abs(s1 - 0.387) < 1e-6, f"Step 1 expected 0.387, got {s1}"

    # Step 2:
    # live = 0.86 * 0.86 = 0.7396
    # disp = 0.387 + (0.7396 - 0.387) * 0.45 = 0.54567
    s2 = model.step_audio_filter()
    assert abs(s2 - 0.54567) < 1e-6, f"Step 2 expected 0.54567, got {s2}"

    # Step 3:
    # live = 0.7396 * 0.86 = 0.636056
    # disp = 0.54567 + (0.636056 - 0.54567) * 0.45 = 0.5863437
    s3 = model.step_audio_filter()
    assert abs(s3 - 0.5863437) < 1e-6, f"Step 3 expected 0.5863437, got {s3}"

    # After step 3 (the peak), amplitude must strictly decay monotonically
    prev = s3
    decay_steps = 0
    for step_num in range(4, 100):
        cur = model.step_audio_filter()
        decay_steps = step_num
        if cur > 0.0:
            assert cur < prev, f"Decay not monotonic at step {step_num}: cur={cur} >= prev={prev}"
        prev = cur
        if model._live_amp == 0.0 and model.get_display_amplitude() == 0.0:
            break

    # Convergence must be achieved in <= 50 steps
    assert decay_steps <= 50, f"Convergence took {decay_steps} steps (>50)"
    assert model.get_display_amplitude() == 0.0
    assert model._live_amp == 0.0


def test_filter_decay_from_arbitrary_initial_levels():
    """Verify decay converges to exact 0.0 from multiple initial energy levels."""
    _ = get_or_create_qapp()
    model = IslandPresentationModel()

    initial_levels = [0.05, 0.2, 0.5, 0.75, 0.9, 1.0]
    for init in initial_levels:
        model.reset_audio()
        model.set_audio_level(init)
        for _ in range(60):
            model.step_audio_filter()
        assert model._live_amp == 0.0, f"Live amp failed to converge to 0.0 from init {init}"
        assert model.get_display_amplitude() == 0.0, f"Display amp failed to converge from init {init}"


# ── 3. Arbitrary State String Fuzzing ────────────────────────────────────────

def test_arbitrary_state_string_fuzzing():
    """Verify state normalization and transition handling for arbitrary / fuzz inputs."""
    _ = get_or_create_qapp()
    model = IslandPresentationModel()

    fuzz_matrix: List[Any] = [
        # Empty & whitespace
        "",
        "   ",
        "\t\t\n",
        "\r\n",
        " \u00a0\u2000\u3000 ",
        # Standard states lowercase & mixed
        "idle", "IDLE", "Idle", "iDlE",
        "listening", "LISTENING", "Listening", "LiStEnInG",
        "thinking", "THINKING", "Thinking", "tHiNkInG",
        "speaking", "SPEAKING", "Speaking", "sPeAkInG",
        "error", "ERROR", "Error", "eRrOr",
        "offline", "OFFLINE", "Offline", "oFfLiNe",
        # Aliases
        "ready", "online", "standby", "sleep", "sleeping", "muted",
        "listen", "hear", "hearing", "mic",
        "think", "process", "processing", "working",
        "speak", "talk", "talking",
        "err", "fail", "failed", "crash",
        "disconnected", "off",
        # Non-ASCII & Unicode & Emojis
        "Привет", "日本語", "🔥🤖🚀", "éèçà", "\x00\x01\x7f",
        # Special tokens & SQL/script injection attempts
        "UNKNOWN_XYZ_STATE", "!@#$%^&*()", "SELECT * FROM states",
        "<script>alert(1)</script>", "None", "False", "NaN",
        # Types other than str
        None, 123, 3.14159, True, False, [1, 2, 3], {"a": 1}, object(), b"raw_bytes",
        # Very long string
        "A" * 10000,
    ]

    for raw in fuzz_matrix:
        # normalize_state must return valid IslandState enum
        norm = model.normalize_state(raw)
        assert isinstance(norm, IslandState), f"normalize_state({raw!r}) returned {type(norm)}"

        # set_state must not raise
        model.set_state(raw)
        cur_state = model.get_state()
        assert isinstance(cur_state, IslandState)

        status_text = model.get_status_text()
        assert isinstance(status_text, str)
        assert len(status_text) >= 0

        # Themes must remain intact
        theme = model.get_theme_colors()
        assert isinstance(theme, dict)
        for key in ("background", "surface", "primary", "secondary", "accent",
                    "highlight", "text", "text_muted", "border", "glow", "palette"):
            assert key in theme, f"Missing key '{key}' in theme for state {cur_state}"
        assert theme["palette"] == PALETTE


def test_status_text_override_fuzzing():
    """Verify set_status_text survives arbitrary input fuzzing."""
    _ = get_or_create_qapp()
    model = IslandPresentationModel()

    fuzz_texts: List[Any] = [
        "", "   ", None, 123, 3.14, True, False,
        "System Initialized", "PROCESSING QUERY...", "Привет Мир",
        "🔥 JARVIS ACTIVE 🔥", "A" * 2000
    ]

    for txt in fuzz_texts:
        model.set_status_text(txt)
        res = model.get_status_text()
        assert isinstance(res, str)
        if txt is None or txt == "" or txt == "   ":
            assert res == ""
        else:
            assert res == str(txt).strip().upper()


# ── 4. Thread Safety & Concurrency Stress ────────────────────────────────────

def test_thread_safety_high_contention():
    """Verify multi-threaded concurrent execution across ingestion, stepping, and state switching."""
    app = get_or_create_qapp()
    model = IslandPresentationModel()

    errors: List[tuple[str, Exception]] = []
    state_signals: List[IslandState] = []
    audio_signals: List[float] = []

    lock = threading.Lock()

    def record_state(s: IslandState):
        with lock:
            state_signals.append(s)

    def record_audio(a: float):
        with lock:
            audio_signals.append(a)

    model.state_changed.connect(record_state)
    model.audio_level_changed.connect(record_audio)

    # Ingestion worker 1: high frequency continuous levels
    def audio_worker_a(iterations: int):
        try:
            for _ in range(iterations):
                model.set_audio_level(random.random())
        except Exception as e:
            errors.append(("audio_worker_a", e))

    # Ingestion worker 2: extreme boundary values
    def audio_worker_b(iterations: int):
        pool = [-1.0, 0.0, 1.0, 2.0, float("nan"), float("inf"), None]
        try:
            for _ in range(iterations):
                model.set_audio_level(random.choice(pool))
        except Exception as e:
            errors.append(("audio_worker_b", e))

    # Stepper worker: advances smoothing filter
    def stepper_worker(iterations: int):
        try:
            for _ in range(iterations):
                val = model.step_audio_filter()
                if not (0.0 <= val <= 1.0):
                    errors.append(("stepper_bounds", ValueError(f"Value {val} out of bounds")))
        except Exception as e:
            errors.append(("stepper_worker", e))

    # State switcher: rapid state transitions including aliases and fuzz tokens
    def state_worker(iterations: int):
        states = [
            "IDLE", "LISTENING", "THINKING", "SPEAKING", "ERROR", "OFFLINE",
            "SLEEPING", "MUTED", "TALK", "MIC", "UNKNOWN", "", None, 42
        ]
        try:
            for _ in range(iterations):
                model.set_state(random.choice(states))
        except Exception as e:
            errors.append(("state_worker", e))

    # Reader worker: continuous property queries
    def reader_worker(iterations: int):
        try:
            for _ in range(iterations):
                _ = model.get_state()
                _ = model.get_status_text()
                _ = model.get_display_amplitude()
                _ = model.get_theme_colors()
        except Exception as e:
            errors.append(("reader_worker", e))

    threads = [
        threading.Thread(target=audio_worker_a, args=(5000,), name="AudioWorkerA"),
        threading.Thread(target=audio_worker_b, args=(5000,), name="AudioWorkerB"),
        threading.Thread(target=stepper_worker, args=(5000,), name="StepperWorker"),
        threading.Thread(target=state_worker, args=(5000,), name="StateWorker"),
        threading.Thread(target=reader_worker, args=(5000,), name="ReaderWorker"),
    ]

    t0 = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)
        assert not t.is_alive(), f"Thread {t.name} deadlocked or timed out"

    elapsed = time.perf_counter() - t0

    # Pump Qt events to process all cross-thread queued signal dispatches
    app.processEvents()

    assert len(errors) == 0, f"Thread errors encountered: {errors}"
    assert 0.0 <= model.get_display_amplitude() <= 1.0
    assert isinstance(model.get_state(), IslandState)
    assert isinstance(model.get_status_text(), str)

    print(f"\n[STRESS TEST] Concurrent 25,000 multi-thread ops completed in {elapsed:.3f}s. Zero errors.")


# ── Standalone CLI Runner ────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 70)
    print("RUNNING ADVERSARIAL STRESS SUITE FOR IslandPresentationModel")
    print("=" * 70)

    test_audio_level_extreme_boundary_injection()
    print("  [PASS] test_audio_level_extreme_boundary_injection")

    test_audio_level_oscillating_bursts_and_10k_steps()
    print("  [PASS] test_audio_level_oscillating_bursts_and_10k_steps")

    test_filter_decay_convergence_exact_rate()
    print("  [PASS] test_filter_decay_convergence_exact_rate")

    test_filter_decay_from_arbitrary_initial_levels()
    print("  [PASS] test_filter_decay_from_arbitrary_initial_levels")

    test_arbitrary_state_string_fuzzing()
    print("  [PASS] test_arbitrary_state_string_fuzzing")

    test_status_text_override_fuzzing()
    print("  [PASS] test_status_text_override_fuzzing")

    test_thread_safety_high_contention()
    print("  [PASS] test_thread_safety_high_contention")

    print("=" * 70)
    print("ALL 7 ADVERSARIAL STRESS TESTS PASSED SUCCESSFULLY.")
    print("=" * 70)
