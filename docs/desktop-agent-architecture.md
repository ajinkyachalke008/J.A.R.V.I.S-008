# J.A.R.V.I.S. — 008 — Universal Desktop Agent, Visual Context Intelligence & Creation Studio Architecture

## 1. Overview & System Mission

J.A.R.V.I.S. — 008 provides an autonomous desktop assistant, context-aware visual intelligence system, and native multi-domain engineering studio for Windows 10 and 11.

The assistant combines real-time multimodal perception with safe, human-like desktop automation and precision creation tools (Mechanical CAD, Circuit Schematics, Workflow Diagrams).

---

## 2. Core Architecture Modules

### 2.1 Desktop Access & Security Framework (`core/desktop/`)

- `core/desktop/access_manager.py`:
  - Central permission and state machine governing all desktop observation and automation.
  - States: `DISABLED`, `OBSERVE_ONLY`, `CONTROL_ENABLED`, `PAUSED`, `ERROR`.
  - Scopes: `SCREEN_CAPTURE`, `ACTIVE_WINDOW_READ`, `UI_AUTOMATION_READ`, `MOUSE_MOVE`, `MOUSE_CLICK`, `MOUSE_DRAG`, `KEYBOARD_INPUT`, `CLIPBOARD_ACCESS`, `FILE_ACCESS`, `EXTERNAL_DATA_SUBMISSION`, `SHELL_EXECUTION`.
  - Time-limited sessions with inactivity timeouts (default 30-min session, 10-min idle timeout).

- `core/desktop/emergency_stop.py`:
  - Instant failsafe interrupt.
  - Global hotkeys (`Ctrl+Alt+Escape`, `Esc`), mouse flick detection to screen corners, and visual HUD stop button.
  - Unconditionally releases all held keys (`pyautogui.keyUp`) and mouse buttons (`pyautogui.mouseUp`), shifts state to `ERROR`, and aborts running tasks.

### 2.2 Advanced Desktop Perception Engine

- `core/desktop/monitor_manager.py`:
  - Enumerate multiple displays, compute total virtual desktop bounds, identify primary monitor and per-monitor DPI scale factors (`SetProcessDpiAwareness(2)`).

- `core/desktop/screen_capture.py`:
  - High-performance screen capture utilizing MSS and PIL.
  - Supports virtual desktop grab, monitor-specific grab, and arbitrary bounding box cropping.

- `core/desktop/ui_automation.py`:
  - Native Windows UI Automation engine using `pywinauto` with `uia` backend and `win32gui`.
  - Traverses the active window control hierarchy, discovering interactive elements (Buttons, Edit fields, CheckBoxes, Menus) with bounding boxes, names, and automation IDs.

- `core/desktop/ocr_engine.py`:
  - Multi-tier text detection cascade (EasyOCR, Windows accessibility text, multimodal vision fallback).

- `core/desktop/visual_grounding.py`:
  - Translates normalized multimodal coordinates ($0..1000$) to physical screen pixels with DPI awareness.
  - Centroid element snapping within a 25px radius for 100% click precision.

### 2.3 Intelligent Cursor & Desktop Control

- `core/desktop/cursor_controller.py`:
  - Generates smooth human-like cubic Bézier curves with perpendicular randomized deviation and ease-in-out velocity profiles.
  - Safe mouse clicks (hover-settle delay before click, double click, right click, smooth drag-and-drop).
  - Resilient keyboard typing with `clear_first` option and clipboard fallback for Unicode / multi-line text via `pyperclip`.

- `core/desktop/action_verifier.py`:
  - Wraps actions in a pre/post verification cycle.
  - Compares window focus, title, and visual pixel differences to emit verified facts (`status=done`, `status=unverified`, `status=failed`).

- `core/desktop/task_planner.py`:
  - Multi-step task planner executing autonomous sequences with safety step budgets (max 10) and loop detection.

### 2.4 Circle-to-Understand (C2U) Interaction

- `core/desktop/selection_overlay.py`:
  - Transparent, frameless, multi-monitor PyQt6 overlay window (`Qt.WindowType.WindowStaysOnTopHint`).
  - Freeform lasso / circle or rectangular box selection with glowing cyan HUD visuals (`#00d4ff`).
  - Freezes desktop canvas, crops drawn region, and dispatches context to the vision pipeline for voice and visual explanation.
  - Triggered via HUD button, voice intent, or `Ctrl+Alt+S` global shortcut.

### 2.5 Universal Creation Studio (`core/studio/`)

- `core/studio/models.py` & `schema.json`:
  - Unified project format for 2D CAD, Circuit Schematics, and Workflows.
  - Structured layers, elements (rect, circle, line, arc, dimension, component, pin, wire), and canvas metadata.

- `core/studio/cad_engine.py`:
  - 2D CAD operations and built-in Precision Mechanical Mounting Plate demonstrator ($120\text{ mm} \times 80\text{ mm}$, corner fillets, 4 M4 holes, center cutout, dimensions).

- `core/studio/circuit_engine.py`:
  - Electrical circuit schematics with component pins, netlist wires, and LM2596 buck regulator demonstrator.

- `core/studio/workflow_engine.py`:
  - Flowcharts, decision nodes, and autonomous agent loop demonstrator.

- `core/studio/exporters/`:
  - `dxf_exporter.py`: AutoCAD R12/2000 compliant standard ASCII DXF.
  - `svg_exporter.py`: Standards-compliant vector graphics with layers.
  - `png_exporter.py`: High-resolution 300 DPI rasterization via QPainter.
  - `json_exporter.py`: Native project JSON serialization.

- `core/studio/studio_window.py`:
  - Native PyQt6 window with interactive `QGraphicsScene` / `QGraphicsView`, pan, zoom, grid snapping, and element inspector.

---

## 3. Discovered Action Extensions

1. `actions/desktop_agent.py`:
   - Auto-discovered by `core/action_loader.py`.
   - Tool declaration: `desktop_agent`.
   - Dispatches atomic control operations (`click_element`, `click_coord`, `type_text`, `hotkey`) and multi-step plans.

2. `actions/creation_studio.py`:
   - Auto-discovered by `core/action_loader.py`.
   - Tool declaration: `creation_studio`.
   - Handles natural language requests to create demonstrators, launch studio, and export CAD/circuits to DXF/SVG/PNG.

