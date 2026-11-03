"""
tools/antigravity_input_gui.py — Desktop GUI tool for JARVIS Antigravity Direct Input & Terminal Bridge.

Provides a quick on-desktop interface to:
  1. Insert and submit prompts directly into Antigravity IDE chat.
  2. Execute commands programmatically in Antigravity IDE integrated terminal.
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

import antigravity_ide_api


class AntigravityInputWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S. — 008 // Antigravity Direct Input Channel")
        self.setFixedSize(540, 420)

        ico_path = PROJECT_ROOT / "config" / "jarvis.ico"
        if ico_path.exists():
            self.setWindowIcon(QIcon(str(ico_path)))

        self.setStyleSheet("""
            QWidget {
                background-color: #000914;
                color: #8ffcff;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            QLabel {
                color: #00d4ff;
                font-weight: bold;
                font-size: 13px;
            }
            QTextEdit, QLineEdit {
                background-color: #011520;
                color: #ffffff;
                border: 1px solid #0d3347;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Consolas', monospace;
                font-size: 13px;
            }
            QTextEdit:focus, QLineEdit:focus {
                border: 1px solid #00d4ff;
            }
            QPushButton {
                background-color: #0d3347;
                color: #00f2fe;
                border: 1px solid #00f2fe;
                border-radius: 4px;
                padding: 10px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #00f2fe;
                color: #000914;
            }
            QPushButton:disabled {
                border-color: #334455;
                color: #556677;
            }
            QCheckBox {
                color: #a0d8ef;
                font-size: 12px;
            }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(18, 18, 18, 18)

        # Title
        title = QLabel("⚡ JARVIS — ANTIGRAVITY IDE DIRECT INPUT")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        layout.addWidget(title)

        # Section 1: Chat Prompt
        layout.addWidget(QLabel("💬 Prompt to Active Chat:"))
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("Type prompt here... (e.g. 'Analyze the security of main.py')")
        self.prompt_edit.setFixedHeight(110)
        layout.addWidget(self.prompt_edit)

        prompt_btn_row = QHBoxLayout()
        self.submit_check = QCheckBox("Submit immediately (Enter)")
        self.submit_check.setChecked(True)
        prompt_btn_row.addWidget(self.submit_check)

        self.btn_send_chat = QPushButton("🚀 Send to Antigravity Chat")
        self.btn_send_chat.clicked.connect(self._on_send_chat)
        prompt_btn_row.addWidget(self.btn_send_chat)
        layout.addLayout(prompt_btn_row)

        layout.addSpacing(6)

        # Section 2: Terminal Command
        layout.addWidget(QLabel("💻 Built-in Terminal Command:"))
        self.cmd_edit = QLineEdit()
        self.cmd_edit.setPlaceholderText("Command to execute... (e.g. 'git status', 'pytest')")
        self.cmd_edit.returnPressed.connect(self._on_run_terminal)
        layout.addWidget(self.cmd_edit)

        self.btn_run_term = QPushButton("⚡ Run in Integrated Terminal")
        self.btn_run_term.clicked.connect(self._on_run_terminal)
        layout.addWidget(self.btn_run_term)

        # Status Label
        self.status_lbl = QLabel("Status: Ready. Target: Antigravity IDE")
        self.status_lbl.setStyleSheet("color: #4facfe; font-size: 11px; font-weight: normal;")
        layout.addWidget(self.status_lbl)

        self.setLayout(layout)

    def _on_send_chat(self):
        text = self.prompt_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Empty Prompt", "Please enter a prompt to send to the chat.")
            return

        submit = self.submit_check.isChecked()
        self.status_lbl.setText("Sending prompt to Antigravity IDE chat...")
        QApplication.processEvents()

        success = antigravity_ide_api.insert_prompt_to_chat(text, submit=submit)
        if success:
            action_desc = "submitted" if submit else "inserted into input field"
            self.status_lbl.setText(f"Success: Prompt {action_desc} in Antigravity Chat.")
            self.prompt_edit.clear()
        else:
            self.status_lbl.setText("Error: Could not reach Antigravity IDE window.")
            QMessageBox.critical(self, "Error", "Failed to insert prompt. Please ensure Antigravity IDE is open.")

    def _on_run_terminal(self):
        cmd = self.cmd_edit.text().strip()
        if not cmd:
            QMessageBox.warning(self, "Empty Command", "Please enter a command to execute in the terminal.")
            return

        self.status_lbl.setText(f"Executing command in terminal: {cmd}...")
        QApplication.processEvents()

        success = antigravity_ide_api.execute_terminal_command(cmd, submit=True)
        if success:
            self.status_lbl.setText(f"Success: Command executed in Antigravity Terminal.")
            self.cmd_edit.clear()
        else:
            self.status_lbl.setText("Error: Could not reach Antigravity IDE terminal.")
            QMessageBox.critical(self, "Error", "Failed to execute command. Please ensure Antigravity IDE is open.")


def main():
    app = QApplication(sys.argv)
    window = AntigravityInputWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

