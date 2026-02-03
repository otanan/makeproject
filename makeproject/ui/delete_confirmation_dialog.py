"""
Delete confirmation dialog for MakeProject.
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


class DeleteConfirmationDialog(QDialog):
    """Prompt the user to confirm template deletion."""

    class Choice(str, Enum):
        DELETE = "delete"
        CANCEL = "cancel"

    def __init__(self, template_name: str, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setMinimumWidth(450)  # 50% wider than default
        self._choice = self.Choice.CANCEL

        # Container widget that will receive QDialog styling
        container = QWidget()
        container.setObjectName("dialogContainer")

        # Create custom title bar
        title_bar = DialogTitleBar("Delete Template", container)
        title_bar.close_clicked.connect(self.reject)

        title = QLabel(f'Delete "{template_name}"?')
        title.setWordWrap(True)

        subtitle = QLabel("This action cannot be undone.")
        subtitle.setWordWrap(True)
        subtitle.setProperty("class", "muted")

        self.delete_button = QPushButton("Delete")
        self.cancel_button = QPushButton("Cancel")

        self.delete_button.setProperty("class", "dangerButton")
        style_default_dialog_button(self.cancel_button)

        self.delete_button.clicked.connect(self._on_delete)
        self.cancel_button.clicked.connect(self.reject)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(self.delete_button)
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

    def _on_delete(self):
        self._choice = self.Choice.DELETE
        self.accept()

    @property
    def choice(self) -> "DeleteConfirmationDialog.Choice":
        return self._choice


class DeleteFolderConfirmationDialog(QDialog):
    """Prompt the user to confirm folder deletion."""

    class Choice(str, Enum):
        DELETE = "delete"
        CANCEL = "cancel"

    def __init__(self, folder_name: str, template_count: int = 0, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setMinimumWidth(450)  # 50% wider than default
        self._choice = self.Choice.CANCEL

        # Container widget that will receive QDialog styling
        container = QWidget()
        container.setObjectName("dialogContainer")

        # Create custom title bar
        title_bar = DialogTitleBar("Delete Folder", container)
        title_bar.close_clicked.connect(self.reject)

        title = QLabel(f'Delete folder: "{folder_name}"?')
        title.setWordWrap(True)

        if template_count > 0:
            template_word = "template" if template_count == 1 else "templates"
            subtitle_text = f"This will also delete {template_count} {template_word} inside. This action cannot be undone."
        else:
            subtitle_text = "This action cannot be undone."

        subtitle = QLabel(subtitle_text)
        subtitle.setWordWrap(True)
        subtitle.setProperty("class", "muted")

        self.delete_button = QPushButton("Delete")
        self.cancel_button = QPushButton("Cancel")

        self.delete_button.setProperty("class", "dangerButton")
        style_default_dialog_button(self.cancel_button)

        self.delete_button.clicked.connect(self._on_delete)
        self.cancel_button.clicked.connect(self.reject)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(self.delete_button)
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

    def _on_delete(self):
        self._choice = self.Choice.DELETE
        self.accept()

    @property
    def choice(self) -> "DeleteFolderConfirmationDialog.Choice":
        return self._choice
