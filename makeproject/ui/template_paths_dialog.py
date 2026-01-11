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
    QStackedWidget,
    QWidget,
)

from .dialog_utils import style_default_dialog_button
from .editors import CodeEditor
from .panels import SegmentedControl
from ..highlighter import PythonHighlighter


class TemplatePathsDialog(QDialog):
    """Dialog for configuring MakeProject settings."""

    def __init__(
        self,
        project_path: Path,
        file_path: Path,
        custom_tokens_path: Path,
        project_generation_path: Path,
        default_project_path: Path,
        default_file_path: Path,
        default_custom_tokens_path: Path,
        default_project_generation_path: Path,
        python_interpreter_path: Path,
        default_python_interpreter_path: Path,
        python_preamble: str,
        dark_mode: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("MakeProject Settings")
        self.setModal(True)
        self.setMinimumSize(760, 420)

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

        self._generation_input = QLineEdit()
        self._generation_input.setText(str(project_generation_path))
        self._generation_input.setPlaceholderText(str(default_project_generation_path))
        self._generation_input.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            self._generation_input.sizePolicy().verticalPolicy(),
        )

        project_browse = QPushButton("Browse...")
        project_browse.clicked.connect(lambda: self._browse_folder(self._project_input))

        file_browse = QPushButton("Browse...")
        file_browse.clicked.connect(lambda: self._browse_folder(self._file_input))

        tokens_browse = QPushButton("Browse...")
        tokens_browse.clicked.connect(
            lambda: self._browse_file(self._custom_tokens_input)
        )

        generation_browse = QPushButton("Browse...")
        generation_browse.clicked.connect(
            lambda: self._browse_folder(self._generation_input)
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

        generation_row = QHBoxLayout()
        generation_row.addWidget(self._generation_input, 1)
        generation_row.addWidget(generation_browse)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.addRow("Project templates:", project_row)
        form.addRow("File templates:", file_row)
        form.addRow("Custom tokens file:", tokens_row)
        form.addRow("Project generation folder:", generation_row)

        hint = QLabel("Leave a path blank to use the default location.")
        hint.setWordWrap(True)
        hint.setProperty("class", "muted")

        self._move_checkbox = QCheckBox(
            "Move existing templates/tokens to the new location"
        )
        self._move_checkbox.setChecked(True)

        template_page = QWidget()
        template_layout = QVBoxLayout(template_page)
        template_layout.setContentsMargins(0, 0, 0, 0)
        template_layout.setSpacing(8)
        template_layout.addLayout(form)
        template_layout.addWidget(hint)
        template_layout.addWidget(self._move_checkbox)
        template_layout.addStretch(1)

        self._python_interpreter_input = QLineEdit()
        self._python_interpreter_input.setText(str(python_interpreter_path))
        self._python_interpreter_input.setPlaceholderText(
            str(default_python_interpreter_path)
        )
        self._python_interpreter_input.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            self._python_interpreter_input.sizePolicy().verticalPolicy(),
        )

        python_browse = QPushButton("Browse...")
        python_browse.clicked.connect(
            lambda: self._browse_python_interpreter(self._python_interpreter_input)
        )

        python_row = QHBoxLayout()
        python_row.addWidget(self._python_interpreter_input, 1)
        python_row.addWidget(python_browse)

        python_form = QFormLayout()
        python_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        python_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        python_form.addRow("Python interpreter:", python_row)

        python_hint = QLabel("Leave blank to use the app's Python interpreter.")
        python_hint.setWordWrap(True)
        python_hint.setProperty("class", "muted")

        preamble_label = QLabel("Python Preamble:")
        self._python_preamble_editor = CodeEditor(
            indent_size=4,
            placeholder=("""# Runs before every Python token
# Example:
y = 3
def f(x):
    return x + y
    
# Then writing "{{mp.py:f(2)}}" in a template will replace the token with "5".
"""

            ),
            highlighter_cls=PythonHighlighter,
            dark_mode=dark_mode,
        )
        self._python_preamble_editor.setPlainText(python_preamble or "")
        self._python_preamble_editor.setMinimumHeight(180)

        preamble_hint = QLabel(
            "Runs before every Python expression or block during generation."
        )
        preamble_hint.setWordWrap(True)
        preamble_hint.setProperty("class", "muted")

        python_page = QWidget()
        python_layout = QVBoxLayout(python_page)
        python_layout.setContentsMargins(0, 0, 0, 0)
        python_layout.setSpacing(8)
        python_layout.addLayout(python_form)
        python_layout.addWidget(python_hint)
        python_layout.addWidget(preamble_label)
        python_layout.addWidget(self._python_preamble_editor, 1)
        python_layout.addWidget(preamble_hint)

        tabs = SegmentedControl(["Template Locations", "Python Settings"])
        self._tabs = tabs

        stacked = QStackedWidget()
        stacked.addWidget(template_page)
        stacked.addWidget(python_page)
        self._stacked = stacked
        tabs.index_changed.connect(stacked.setCurrentIndex)

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
        layout.addWidget(tabs)
        layout.addWidget(stacked, 1)
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

    def _browse_python_interpreter(self, target: QLineEdit):
        start_path = target.text().strip()
        if not start_path:
            start_path = str(Path.home())
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Python Interpreter",
            start_path,
            "All Files (*)",
        )
        if selected:
            target.setText(selected)

    def project_path_text(self) -> str:
        return self._project_input.text().strip()

    def file_path_text(self) -> str:
        return self._file_input.text().strip()

    def custom_tokens_path_text(self) -> str:
        return self._custom_tokens_input.text().strip()

    def project_generation_path_text(self) -> str:
        return self._generation_input.text().strip()

    def python_interpreter_text(self) -> str:
        return self._python_interpreter_input.text().strip()

    def python_preamble_text(self) -> str:
        return self._python_preamble_editor.toPlainText()

    def should_move_existing(self) -> bool:
        return self._move_checkbox.isChecked()
