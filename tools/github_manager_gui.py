"""
tools/github_manager_gui.py — Desktop GUI tool for JARVIS GitHub & Git Manager.

Enables viewing repositories, cloning directly into JarvisProjects, and checking Git status.
"""

import sys
import threading
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from plugins import github_manager


class WorkerSignals(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)


class GitHubManagerWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JARVIS — GitHub Operations & Clone Manager")
        self.setFixedSize(560, 440)

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
            QLineEdit, QTextEdit {
                background-color: #011520;
                color: #ffffff;
                border: 1px solid #0d3347;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Consolas', monospace;
                font-size: 12px;
            }
            QLineEdit:focus, QTextEdit:focus {
                border: 1px solid #00d4ff;
            }
            QPushButton {
                background-color: #0d3347;
                color: #00f2fe;
                border: 1px solid #00f2fe;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #00f2fe;
                color: #000914;
            }
            QPushButton:disabled {
                border-color: #334455;
                color: #556677;
            }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(18, 18, 18, 18)

        title = QLabel("🐙 JARVIS — GITHUB & GIT OPERATIONS")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        layout.addWidget(title)

        # Clone Section
        layout.addWidget(QLabel("📦 Clone Repository into Desktop\\JarvisProjects:"))
        clone_row = QHBoxLayout()
        self.repo_edit = QLineEdit()
        self.repo_edit.setPlaceholderText("owner/repo or https://github.com/owner/repo.git")
        clone_row.addWidget(self.repo_edit, 1)

        self.btn_clone = QPushButton("⬇️ Clone")
        self.btn_clone.clicked.connect(self._on_clone)
        clone_row.addWidget(self.btn_clone)
        layout.addLayout(clone_row)

        # Quick Actions
        action_row = QHBoxLayout()
        self.btn_list = QPushButton("📋 My Repositories")
        self.btn_list.clicked.connect(self._on_list_repos)
        action_row.addWidget(self.btn_list)

        self.btn_status = QPushButton("🔍 Git Auth Status")
        self.btn_status.clicked.connect(self._on_status)
        action_row.addWidget(self.btn_status)
        layout.addLayout(action_row)

        # Console / Results Output
        layout.addWidget(QLabel("Telemetry & Output:"))
        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        self.output_box.setPlaceholderText("Results and status will appear here...")
        layout.addWidget(self.output_box, 1)

        self.setLayout(layout)
        self.signals = WorkerSignals()
        self.signals.finished.connect(self._on_finished)
        self.signals.error.connect(self._on_error)

    def _on_clone(self):
        repo = self.repo_edit.text().strip()
        if not repo:
            QMessageBox.warning(self, "Missing Repo", "Please enter a repository name (e.g. owner/repo).")
            return

        self._set_loading("Cloning repository into Desktop\\JarvisProjects...")
        threading.Thread(target=lambda: self._run_op({"action": "clone_repo", "repo_name": repo}), daemon=True).start()

    def _on_list_repos(self):
        self._set_loading("Fetching your GitHub repositories...")
        threading.Thread(target=lambda: self._run_op({"action": "list_repos", "limit": 10}), daemon=True).start()

    def _on_status(self):
        self._set_loading("Checking GitHub CLI authentication...")
        threading.Thread(target=lambda: self._run_op({"action": "status"}), daemon=True).start()

    def _set_loading(self, msg: str):
        self.btn_clone.setEnabled(False)
        self.btn_list.setEnabled(False)
        self.btn_status.setEnabled(False)
        self.output_box.setText(msg)

    def _run_op(self, params: dict):
        try:
            res = github_manager.run(params)
            self.signals.finished.emit(res)
        except Exception as e:
            self.signals.error.emit(str(e))

    def _on_finished(self, msg: str):
        self.btn_clone.setEnabled(True)
        self.btn_list.setEnabled(True)
        self.btn_status.setEnabled(True)
        self.output_box.setText(msg)

    def _on_error(self, err: str):
        self.btn_clone.setEnabled(True)
        self.btn_list.setEnabled(True)
        self.btn_status.setEnabled(True)
        self.output_box.setText(f"Error: {err}")


def main():
    app = QApplication(sys.argv)
    window = GitHubManagerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

