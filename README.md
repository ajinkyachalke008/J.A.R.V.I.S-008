# ⚡ J.A.R.V.I.S. — MARK LVI

<div align="center">

<img src="assets/jarvis-logo.png" width="170" height="170" alt="JARVIS Mark-LVI Logo" style="border-radius: 50%;" />

<p align="center">
  <strong>Autonomous Multimodal AI Desktop Assistant • Real-Time Voice • 3D Holographic Avatar • Computer Control</strong>
</p>

[![Status](https://img.shields.io/badge/System_Status-OPERATIONAL-00f2fe?style=for-the-badge&logo=statuspage&logoColor=black)](https://github.com/ajinkyachalke008/Mark-LVI)
[![Release](https://img.shields.io/badge/Release-Mark--LVI_(v56.0)-4facfe?style=for-the-badge&logo=git&logoColor=white)](https://github.com/ajinkyachalke008/Mark-LVI/releases)
[![Python](https://img.shields.io/badge/Python-3.10_%7C_3.11_%7C_3.12-3776ab?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-CC_BY--NC_4.0-f093fb?style=for-the-badge&logo=creative-commons&logoColor=white)](LICENSE)

[![Gemini Live](https://img.shields.io/badge/Multimodal_Engine-Gemini_3.1_Flash_Live-4285F4?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev/)
[![Local Engine](https://img.shields.io/badge/Local_Fallback-Ollama_%7C_LM_Studio_%7C_vLLM-38ef7d?style=flat-square&logo=linux&logoColor=white)](https://github.com/ajinkyachalke008/Mark-LVI)
[![Wake Word](https://img.shields.io/badge/Wake_Word-Offline_OpenWakeWord-ffd166?style=flat-square&logo=soundcharts&logoColor=black)](https://github.com/ajinkyachalke008/Mark-LVI)
[![Platform](https://img.shields.io/badge/OS-Windows_%7C_macOS_%7C_Linux-2b3137?style=flat-square&logo=windows&logoColor=white)](https://github.com/ajinkyachalke008/Mark-LVI)
[![Stars](https://img.shields.io/github/stars/ajinkyachalke008/Mark-LVI?style=flat-square&color=00f2fe)](https://github.com/ajinkyachalke008/Mark-LVI/stargazers)
[![Forks](https://img.shields.io/github/forks/ajinkyachalke008/Mark-LVI?style=flat-square&color=4facfe)](https://github.com/ajinkyachalke008/Mark-LVI/network/members)

<p align="center">
  <a href="#-system-status--live-telemetry"><b>Live Status</b></a> •
  <a href="#-interface--capabilities-showcase"><b>Interface Tour</b></a> •
  <a href="#-key-capabilities"><b>Capabilities</b></a> •
  <a href="#-whats-new-in-mark-lvi"><b>What's New</b></a> •
  <a href="#-quick-start"><b>Quick Start</b></a> •
  <a href="#-project-architecture"><b>Architecture</b></a> •
  <a href="#-security--data-privacy"><b>Security</b></a>
</p>

</div>

---

## 📡 System Status & Live Telemetry

<div align="center">
  <img src="assets/jarvis-status.svg" width="100%" alt="JARVIS Live Telemetry & Status" />
</div>

> [!NOTE]
> Mark LVI introduces native dual-mode execution: an ultra-low latency cloud stream powered by **Gemini 3.1 Flash Live** combined with a zero-cost local fallback engine (**Ollama**, **LM Studio**, **llama.cpp**, **vLLM**).

---

## 📸 Interface & Capabilities Showcase

<div align="center">
  <img src="assets/jarvis-banner.png" width="100%" alt="JARVIS Mark-LVI Hero Banner" />
</div>

<br />

<table align="center" width="100%">
  <tr>
    <td width="50%" align="center">
      <b>🧑‍🎤 3D Holographic Avatar &amp; Live HUD</b><br />
      <img src="assets/jarvis-hud-avatar.png" width="100%" alt="Holographic Avatar HUD" /><br />
      <i>Software-rendered real-time facial rig with dynamic visemes, acoustic frequency visualizer, and push-to-talk integration.</i>
    </td>
    <td width="50%" align="center">
      <b>🖥️ Autonomous Computer Control &amp; Vision</b><br />
      <img src="assets/jarvis-autonomous-control.png" width="100%" alt="Autonomous Computer Control" /><br />
      <i>Real-time screen OCR, bounding box vision coordinates, verified window focus management, and foreground app control.</i>
    </td>
  </tr>
</table>

---

## 🌟 Key Capabilities

### 🧑‍🎤 Holographic Avatar & Facial Geometry
- **Software 3D Engine:** An animated human head rendered via pure software rasterization (`PyQt6.QtGui.QPainter`). No dedicated GPU or heavy game engine required.
- **Formant & Transcript Lip-Sync:** Produces ~50 expressive mouth shapes per second calculated from acoustic audio formants fused with text visemes.
- **Script-Agnostic Articulation:** Unicode reduction maps Latin, Cyrillic, Greek, and other global scripts cleanly onto anatomical mouth phonemes.
- **Natural Micro-Expressions:** Contextual brow elevation during questions, ocular saccadic drift, spontaneous blinking, and rhythmic syllable nods.

### 🎙️ Fluid Voice & Audio Pipeline
- **Global Push-to-Talk:** Tap or hold `Ctrl+Space` anywhere in your OS to engage the microphone. Audio streams only when requested.
- **Local "Hey Jarvis" Wake Word:** Zero-cloud, on-device acoustic keyword spotting powered by `openwakeword`. Sleeps until invoked and never transmits background audio.
- **Acoustic Self-Echo Cancellation:** Adaptive reference subtractor distinguishes your speech from the assistant's own synthesized voice in real time.
- **Instant Latency Masking:** Synthesizes low-latency immediate audio acknowledgments in the user's spoken language while complex reasoning plans compute.

### 🖥️ Verified Autonomous Computer Control
- **Observation-Driven Action:** Tools report observed ground-truth rather than simple invocation state (`done` indicates verified UI state, `unverified` signifies an unconfirmed attempt).
- **Multi-Process Foreground Focus:** Inspects complete Windows process hierarchies and raises launched apps (like Google Chrome) to `HWND_TOPMOST` foreground visibility.
- **Multimodal Visual Grounding:** Coordinates real-time screen captures, UI element bounding boxes, and OCR target recognition.
- **Safety Confirmation Gates:** Critical disk, filesystem, or network operations trigger interactive UI confirmation dialogues before execution.

---

## 🔄 What's New in Mark LVI

### 1. Dual Engine Architecture (Cloud + Local)
Mark LVI untethers the assistant from proprietary cloud locks:
- **Cloud Mode:** Runs directly on Gemini 3.1 Flash Live for natural sub-second audio conversation.
- **Local Mode:** Switches seamlessly to on-device LLMs through any standard OpenAI-compatible server endpoint:
  - [Ollama](https://ollama.ai) (`http://localhost:11434/v1`)
  - [LM Studio](https://lmstudio.ai) (`http://localhost:1234/v1`)
  - [llama.cpp](https://github.com/ggerganov/llama.cpp) / [vLLM](https://github.com/vllm-project/vllm)
- **Zero Idle Overhead:** If local providers are not configured, the `providers/` module is never loaded (measured import boot time impact: **0.16 ms**).

### 2. Upgraded Model Ladder & Fault-Tolerant Fallbacks
- Replaced outdated API models with high-availability production endpoints (`gemini-flash-lite-latest` and `gemini-3.8-flash`).
- Dynamic rate-limit and quota backoff prevents crashes when quotas are saturated.

### 3. Foreground Window & Multi-Process Visibility
- Refactored `actions/browser_control.py` and `core/appidentity.py` with multi-PID hierarchy tracking.
- Bypassed hidden process monkey-patching so user applications retain visible graphical windows upon launch.

### 4. Background Automation & Dispatch Tools
- Added [`plugins/github_manager.py`](file:///C:/Users/AJINKYA%20CHALKE/AI/Mark-LVI/plugins/github_manager.py) for autonomous repository inspection, issue review, and pull request tracking.
- Added [`plugins/file_dispatcher.py`](file:///C:/Users/AJINKYA%20CHALKE/AI/Mark-LVI/plugins/file_dispatcher.py) and [`plugins/desktop_downloader.py`](file:///C:/Users/AJINKYA%20CHALKE/AI/Mark-LVI/plugins/desktop_downloader.py) for workspace organization and download automation.

---

## ⚙️ Architecture & Engine Providers

```
                     ┌────────────────────────────────────────┐
                     │          JARVIS Core Runtime           │
                     │  (PyQt6 HUD • 3D Mesh • Tray Daemon)   │
                     └───────────────────┬────────────────────┘
                                         │
             ┌───────────────────────────┴───────────────────────────┐
             ▼                                                       ▼
┌─────────────────────────┐                             ┌─────────────────────────┐
│     Cloud Pipeline      │                             │     Local Pipeline      │
│  Gemini 3.1 Flash Live  │                             │   Whisper / Ollama /    │
│  (WebSocket Full-Duplex)│                             │   LM Studio / Kokoro    │
└────────────┬────────────┘                             └────────────┬────────────┘
             │                                                       │
             └───────────────────────────┬───────────────────────────┘
                                         ▼
                     ┌────────────────────────────────────────┐
                     │      Autonomous Execution Layer        │
                     │  • Process Focus & Topmost Z-Order     │
                     │  • Screen OCR & Grounded Bounding Boxes│
                     │  • Verified Outcome Status Engine      │
                     └────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- Python `3.10`, `3.11`, or `3.12`
- Windows 10/11, macOS, or modern Linux
- A Google Gemini API Key ([Get one for free at Google AI Studio](https://aistudio.google.com/app/apikey))

### 1. Clone the Repository
```bash
git clone https://github.com/ajinkyachalke008/Mark-LVI.git
cd Mark-LVI
```

### 2. Set Up Virtual Environment
```bash
python -m venv .venv

# On Windows:
.venv\Scripts\activate

# On macOS/Linux:
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure API Keys
On your first run, a setup wizard appears automatically. Alternatively, you can configure [`config/api_keys.json`](file:///C:/Users/AJINKYA%20CHALKE/AI/Mark-LVI/config/api_keys.json):
```json
{
  "gemini_api_key": "YOUR_GEMINI_API_KEY",
  "assistant_name": "Jarvis",
  "voice": "Puck",
  "wake_word_enabled": true
}
```

### 5. Launch JARVIS
```bash
# Standard interactive launch:
python main.py

# Or run via Windows batch launcher:
launch.bat
```

> [!TIP]
> For silent background operation on Windows, run [`run.vbs`](file:///C:/Users/AJINKYA%20CHALKE/AI/Mark-LVI/run.vbs). JARVIS will live in your system notification tray.

---

## 📂 Project Architecture

```text
Mark-LVI/
├── actions/                  # Core computer control and automation tools
│   ├── browser_control.py    # Playwright browser driver & foreground window focus
│   ├── computer_control.py   # Native OS key, mouse, and window orchestration
│   ├── screen_processor.py   # Desktop visual capture and OCR coordinate mapping
│   └── open_app.py           # Application launcher with process verification
├── assets/                   # High-resolution logos, banners, animated SVGs, and screenshots
│   ├── jarvis-logo.png       # Circular Arc-Reactor emblem logo
│   ├── jarvis-banner.png     # Widescreen cinematic hero banner
│   ├── jarvis-status.svg     # Animated SVG live telemetry component
│   ├── jarvis-hud-avatar.png # 3D Avatar HUD interface screenshot
│   └── jarvis-autonomous-control.png # Autonomous computer control screenshot
├── config/                   # Configuration parameters, icons, and TLS keys
│   ├── api_keys.json         # Local credentials and settings (git-ignored)
│   └── jarvis.ico            # Native Windows application icon
├── core/                     # Internal engine logic and multimodal pipelines
│   ├── appidentity.py        # Process tree inspector and Z-order focus manager
│   ├── avatar.py             # Software 3D facial renderer & QPainter engine
│   ├── avatar_mesh.py        # Canonical 468-vertex 3D facial geometry
│   ├── gemini.py             # Gemini API client with fallback model ladders
│   ├── wake_word.py          # Offline openwakeword keyword detection
│   └── viseme.py             # Formant-to-mouth phoneme mapping engine
├── plugins/                  # Extensible plugins and developer tools
│   ├── github_manager.py     # GitHub workflow automation and repository inspection
│   ├── file_dispatcher.py    # Autonomous filesystem management
│   └── desktop_downloader.py # Automated file retrieval utilities
├── dashboard/                # Web & mobile remote companion interface
├── launch.bat                # Windows fast console launcher
├── run.vbs                   # Silent Windows tray background launcher
├── main.py                   # Main entry point and runtime loop
├── ui.py                     # PyQt6 user interface, HUD, and system tray
└── requirements.txt          # Python runtime dependencies
```

---

## 🔒 Security & Data Privacy

- **Zero-Cloud Audio Idle:** Audio is never recorded or streamed while JARVIS is sleeping. The wake word engine operates 100% locally on your CPU.
- **Local Secret Storage:** All keys and tokens are stored exclusively in [`config/api_keys.json`](file:///C:/Users/AJINKYA%20CHALKE/AI/Mark-LVI/config/api_keys.json) on your physical machine.
- **Repository Integrity:** [`config/api_keys.json`](file:///C:/Users/AJINKYA%20CHALKE/AI/Mark-LVI/config/api_keys.json), OAuth tokens, local session files, `.env`, logs, and temporary caches are strictly excluded by [`.gitignore`](file:///C:/Users/AJINKYA%20CHALKE/AI/Mark-LVI/.gitignore).
- **Verified Operation Gates:** Destructive file modifications or sensitive external commands require manual interactive confirmation before execution.

---

## 📄 License & Attribution

- **License:** Licensed under [Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)](LICENSE).
- **Original Project:** Created by [FatihMakes](https://www.youtube.com/@FatihMakes) ([@fatihmakes](https://www.instagram.com/fatihmakes)).
- **Custom Enhancements & Automation:** Maintained and enhanced by [@ajinkyachalke008](https://github.com/ajinkyachalke008).

<div align="center">
  <sub>Engineered with precision for autonomous intelligence and human-machine cooperation.</sub>
</div>
