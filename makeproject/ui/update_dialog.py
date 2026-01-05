"""
Update dialog UI for MakeProject.
"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
    QProgressBar,
    QPushButton,
)

from .dialog_utils import style_default_dialog_button

class UpdateDialog(QDialog):
    """Update prompt dialog that hosts progress and status updates."""

    update_requested = pyqtSignal()

    def __init__(self, version: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Update Available")
        self.setModal(True)

        self._is_updating = False

        self.message_label = QLabel(
            f"A new version ({version}) is available. Download and install?"
        )
        self.message_label.setWordWrap(True)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)

        self.status_label = QLabel("")
        self.status_label.setVisible(False)

        progress_layout = QHBoxLayout()
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.status_label, 1)

        self.update_button = QPushButton("Update")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setProperty("class", "cancelButton")
        style_default_dialog_button(self.update_button)

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(self.update_button)
        buttons_layout.addWidget(self.cancel_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        layout.addWidget(self.message_label)
        layout.addLayout(progress_layout)
        layout.addLayout(buttons_layout)

        self.update_button.clicked.connect(self._on_update_clicked)
        self.cancel_button.clicked.connect(self.reject)

    def _on_update_clicked(self):
        if self._is_updating:
            return
        self._is_updating = True
        self.update_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setVisible(True)
        self.set_status("Starting update...")
        self.layout().activate()
        self.adjustSize()
        self.update_requested.emit()

    def set_status(self, message: str):
        self.status_label.setText(message)

    def set_progress(self, value: int):
        self.progress_bar.setValue(value)

    def mark_finished(self, success: bool, message: str):
        self._is_updating = False
        if success:
            self.update_button.setEnabled(False)
            self.set_status(message)
        else:
            self.update_button.setEnabled(True)
            self.set_status(message)
        self.cancel_button.setEnabled(True)
        self.cancel_button.setText("Close")
