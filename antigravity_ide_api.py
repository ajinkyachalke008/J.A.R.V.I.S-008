"""
Antigravity IDE Automation & Direct Input API
=============================================
Provides direct programmatic input and command execution into Google Antigravity IDE.

Exposes:
    - insert_prompt_to_chat(prompt_text: str, submit: bool = True, method: str = "auto") -> bool
    - execute_terminal_command(command_text: str, submit: bool = True) -> bool
    - start_api_server(host: str, port: int, background: bool) -> None
    - AntigravityIDE: Full object-oriented interface
"""

from __future__ import annotations

import ctypes
import json
import logging
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [AntigravityAPI] %(message)s")
logger = logging.getLogger("AntigravityAPI")

# Win32 Constants
VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_MENU = 0x12  # Alt
VK_RETURN = 0x0D
VK_V = 0x56
VK_L = 0x4C
VK_OEM_3 = 0xC0  # Backtick ` ~
KEYEVENTF_KEYUP = 0x0002
SW_RESTORE = 9
SW_SHOW = 5

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

ANTIGRAV_BIN = r"C:\Users\AJINKYA CHALKE\AppData\Local\Programs\Antigravity IDE\bin\antigravity-ide.cmd"


class AntigravityIDE:
    """
    Interface for automating and communicating with the Antigravity IDE instance.
    """

    def __init__(self, ide_bin_path: Optional[str] = None) -> None:
        self.bin_path = ide_bin_path or ANTIGRAV_BIN
        if not os.path.exists(self.bin_path):
            alt_path = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Antigravity IDE\bin\antigravity-ide.cmd")
            if os.path.exists(alt_path):
                self.bin_path = alt_path

    # --------------------------------------------------------------------------
    # Window Management & Win32 Helpers
    # --------------------------------------------------------------------------

    def find_ide_window(self) -> Optional[Tuple[int, str]]:
        """
        Locates the top-level window handle for the active Antigravity IDE.
        """
        found: list[Tuple[int, str]] = []

        # Win32 EnumDesktopWindows callback
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)

        def _enum_cb(hwnd: int, _: int) -> bool:
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value
                    if "Antigravity IDE" in title:
                        found.append((hwnd, title))
            return True

        cb = WNDENUMPROC(_enum_cb)

        # Attempt enumeration across default desktop station
        try:
            import win32service, win32con, win32gui
            hwinsta = win32service.OpenWindowStation('winsta0', False, win32con.MAXIMUM_ALLOWED)
            hwinsta.SetProcessWindowStation()
            hdesk = win32service.OpenDesktop('default', 0, False, win32con.MAXIMUM_ALLOWED)
            hdesk.SetThreadDesktop()
            win32gui.EnumDesktopWindows(hdesk, lambda h, _: _enum_cb(h, 0), 0)
        except Exception:
            user32.EnumWindows(cb, 0)

        if found:
            return found[0]
        return None

    def bring_ide_to_foreground(self, hwnd: Optional[int] = None) -> bool:
        """
        Brings the Antigravity IDE window to the foreground, restoring if minimized
        and bypassing Windows OS foreground locks.
        """
        if hwnd is None:
            ide_info = self.find_ide_window()
            if not ide_info:
                logger.warning("No running Antigravity IDE window detected.")
                return False
            hwnd = ide_info[0]

        try:
            # Force restore if minimized
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.BringWindowToTop(hwnd)

            # Thread attachment technique to reliably grant foreground rights
            fg_hwnd = user32.GetForegroundWindow()
            if fg_hwnd != hwnd:
                fg_tid = user32.GetWindowThreadProcessId(fg_hwnd, None)
                cur_tid = kernel32.GetCurrentThreadId()
                if fg_tid != cur_tid:
                    user32.AttachThreadInput(cur_tid, fg_tid, True)
                    user32.SetForegroundWindow(hwnd)
                    user32.AttachThreadInput(cur_tid, fg_tid, False)
                else:
                    user32.SetForegroundWindow(hwnd)
            time.sleep(0.12)
            return True
        except Exception as e:
            logger.error("Failed to bring IDE to foreground: %s", e)
            return False

    @staticmethod
    def _send_key_combo(vk_modifier: int, vk_key: int) -> None:
        """Sends a modifier + key combination (e.g. Ctrl + L)."""
        user32.keybd_event(vk_modifier, 0, 0, 0)
        time.sleep(0.04)
        user32.keybd_event(vk_key, 0, 0, 0)
        time.sleep(0.04)
        user32.keybd_event(vk_key, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.04)
        user32.keybd_event(vk_modifier, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.06)

    @staticmethod
    def _send_key(vk_key: int) -> None:
        """Sends a single keypress (e.g. Enter)."""
        user32.keybd_event(vk_key, 0, 0, 0)
        time.sleep(0.03)
        user32.keybd_event(vk_key, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.05)

    @staticmethod
    def _set_clipboard_text(text: str) -> bool:
        """Injects text into Windows clipboard using win32/ctypes."""
        try:
            import pyperclip
            pyperclip.copy(text)
            return True
        except Exception:
            pass

        # Fallback native ctypes clipboard
        GMEM_MOVEABLE = 0x0002
        CF_UNICODETEXT = 13
        if not user32.OpenClipboard(0):
            return False
        try:
            user32.EmptyClipboard()
            encoded = text.encode("utf-16le") + b"\x00\x00"
            h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
            ptr = kernel32.GlobalLock(h_mem)
            ctypes.memmove(ptr, encoded, len(encoded))
            kernel32.GlobalUnlock(h_mem)
            user32.SetClipboardData(CF_UNICODETEXT, h_mem)
            return True
        finally:
            user32.CloseClipboard()

    # --------------------------------------------------------------------------
    # Core API Endpoints
    # --------------------------------------------------------------------------

    def insert_prompt_to_chat(
        self,
        prompt_text: str,
        submit: bool = True,
        method: str = "auto",
    ) -> bool:
        """
        Accepts a string and directly inserts it into the user input field of
        the active chat window in Antigravity IDE, as if the user typed it.

        Args:
            prompt_text: The prompt string to insert.
            submit: Whether to immediately press Enter and submit (default True).
            method: 'auto', 'ui', or 'cli'.
                    - 'ui': Simulates user UI focus (Ctrl+L), paste (Ctrl+V), and Enter.
                    - 'cli': Invokes `antigravity-ide chat -r` IPC interface.
                    - 'auto': Attempts 'ui' if IDE is running, falls back to 'cli'.

        Returns:
            bool: True if prompt was successfully inserted/submitted, False otherwise.
        """
        if not prompt_text:
            logger.warning("Empty prompt_text provided to insert_prompt_to_chat.")
            return False

        if method == "cli":
            return self._send_prompt_via_cli(prompt_text)

        # UI Method
        ide_window = self.find_ide_window()
        if not ide_window and method == "auto":
            logger.info("IDE window not directly detected for UI injection; falling back to CLI IPC.")
            return self._send_prompt_via_cli(prompt_text)

        if not self.bring_ide_to_foreground():
            if method == "auto":
                return self._send_prompt_via_cli(prompt_text)
            return False

        try:
            # 1. Focus the active Chat Input field (Ctrl + L in Antigravity IDE)
            self._send_key_combo(VK_CONTROL, VK_L)
            time.sleep(0.15)

            # 2. Populate clipboard and paste into input field (Ctrl + V)
            if not self._set_clipboard_text(prompt_text):
                logger.error("Failed to copy prompt to clipboard.")
                return False

            self._send_key_combo(VK_CONTROL, VK_V)
            time.sleep(0.10)

            # 3. Submit prompt if requested
            if submit:
                self._send_key(VK_RETURN)
                logger.info("Successfully inserted and submitted prompt to chat.")
            else:
                logger.info("Successfully inserted prompt into chat input field (awaiting user send).")

            return True
        except Exception as e:
            logger.error("Error during UI prompt insertion: %s", e)
            if method == "auto":
                return self._send_prompt_via_cli(prompt_text)
            return False

    def execute_terminal_command(
        self,
        command_text: str,
        submit: bool = True,
    ) -> bool:
        """
        Allows programmatic execution of commands in the built-in terminal
        of the Antigravity IDE.

        Args:
            command_text: The command line string to execute.
            submit: Whether to simulate pressing Enter (default True).

        Returns:
            bool: True if command was successfully sent to the terminal.
        """
        if not command_text:
            logger.warning("Empty command_text provided to execute_terminal_command.")
            return False

        if not self.bring_ide_to_foreground():
            logger.error("Cannot execute terminal command: Antigravity IDE window not reachable.")
            return False

        try:
            # 1. Focus the Integrated Terminal (Ctrl + ` [Backtick])
            self._send_key_combo(VK_CONTROL, VK_OEM_3)
            time.sleep(0.18)

            # 2. Copy command and paste into terminal (Ctrl + V)
            if not self._set_clipboard_text(command_text):
                logger.error("Failed to copy terminal command to clipboard.")
                return False

            self._send_key_combo(VK_CONTROL, VK_V)
            time.sleep(0.08)

            # 3. Execute command
            if submit:
                self._send_key(VK_RETURN)
                logger.info("Successfully executed terminal command: %s", command_text)
            else:
                logger.info("Inserted command into terminal without submit: %s", command_text)

            return True
        except Exception as e:
            logger.error("Error executing terminal command: %s", e)
            return False

    def _send_prompt_via_cli(self, prompt_text: str) -> bool:
        """Sends prompt through Antigravity IDE CLI IPC."""
        if not os.path.exists(self.bin_path):
            logger.error("Antigravity CLI binary not found at: %s", self.bin_path)
            return False

        try:
            cmd = [self.bin_path, "chat", "-r", prompt_text]
            res = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=15)
            if res.returncode == 0:
                logger.info("Prompt submitted successfully via Antigravity CLI IPC.")
                return True
            else:
                logger.error("CLI IPC failed with code %d: %s", res.returncode, res.stderr)
                return False
        except Exception as e:
            logger.error("CLI IPC invocation error: %s", e)
            return False


# ------------------------------------------------------------------------------
# Module-Level Convenience Functions
# ------------------------------------------------------------------------------

_default_ide = AntigravityIDE()

def insert_prompt_to_chat(prompt_text: str, submit: bool = True, method: str = "auto") -> bool:
    """
    Direct input function for JARVIS and external applications.
    Inserts prompt_text into the active chat input field of Antigravity IDE.
    """
    return _default_ide.insert_prompt_to_chat(prompt_text, submit=submit, method=method)


def execute_terminal_command(command_text: str, submit: bool = True) -> bool:
    """
    Direct execution function for JARVIS and external applications.
    Executes command_text in the built-in terminal of Antigravity IDE.
    """
    return _default_ide.execute_terminal_command(command_text, submit=submit)


# ------------------------------------------------------------------------------
# Built-in REST / HTTP Bridge Server
# ------------------------------------------------------------------------------

class _BridgeHTTPRequestHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code: int, data: Dict[str, Any]) -> None:
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/api/status", "/status"):
            ide_info = _default_ide.find_ide_window()
            self._send_json(200, {
                "status": "online",
                "ide_running": ide_info is not None,
                "ide_window": ide_info[1] if ide_info else None,
            })
        elif parsed.path in ("/api/health", "/health"):
            self._send_json(200, {"status": "healthy"})
        else:
            self._send_json(404, {"error": "Not Found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length)

        try:
            body = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except Exception:
            self._send_json(400, {"error": "Invalid JSON body"})
            return

        if parsed.path in ("/api/chat", "/chat"):
            prompt = body.get("prompt_text") or body.get("prompt") or ""
            submit = body.get("submit", True)
            method = body.get("method", "auto")

            if not prompt:
                self._send_json(400, {"error": "Missing 'prompt_text' or 'prompt' in request"})
                return

            success = insert_prompt_to_chat(prompt, submit=submit, method=method)
            self._send_json(200 if success else 500, {
                "success": success,
                "prompt": prompt,
                "submitted": submit,
            })

        elif parsed.path in ("/api/terminal", "/terminal"):
            command = body.get("command_text") or body.get("command") or ""
            submit = body.get("submit", True)

            if not command:
                self._send_json(400, {"error": "Missing 'command_text' or 'command' in request"})
                return

            success = execute_terminal_command(command, submit=submit)
            self._send_json(200 if success else 500, {
                "success": success,
                "command": command,
                "executed": submit,
            })
        else:
            self._send_json(404, {"error": "Not Found"})

    def log_message(self, format: str, *args: Any) -> None:
        # Route HTTP server logs to module logger
        logger.debug(format, *args)


def start_api_server(host: str = "127.0.0.1", port: int = 24680, background: bool = True) -> HTTPServer:
    """
    Spawns a local REST API server allowing any application or language to trigger
    chat prompt insertion and terminal command execution over HTTP.
    """
    server = HTTPServer((host, port), _BridgeHTTPRequestHandler)
    logger.info("Antigravity Direct Input HTTP Server listening on http://%s:%d", host, port)

    if background:
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        return server
    else:
        server.serve_forever()
        return server


# ------------------------------------------------------------------------------
# CLI Entrypoint for Testing and Standalone Service
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Antigravity IDE Direct Input & Automation API")
    parser.add_argument("--prompt", type=str, help="Prompt text to insert into active chat")
    parser.add_argument("--no-submit", action="store_true", help="Insert prompt without pressing Enter")
    parser.add_argument("--command", type=str, help="Command text to execute in built-in terminal")
    parser.add_argument("--server", action="store_true", help="Start local HTTP bridge server")
    parser.add_argument("--port", type=int, default=24680, help="Port for HTTP server (default 24680)")

    args = parser.parse_args()

    if args.prompt:
        ok = insert_prompt_to_chat(args.prompt, submit=not args.no_submit)
        sys.exit(0 if ok else 1)
    elif args.command:
        ok = execute_terminal_command(args.command)
        sys.exit(0 if ok else 1)
    elif args.server:
        print(f"Starting Antigravity Direct Input Server on http://127.0.0.1:{args.port}...")
        start_api_server(port=args.port, background=False)
    else:
        ide_window = _default_ide.find_ide_window()
        print("Antigravity IDE API Initialized.")
        print(f"Detected IDE Window: {ide_window[1] if ide_window else 'Not currently running'}")
        print("Run with --help to see CLI options or import this module in Python.")

