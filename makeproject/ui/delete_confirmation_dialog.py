"""
Delete confirmation dialog for MakeProject.
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


class DeleteConfirmationDialog(QDialog):
    """Prompt the user to confirm template deletion."""

    class Choice(str, Enum):
        DELETE = "delete"
        CANCEL = "cancel"

    def __init__(self, template_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Delete Template")
        self.setModal(True)
        self._choice = self.Choice.CANCEL

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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(button_row)

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
        self.setWindowTitle("Delete Folder")
        self.setModal(True)
        self._choice = self.Choice.CANCEL

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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(button_row)

    def _on_delete(self):
        self._choice = self.Choice.DELETE
        self.accept()

    @property
    def choice(self) -> "DeleteFolderConfirmationDialog.Choice":
        return self._choice
