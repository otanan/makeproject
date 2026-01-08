"""
Empty title confirmation dialog for MakeProject.
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


class EmptyTitleDialog(QDialog):
    """Prompt the user before continuing with an empty Title."""

    class Choice(str, Enum):
        CONTINUE = "continue"
        CANCEL = "cancel"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Empty Title")
        self.setModal(True)
        self._choice = self.Choice.CANCEL

        title = QLabel("Project currently has no title.")
        title.setWordWrap(True)

        subtitle = QLabel("Do you want to continue anyway?")
        subtitle.setWordWrap(True)
        subtitle.setProperty("class", "muted")

        self.continue_button = QPushButton("Continue")
        self.cancel_button = QPushButton("Cancel")

        style_default_dialog_button(self.continue_button)
        self.continue_button.setDefault(True)
        self.continue_button.setAutoDefault(True)

        self.continue_button.clicked.connect(self._on_continue)
        self.cancel_button.clicked.connect(self.reject)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.continue_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(button_row)

    def _on_continue(self):
        self._choice = self.Choice.CONTINUE
        self.accept()

    @property
    def choice(self) -> "EmptyTitleDialog.Choice":
        return self._choice
