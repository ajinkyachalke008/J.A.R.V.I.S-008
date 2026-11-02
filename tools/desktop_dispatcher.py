"""
tools/desktop_dispatcher.py — Desktop GUI tool for quick file dispatching to WhatsApp, Claude, and ChatGPT.

Can be run directly or with a dragged-and-dropped file argument.
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
    QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from plugins import file_dispatcher


class DispatcherWindow(QWidget):
    def __init__(self, initial_file: str = ""):
        super().__init__()
        self.setWindowTitle("JARVIS — Quick File Dispatcher")
        self.setFixedSize(520, 360)
        
        ico_path = PROJECT_ROOT / "config" / "jarvis.ico"
        if ico_path.exists():
            self.setWindowIcon(QIcon(str(ico_path)))

        self.setStyleSheet("""
            QWidget {
                background-color: #000914;
                color: #8ffcff;
                font-family: 'Courier New', sans-serif;
            }
            QLabel {
                color: #00d4ff;
                font-weight: bold;
            }
            QLineEdit, QComboBox {
                background-color: #011520;
                color: #ffffff;
                border: 1px solid #0d3347;
                border-radius: 4px;
                padding: 6px;
                font-size: 11px;
            }
            QLineEdit:focus, QComboBox:focus {
                border-color: #00d4ff;
            }
            QPushButton {
                background-color: #011520;
                color: #00d4ff;
                border: 1px solid #1a5c7a;
                border-radius: 4px;
                padding: 8px 14px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #001f2e;
                border-color: #00d4ff;
                color: #ffffff;
            }
            QPushButton#actionBtn {
                background-color: #002b40;
                color: #00ff88;
                border: 1px solid #00aa55;
            }
            QPushButton#actionBtn:hover {
                background-color: #004466;
                color: #ffffff;
                border-color: #00ff88;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header
        hdr = QLabel("◈  JARVIS FILE DISPATCHER")
        hdr.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        layout.addWidget(hdr)

        # File Selection Row
        layout.addWidget(QLabel("1. SELECT FILE:"))
        file_row = QHBoxLayout()
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("Select or enter file path...")
        if initial_file:
            self.file_input.setText(initial_file)
        file_row.addWidget(self.file_input)

        browse_btn = QPushButton("📁 Browse")
        browse_btn.clicked.connect(self._browse_file)
        file_row.addWidget(browse_btn)
        layout.addLayout(file_row)

        # Target App Row
        layout.addWidget(QLabel("2. TARGET APPLICATION:"))
        self.app_combo = QComboBox()
        self.app_combo.addItem("WhatsApp Desktop", "whatsapp")
        self.app_combo.addItem("Claude (claude.ai)", "claude")
        self.app_combo.addItem("ChatGPT (chatgpt.com)", "chatgpt")
        self.app_combo.addItem("Active / Current Window", "active_window")
        self.app_combo.currentIndexChanged.connect(self._on_app_changed)
        layout.addWidget(self.app_combo)

        # Recipient (for WhatsApp)
        self.receiver_lbl = QLabel("3. WHATSAPP RECIPIENT:")
        self.receiver_input = QLineEdit()
        self.receiver_input.setPlaceholderText("Contact or Group name (leave empty for current chat)...")
        layout.addWidget(self.receiver_lbl)
        layout.addWidget(self.receiver_input)

        # Optional Caption / Message
        layout.addWidget(QLabel("4. CAPTION / PROMPT (OPTIONAL):"))
        self.caption_input = QLineEdit()
        self.caption_input.setPlaceholderText("Message to accompany the file...")
        layout.addWidget(self.caption_input)

        layout.addSpacing(10)

        # Dispatch Button
        self.dispatch_btn = QPushButton("⚡ ATTACH & VERIFY")
        self.dispatch_btn.setObjectName("actionBtn")
        self.dispatch_btn.setFixedHeight(38)
        self.dispatch_btn.clicked.connect(self._do_dispatch)
        layout.addWidget(self.dispatch_btn)

    def _browse_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select File to Dispatch", str(Path.home() / "Desktop"))
        if f:
            self.file_input.setText(f)

    def _on_app_changed(self):
        target = self.app_combo.currentData()
        is_wa = (target == "whatsapp")
        self.receiver_lbl.setVisible(is_wa)
        self.receiver_input.setVisible(is_wa)

    def _do_dispatch(self):
        file_val = self.file_input.text().strip()
        if not file_val:
            QMessageBox.warning(self, "Missing File", "Please select or type a file path first.")
            return

        target = self.app_combo.currentData()
        receiver = self.receiver_input.text().strip()
        caption = self.caption_input.text().strip()

        params = {
            "file_name_or_path": file_val,
            "target_app": target,
            "receiver": receiver,
            "caption": caption,
        }

        self.hide()
        res = file_dispatcher.run(params)
        print("[Dispatcher] Result:", res)
        self.close()


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    initial = sys.argv[1] if len(sys.argv) > 1 else ""
    w = DispatcherWindow(initial)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

