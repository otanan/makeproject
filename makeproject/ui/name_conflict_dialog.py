"""
Name conflict dialog for MakeProject.
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


class NameConflictDialog(QDialog):
    """Prompt the user when a name conflict occurs."""

    class Choice(str, Enum):
        OVERWRITE = "overwrite"
        KEEP = "keep"
        CANCEL = "cancel"

    def __init__(self, name: str, item_type: str = "Template", parent=None):
        """
        Create a name conflict dialog.

        Args:
            name: The conflicting name
            item_type: Type of item (e.g., "Template", "Token")
            parent: Parent widget
        """
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
        title_bar = DialogTitleBar(f"{item_type} Exists", container)
        title_bar.close_clicked.connect(self.reject)

        title = QLabel(f'"{name}" already exists.')
        title.setWordWrap(True)

        subtitle = QLabel(f"Choose what to do with this {item_type.lower()}.")
        subtitle.setWordWrap(True)
        subtitle.setProperty("class", "muted")

        self.overwrite_button = QPushButton("Overwrite")
        self.keep_button = QPushButton("Keep Both")
        self.cancel_button = QPushButton("Cancel")

        self.overwrite_button.setProperty("class", "dangerButton")
        style_default_dialog_button(self.keep_button)
        self.keep_button.setDefault(True)
        self.keep_button.setAutoDefault(True)
        self.cancel_button.setProperty("class", "cancelButton")

        self.overwrite_button.clicked.connect(self._on_overwrite)
        self.keep_button.clicked.connect(self._on_keep)
        self.cancel_button.clicked.connect(self.reject)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(self.overwrite_button)
        button_row.addWidget(self.keep_button)
        button_row.addWidget(self.cancel_button)

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

    def _on_overwrite(self):
        self._choice = self.Choice.OVERWRITE
        self.accept()

    def _on_keep(self):
        self._choice = self.Choice.KEEP
        self.accept()

    @property
    def choice(self) -> str:
        """Get the user's choice as a string."""
        return self._choice.value
