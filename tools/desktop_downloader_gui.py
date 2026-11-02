"""
tools/desktop_downloader_gui.py — Desktop GUI tool for JARVIS Universal Downloader.

Allows downloading YouTube videos, audio (MP3), media streams, and web files directly to Desktop.
"""

import os
import sys
import threading
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QProgressBar, QVBoxLayout, QWidget,
)

from plugins import desktop_downloader


class WorkerSignals(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)


class DownloaderWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JARVIS — Universal Desktop Downloader")
        self.setFixedSize(540, 360)

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
            QLineEdit, QComboBox {
                background-color: #011520;
                color: #ffffff;
                border: 1px solid #0d3347;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Consolas', monospace;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus {
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
            QProgressBar {
                border: 1px solid #0d3347;
                border-radius: 4px;
                text-align: center;
                color: #ffffff;
                background-color: #011520;
            }
            QProgressBar::chunk {
                background-color: #00f2fe;
            }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(18, 18, 18, 18)

        title = QLabel("📥 JARVIS — UNIVERSAL DESKTOP DOWNLOADER")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        layout.addWidget(title)

        # URL Input
        layout.addWidget(QLabel("🔗 Media or File URL:"))
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("Paste YouTube, video, or direct file download link...")
        layout.addWidget(self.url_edit)

        # Download Format Selection
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems([
            "Auto Detect (Video/File)",
            "Video (Best Quality MP4)",
            "Audio Only (MP3)",
            "Direct Web File (PDF, ZIP, Image)",
        ])
        fmt_row.addWidget(self.format_combo, 1)
        layout.addLayout(fmt_row)

        # Custom File Name (Optional)
        layout.addWidget(QLabel("Custom Filename (Optional):"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Leave blank to use original title/filename...")
        layout.addWidget(self.name_edit)

        # Progress / Status
        self.status_lbl = QLabel("Target: C:\\Users\\AJINKYA CHALKE\\Desktop")
        self.status_lbl.setStyleSheet("color: #4facfe; font-size: 11px; font-weight: normal;")
        layout.addWidget(self.status_lbl)

        self.btn_download = QPushButton("⚡ Download to Desktop")
        self.btn_download.clicked.connect(self._on_download)
        layout.addWidget(self.btn_download)

        self.setLayout(layout)
        self.signals = WorkerSignals()
        self.signals.finished.connect(self._on_finished)
        self.signals.error.connect(self._on_error)

    def _on_download(self):
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "Missing URL", "Please enter a valid URL to download.")
            return

        fmt_text = self.format_combo.currentText()
        media_type = "auto"
        if "Audio" in fmt_text:
            media_type = "audio"
        elif "Video" in fmt_text:
            media_type = "video"
        elif "Direct" in fmt_text:
            media_type = "file"

        custom_name = self.name_edit.text().strip() or None

        self.btn_download.setEnabled(False)
        self.status_lbl.setText("Downloading stream to Desktop... please wait...")

        def _worker():
            try:
                res = desktop_downloader.run({
                    "url": url,
                    "media_type": media_type,
                    "file_name": custom_name,
                })
                self.signals.finished.emit(res)
            except Exception as e:
                self.signals.error.emit(str(e))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_finished(self, msg: str):
        self.btn_download.setEnabled(True)
        self.status_lbl.setText("Download completed successfully!")
        self.url_edit.clear()
        self.name_edit.clear()
        QMessageBox.information(self, "Download Complete", msg)

    def _on_error(self, err: str):
        self.btn_download.setEnabled(True)
        self.status_lbl.setText("Download failed.")
        QMessageBox.critical(self, "Download Error", f"Failed to download: {err}")


def main():
    app = QApplication(sys.argv)
    window = DownloaderWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

