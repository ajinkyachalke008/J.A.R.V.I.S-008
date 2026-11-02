"""
plugins/file_dispatcher.py — Universal File Attachment & Dispatcher with User Verification Gate.

Capabilities:
  1. Locates any requested file by full path or by filename across common user directories
     (Desktop, Downloads, Documents, Pictures, Videos, JarvisProjects, and Workspace).
  2. Packages the file into the Windows CF_HDROP clipboard format (native file-drop).
  3. Switches to the specified application:
     - WhatsApp Desktop / Web (opens conversation if contact provided)
     - Claude (claude.ai)
     - ChatGPT (chatgpt.com)
     - Active / current foreground window
  4. Simulates Ctrl+V to attach/upload the file into the message or prompt box.
  5. Optionally pastes an accompanying caption, message, or prompt.
  6. MANDATORY SAFETY GATE: Parks the final transmission behind `core.confirm.request`.
     The user must physically click CONFIRM on the HUD before Enter/Send is pressed.
"""

from __future__ import annotations

import ctypes
import os
import platform
import subprocess
import sys
import time
import webbrowser
from ctypes import wintypes
from pathlib import Path
from typing import Optional

from core import confirm
from core import outcome

_OS = platform.system()

PLUGIN = {
    "name": "file_dispatcher",
    "description": (
        "Attaches, uploads, or sends files (documents, PDFs, images, code files, spreadsheets, "
        "presentations, archives) to WhatsApp, Claude, ChatGPT, or the active window. "
        "Locates the file on the computer, switches to the target app, attaches the file, "
        "and pauses for mandatory user verification on screen before sending."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_name_or_path": {
                "type": "STRING",
                "description": "The name of the file (e.g. 'report.pdf', 'photo.png') or an absolute file path.",
            },
            "target_app": {
                "type": "STRING",
                "description": "Target application: 'whatsapp', 'claude', 'chatgpt', or 'active_window'.",
            },
            "receiver": {
                "type": "STRING",
                "description": "Optional: For WhatsApp, the contact or group name to send to (e.g. 'Mom', 'Alex', 'Project Team').",
            },
            "caption": {
                "type": "STRING",
                "description": "Optional: Message, prompt, or caption to accompany the attached file.",
            },
        },
        "required": ["file_name_or_path", "target_app"],
    },
}


class DROPFILES(ctypes.Structure):
    _fields_ = [
        ("pFiles", wintypes.DWORD),
        ("pt", wintypes.POINT),
        ("fNC", wintypes.BOOL),
        ("fWide", wintypes.BOOL),
    ]


def _format_size(path: Path) -> str:
    """Format file size in human-readable units."""
    try:
        bytes_val = path.stat().st_size
        if bytes_val < 1024:
            return f"{bytes_val} B"
        if bytes_val < 1024 * 1024:
            return f"{bytes_val / 1024:.1f} KB"
        return f"{bytes_val / (1024 * 1024):.1f} MB"
    except Exception:
        return "Unknown size"


def _find_file(query: str) -> Optional[Path]:
    """Resolve a file query to an existing Path object. Searches common user folders."""
    q_str = str(query or "").strip().strip("\"'")
    if not q_str:
        return None

    # 1. Direct path check
    direct = Path(q_str)
    if direct.is_file():
        return direct.resolve()

    expanded = Path(os.path.expandvars(q_str)).expanduser()
    if expanded.is_file():
        return expanded.resolve()

    # 2. Search common user directories
    home = Path.home()
    search_roots = [
        home / "Desktop",
        home / "Downloads",
        home / "Documents",
        home / "Pictures",
        home / "Videos",
        home / "Desktop" / "JarvisProjects",
        Path.cwd(),
    ]

    clean_name = Path(q_str).name.lower()
    exact_matches: list[Path] = []
    fuzzy_matches: list[Path] = []

    for root in search_roots:
        if not root.exists():
            continue
        try:
            # Check immediate directory first
            for item in root.iterdir():
                if item.is_file():
                    name_lower = item.name.lower()
                    if name_lower == clean_name:
                        exact_matches.append(item.resolve())
                    elif clean_name in name_lower:
                        fuzzy_matches.append(item.resolve())

            # Check 1 level of subdirectories
            for sub in root.iterdir():
                if sub.is_dir() and not sub.name.startswith("."):
                    try:
                        for item in sub.iterdir():
                            if item.is_file():
                                name_lower = item.name.lower()
                                if name_lower == clean_name:
                                    exact_matches.append(item.resolve())
                                elif clean_name in name_lower:
                                    fuzzy_matches.append(item.resolve())
                    except Exception:
                        continue
        except Exception:
            continue

    if exact_matches:
        exact_matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return exact_matches[0]

    if fuzzy_matches:
        fuzzy_matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return fuzzy_matches[0]

    return None


def _set_clipboard_file(file_path: Path) -> bool:
    """Set the file onto the Windows clipboard using native CF_HDROP format."""
    if _OS != "Windows":
        return False
    try:
        import win32clipboard
        import win32con

        resolved_str = str(file_path.resolve()) + "\0\0"
        encoded = resolved_str.encode("utf-16le")

        df = DROPFILES()
        df.pFiles = ctypes.sizeof(DROPFILES)
        df.pt = wintypes.POINT(0, 0)
        df.fNC = False
        df.fWide = True

        blob = bytes(df) + encoded

        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_HDROP, blob)
        finally:
            win32clipboard.CloseClipboard()
        return True
    except Exception as exc:
        print(f"[file_dispatcher] CF_HDROP clipboard error: {exc}")
        return False


def _focus_window_by_title(fragment: str) -> bool:
    """Attempt to find and bring a window with matching title to the foreground."""
    frag_lower = fragment.lower().strip()
    try:
        import pygetwindow as gw
        for win in gw.getAllWindows():
            if win.title and frag_lower in win.title.lower():
                try:
                    win.restore()
                    win.activate()
                    time.sleep(0.5)
                    return True
                except Exception:
                    pass
    except Exception:
        pass

    # Windows user32 fallback
    if _OS == "Windows":
        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            found_hwnd = None

            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

            def _enum(hwnd, _lparam):
                nonlocal found_hwnd
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        if frag_lower in buf.value.lower():
                            found_hwnd = hwnd
                            return False
                return True

            user32.EnumWindows(WNDENUMPROC(_enum), 0)
            if found_hwnd:
                SW_RESTORE = 9
                user32.ShowWindow(found_hwnd, SW_RESTORE)
                user32.SetForegroundWindow(found_hwnd)
                time.sleep(0.5)
                return True
        except Exception:
            pass

    return False


def _prepare_target_app(target: str, receiver: str = "") -> tuple[bool, str]:
    """Focus or open the target application and prepare the input container."""
    t_clean = target.lower().strip()

    import pyautogui
    import pyperclip

    if "whatsapp" in t_clean:
        # Focus existing or launch WhatsApp
        focused = _focus_window_by_title("WhatsApp")
        if not focused:
            try:
                # Protocol launch
                os.system("start whatsapp:")
                time.sleep(2.5)
                _focus_window_by_title("WhatsApp")
            except Exception:
                pass

        time.sleep(0.8)

        # Navigate to recipient if provided
        if receiver:
            pyautogui.hotkey("ctrl", "f")
            time.sleep(0.4)
            pyperclip.copy(receiver)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.8)
            pyautogui.press("enter")
            time.sleep(0.8)

        return True, "WhatsApp"

    elif "claude" in t_clean:
        focused = _focus_window_by_title("Claude")
        if not focused:
            webbrowser.open("https://claude.ai/new")
            time.sleep(3.5)
            _focus_window_by_title("Claude")
        return True, "Claude"

    elif "chatgpt" in t_clean:
        focused = _focus_window_by_title("ChatGPT")
        if not focused:
            webbrowser.open("https://chatgpt.com")
            time.sleep(3.5)
            _focus_window_by_title("ChatGPT")
        return True, "ChatGPT"

    elif "active" in t_clean or "current" in t_clean:
        # Leave focus in whatever window user currently has
        time.sleep(0.3)
        return True, "Active Window"

    else:
        # Generic app name search
        focused = _focus_window_by_title(target)
        if not focused:
            return False, f"Could not locate or open application '{target}'"
        return True, target


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Execute the file attachment and park final transmission behind the confirmation gate."""
    raw_query = parameters.get("file_name_or_path", "")
    target_app = parameters.get("target_app", "active_window")
    receiver = parameters.get("receiver", "").strip()
    caption = parameters.get("caption", "").strip()

    if not raw_query:
        return outcome.failed("file_dispatcher", "No file name or path was provided.")

    # 1. Locate file
    file_path = _find_file(raw_query)
    if not file_path or not file_path.exists():
        return outcome.failed(
            "file_dispatcher",
            f"Could not locate file '{raw_query}'. Checked Desktop, Downloads, Documents, and project folders.",
            query=raw_query,
        )

    # 2. Package into native CF_HDROP clipboard format
    if not _set_clipboard_file(file_path):
        return outcome.failed(
            "file_dispatcher",
            f"Failed to place {file_path.name} on the Windows clipboard.",
            path=str(file_path),
        )

    # 3. Switch to target app & paste attachment
    ok, app_name = _prepare_target_app(target_app, receiver=receiver)
    if not ok:
        return outcome.failed("file_dispatcher", app_name, target=target_app)

    try:
        import pyautogui
        import pyperclip

        # Paste the file drop into the chat/prompt
        time.sleep(0.5)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.8)

        # Paste caption if specified
        if caption:
            pyperclip.copy(caption)
            time.sleep(0.2)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.3)
    except Exception as exc:
        return outcome.failed("file_dispatcher", f"Error pasting attachment into {app_name}: {exc}")

    if player:
        try:
            player.write_log(f"ATTACH: {file_path.name} ({_format_size(file_path)}) attached in {app_name}.")
        except Exception:
            pass

    # 4. Mandatory User Verification Gate
    target_summary = f"{app_name}" + (f" ({receiver})" if receiver else "")

    def _do_send():
        try:
            import pyautogui
            time.sleep(0.2)
            pyautogui.press("enter")
            return f"Done: {file_path.name} sent to {target_summary}."
        except Exception as exc:
            return f"Failed to send: {exc}"

    # Hand off to MARK LVI's native on-screen confirmation banner
    return confirm.request(
        key=f"dispatch_{file_path.name}_{app_name}",
        title=f"Send {file_path.name} to {target_summary}?",
        detail=(
            f"File: {file_path.name} ({_format_size(file_path)})\n"
            f"Destination: {target_summary}\n"
            f"Location: {file_path.parent}\n"
            + (f"Caption: \"{caption}\"\n" if caption else "")
            + "\nTap CONFIRM to transmit now, or CANCEL to keep as draft."
        ),
        run=_do_send,
    )

