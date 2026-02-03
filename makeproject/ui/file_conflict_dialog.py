"""
File/Folder conflict dialog for MakeProject.
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
    QCheckBox,
)

from .dialog_utils import style_default_dialog_button
from .title_bar import DialogTitleBar


class FileConflictDialog(QDialog):
    """Prompt the user when a file or folder conflict occurs during project generation."""

    class Choice(str, Enum):
        OVERWRITE = "overwrite"
        OVERWRITE_ALL = "overwrite_all"
        MERGE = "merge"
        MERGE_ALL = "merge_all"
        SKIP = "skip"
        SKIP_ALL = "skip_all"
        KEEP = "keep"
        KEEP_ALL = "keep_all"
        CANCEL = "cancel"

    def __init__(self, path: str, is_folder: bool = False, parent=None):
        """
        Create a file/folder conflict dialog.

        Args:
            path: The conflicting file or folder path (relative display path)
            is_folder: Whether this is a folder conflict (True) or file conflict (False)
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setMinimumWidth(450)
        self._choice = self.Choice.CANCEL
        self._is_folder = is_folder

        # Container widget that will receive QDialog styling
        container = QWidget()
        container.setObjectName("dialogContainer")

        # Create custom title bar
        title_text = "Folder Conflict" if is_folder else "File Conflict"
        title_bar = DialogTitleBar(title_text, container)
        title_bar.close_clicked.connect(self.reject)

        title = QLabel(f'"{path}" already exists.')
        title.setWordWrap(True)

        item_type = "folder" if is_folder else "file"
        subtitle = QLabel(f"Choose what to do with this {item_type}.")
        subtitle.setWordWrap(True)
        subtitle.setProperty("class", "muted")

        # "Apply to all" checkbox
        self.apply_to_all_checkbox = QCheckBox("Apply to all")
        self.apply_to_all_checkbox.setChecked(False)

        # Create buttons based on conflict type
        self.overwrite_button = QPushButton("Overwrite")
        self.cancel_button = QPushButton("Cancel (Esc)")

        self.overwrite_button.setProperty("class", "dangerButton")
        self.cancel_button.setProperty("class", "cancelButton")
        self.cancel_button.setShortcut(Qt.Key.Key_Escape)

        self.overwrite_button.clicked.connect(self._on_overwrite)
        self.cancel_button.clicked.connect(self.reject)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(self.overwrite_button)

        if is_folder:
            # Folder conflict: add Merge and Skip buttons
            self.merge_button = QPushButton("Merge")
            self.skip_button = QPushButton("Skip")

            style_default_dialog_button(self.merge_button)
            self.merge_button.setDefault(True)
            self.merge_button.setAutoDefault(True)
            self.skip_button.setProperty("class", "cancelButton")

            self.merge_button.clicked.connect(self._on_merge)
            self.skip_button.clicked.connect(self._on_skip)

            button_row.addWidget(self.merge_button)
            button_row.addWidget(self.skip_button)
        else:
            # File conflict: add Keep Both button
            self.keep_button = QPushButton("Keep Both")

            style_default_dialog_button(self.keep_button)
            self.keep_button.setDefault(True)
            self.keep_button.setAutoDefault(True)

            self.keep_button.clicked.connect(self._on_keep)

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
        content.addWidget(self.apply_to_all_checkbox)
        content.addLayout(button_row)

        container_layout.addLayout(content)

        # Dialog layout contains only the container
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(container)

    def _on_overwrite(self):
        if self.apply_to_all_checkbox.isChecked():
            self._choice = self.Choice.OVERWRITE_ALL
        else:
            self._choice = self.Choice.OVERWRITE
        self.accept()

    def _on_merge(self):
        if self.apply_to_all_checkbox.isChecked():
            self._choice = self.Choice.MERGE_ALL
        else:
            self._choice = self.Choice.MERGE
        self.accept()

    def _on_skip(self):
        if self.apply_to_all_checkbox.isChecked():
            self._choice = self.Choice.SKIP_ALL
        else:
            self._choice = self.Choice.SKIP
        self.accept()

    def _on_keep(self):
        if self.apply_to_all_checkbox.isChecked():
            self._choice = self.Choice.KEEP_ALL
        else:
            self._choice = self.Choice.KEEP
        self.accept()

    @property
    def choice(self) -> str:
        """Get the user's choice as a string."""
        return self._choice.value

    @property
    def apply_to_all(self) -> bool:
        """Check if 'Apply to all' is checked."""
        return self.apply_to_all_checkbox.isChecked()
