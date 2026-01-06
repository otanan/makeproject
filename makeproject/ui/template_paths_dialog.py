"""
Template path configuration dialog for MakeProject.
"""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QLineEdit,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QFormLayout,
    QDialogButtonBox,
    QFileDialog,
    QCheckBox,
    QSizePolicy,
)

from .dialog_utils import style_default_dialog_button


class TemplatePathsDialog(QDialog):
    """Dialog for configuring template storage locations."""

    def __init__(
        self,
        project_path: Path,
        file_path: Path,
        custom_tokens_path: Path,
        default_project_path: Path,
        default_file_path: Path,
        default_custom_tokens_path: Path,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("MakeProject Settings")
        self.setModal(True)
        self.setMinimumSize(720, 260)

        self._project_input = QLineEdit()
        self._project_input.setText(str(project_path))
        self._project_input.setPlaceholderText(str(default_project_path))
        self._project_input.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            self._project_input.sizePolicy().verticalPolicy(),
        )

        self._file_input = QLineEdit()
        self._file_input.setText(str(file_path))
        self._file_input.setPlaceholderText(str(default_file_path))
        self._file_input.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            self._file_input.sizePolicy().verticalPolicy(),
        )

        self._custom_tokens_input = QLineEdit()
        self._custom_tokens_input.setText(str(custom_tokens_path))
        self._custom_tokens_input.setPlaceholderText(str(default_custom_tokens_path))
        self._custom_tokens_input.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            self._custom_tokens_input.sizePolicy().verticalPolicy(),
        )

        project_browse = QPushButton("Browse...")
        project_browse.clicked.connect(lambda: self._browse_folder(self._project_input))

        file_browse = QPushButton("Browse...")
        file_browse.clicked.connect(lambda: self._browse_folder(self._file_input))

        tokens_browse = QPushButton("Browse...")
        tokens_browse.clicked.connect(
            lambda: self._browse_file(self._custom_tokens_input)
        )

        project_row = QHBoxLayout()
        project_row.addWidget(self._project_input, 1)
        project_row.addWidget(project_browse)

        file_row = QHBoxLayout()
        file_row.addWidget(self._file_input, 1)
        file_row.addWidget(file_browse)

        tokens_row = QHBoxLayout()
        tokens_row.addWidget(self._custom_tokens_input, 1)
        tokens_row.addWidget(tokens_browse)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.addRow("Project templates:", project_row)
        form.addRow("File templates:", file_row)
        form.addRow("Custom tokens file:", tokens_row)

        hint = QLabel("Leave a path blank to use the default location.")
        hint.setProperty("class", "muted")

        self._move_checkbox = QCheckBox(
            "Move existing templates/tokens to the new location"
        )
        self._move_checkbox.setChecked(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button:
            style_default_dialog_button(ok_button)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(self._move_checkbox)
        layout.addWidget(buttons)

    def _browse_folder(self, target: QLineEdit):
        start_dir = target.text().strip()
        if not start_dir:
            start_dir = str(Path.home())
        selected = QFileDialog.getExistingDirectory(
            self, "Choose Folder", start_dir
        )
        if selected:
            target.setText(selected)

    def _browse_file(self, target: QLineEdit):
        start_path = target.text().strip()
        if not start_path:
            start_path = str(Path.home())
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Choose File",
            start_path,
            "YAML Files (*.yaml *.yml);;All Files (*)",
        )
        if selected:
            target.setText(selected)

    def project_path_text(self) -> str:
        return self._project_input.text().strip()

    def file_path_text(self) -> str:
        return self._file_input.text().strip()

    def custom_tokens_path_text(self) -> str:
        return self._custom_tokens_input.text().strip()

    def should_move_existing(self) -> bool:
        return self._move_checkbox.isChecked()
