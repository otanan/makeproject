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


class TemplatePathsDialog(QDialog):
    """Dialog for configuring template storage locations."""

    def __init__(
        self,
        project_path: Path,
        file_path: Path,
        default_project_path: Path,
        default_file_path: Path,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Template Locations")
        self.setModal(True)
        self.setMinimumSize(560, 220)

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

        project_browse = QPushButton("Browse...")
        project_browse.clicked.connect(lambda: self._browse_folder(self._project_input))

        file_browse = QPushButton("Browse...")
        file_browse.clicked.connect(lambda: self._browse_folder(self._file_input))

        project_row = QHBoxLayout()
        project_row.addWidget(self._project_input, 1)
        project_row.addWidget(project_browse)

        file_row = QHBoxLayout()
        file_row.addWidget(self._file_input, 1)
        file_row.addWidget(file_browse)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.addRow("Project templates:", project_row)
        form.addRow("File templates:", file_row)

        hint = QLabel("Leave a path blank to use the default location.")
        hint.setProperty("class", "muted")

        self._move_checkbox = QCheckBox("Move existing templates to the new location")
        self._move_checkbox.setChecked(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

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

    def project_path_text(self) -> str:
        return self._project_input.text().strip()

    def file_path_text(self) -> str:
        return self._file_input.text().strip()

    def should_move_existing(self) -> bool:
        return self._move_checkbox.isChecked()
