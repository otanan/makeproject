"""
Unsaved changes dialog for MakeProject.
"""

from enum import Enum

from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
)

from .dialog_utils import style_default_dialog_button


class UnsavedChangesDialog(QDialog):
    """Prompt the user when there are unsaved changes on quit."""

    class Choice(str, Enum):
        SAVE = "save"
        DISCARD = "discard"
        CANCEL = "cancel"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Unsaved Changes")
        self.setModal(True)
        self._choice = self.Choice.CANCEL

        title = QLabel("You have unsaved changes.")
        title.setWordWrap(True)

        subtitle = QLabel("Do you want to save your changes before quitting?")
        subtitle.setWordWrap(True)
        subtitle.setProperty("class", "muted")

        self.save_button = QPushButton("Save All")
        self.discard_button = QPushButton("Quit Without Saving")
        self.cancel_button = QPushButton("Cancel")

        self.discard_button.setProperty("class", "dangerButton")
        style_default_dialog_button(self.cancel_button)

        self.save_button.clicked.connect(self._on_save)
        self.discard_button.clicked.connect(self._on_discard)
        self.cancel_button.clicked.connect(self.reject)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(self.save_button)
        button_row.addWidget(self.discard_button)
        button_row.addWidget(self.cancel_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(button_row)

    def _on_save(self):
        self._choice = self.Choice.SAVE
        self.accept()

    def _on_discard(self):
        self._choice = self.Choice.DISCARD
        self.accept()

    @property
    def choice(self) -> "UnsavedChangesDialog.Choice":
        return self._choice
