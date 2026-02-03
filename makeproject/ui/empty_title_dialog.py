"""
Empty title confirmation dialog for MakeProject.
"""

from enum import Enum

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from .dialog_utils import style_default_dialog_button
from .title_bar import DialogTitleBar


class EmptyTitleDialog(QDialog):
    """Prompt the user before continuing with an empty Title."""

    class Choice(str, Enum):
        CONTINUE = "continue"
        CANCEL = "cancel"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setMinimumWidth(450)
        self._choice = self.Choice.CANCEL

        # Container widget that will receive QDialog styling
        container = QWidget()
        container.setObjectName("dialogContainer")

        # Create custom title bar
        title_bar = DialogTitleBar("Empty Title", container)
        title_bar.close_clicked.connect(self.reject)

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

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.addWidget(title_bar)

        content = QVBoxLayout()
        content.setContentsMargins(20, 16, 20, 16)
        content.setSpacing(12)
        content.addWidget(title)
        content.addWidget(subtitle)
        content.addLayout(button_row)

        container_layout.addLayout(content)

        # Dialog layout contains only the container
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(container)

    def _on_continue(self):
        self._choice = self.Choice.CONTINUE
        self.accept()

    @property
    def choice(self) -> "EmptyTitleDialog.Choice":
        return self._choice
