"""
Main application window and orchestration logic.
"""

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import (
    QAction, QDesktopServices, QKeySequence, QPainter, QPainterPath,
    QTextCursor
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QFrame, QLabel, QPushButton, QFileDialog, QMessageBox, QStackedWidget,
    QProgressBar
)

from ..styles import load_qss
from ..highlighter import YAMLHighlighter
from ..template_engine import (
    parse_yaml, build_token_context, build_file_tree,
    generate_project, DEFAULT_YAML
)
from .. import library
from ..updater import UpdateChecker, UpdateDownloader, cleanup_updates
from .title_bar import TitleBar
from .panels import (
    ProjectTemplatesPanel, FileTemplatesPanel, DetailsPanel, PreviewPanel,
    CustomTokensPanel, SegmentedControl
)
from .editors import CodeEditor


@dataclass
class HistoryAction:
    """Undo/redo action entry."""

    undo: Callable[[], None]
    redo: Callable[[], None]
    label: str = ""


class MakeProjectWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()

        library.initialize()
        cleanup_updates()

        self._dark_mode = library.get_preference("dark_mode", True)
        self._is_maximized = False
        self._last_valid_tree = None

        self._preview_timer = QTimer()
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._update_preview)

        self._history = []
        self._history_index = 0
        self._history_suspended = False
        self._project_template_drafts = {}
        self._yaml_history_last = ""
        self._yaml_history_pending = False
        self._yaml_history_timer = QTimer()
        self._yaml_history_timer.setSingleShot(True)
        self._yaml_history_timer.setInterval(400)
        self._yaml_history_timer.timeout.connect(self._commit_yaml_history_entry)

        self._setup_window()
        self._setup_menu()
        self._setup_ui()
        self._setup_signals()
        self._apply_theme()
        self._reset_yaml_history()

        self.title_bar.dark_mode_toggle.blockSignals(True)
        self.title_bar.dark_mode_toggle._checked = self._dark_mode
        self.title_bar.dark_mode_toggle._thumb_position = 1.0 if self._dark_mode else 0.0
        self.title_bar.dark_mode_toggle.update()
        self.title_bar.dark_mode_toggle.blockSignals(False)

        QTimer.singleShot(0, self._restore_last_template)
        QTimer.singleShot(2000, self._check_for_updates)

    def _setup_window(self):
        """Configure frameless window with translucent background."""
        self.setWindowTitle("MakeProject")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def _setup_menu(self):
        """Set up the native menu bar."""
        menubar = self.menuBar()

        if sys.platform == "darwin":
            menubar.setNativeMenuBar(True)

        file_menu = menubar.addMenu("File")

        new_action = QAction("New", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._new_project)
        file_menu.addAction(new_action)

        open_action = QAction("Open...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._open_project)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        save_action = QAction("Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._save_current)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save As...", self)
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.triggered.connect(self._save_project_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        close_action = QAction("Close", self)
        close_action.setShortcut(QKeySequence.StandardKey.Close)
        close_action.triggered.connect(self.close)
        file_menu.addAction(close_action)

        edit_menu = menubar.addMenu("Edit")

        self.undo_action = QAction("Undo", self)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.undo_action.triggered.connect(self._undo)
        self.undo_action.setEnabled(False)
        edit_menu.addAction(self.undo_action)

        self.redo_action = QAction("Redo", self)
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.redo_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.redo_action.triggered.connect(self._redo)
        self.redo_action.setEnabled(False)
        edit_menu.addAction(self.redo_action)

        help_menu = menubar.addMenu("Help")

        update_action = QAction("Check for Updates...", self)
        update_action.triggered.connect(lambda: self._check_for_updates(manual=True))
        help_menu.addAction(update_action)

    def _setup_ui(self):
        """Set up the main UI layout."""
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.title_bar = TitleBar()
        main_layout.addWidget(self.title_bar)

        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(12)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.project_templates_panel = ProjectTemplatesPanel(
            draft_store=self._project_template_drafts
        )
        self.project_templates_panel.setMinimumWidth(200)
        self.project_templates_panel.setMaximumWidth(300)
        main_splitter.addWidget(self.project_templates_panel)
        main_splitter.setCollapsible(0, False)

        center_splitter = QSplitter(Qt.Orientation.Vertical)

        yaml_panel = QFrame()
        yaml_panel.setObjectName("projectYamlPanel")
        yaml_panel.setProperty("class", "panel")
        yaml_layout = QVBoxLayout(yaml_panel)
        yaml_layout.setContentsMargins(12, 12, 12, 12)
        yaml_layout.setSpacing(8)

        yaml_header = QLabel("PROJECT YAML")
        yaml_header.setProperty("class", "panelHeader")
        yaml_header.setToolTip("YAML configuration defining project structure")
        yaml_layout.addWidget(yaml_header)

        self.yaml_editor = CodeEditor(
            indent_size=2,
            placeholder="",
            highlighter_cls=YAMLHighlighter,
            dark_mode=self._dark_mode,
        )
        self.yaml_editor.setPlainText(DEFAULT_YAML)
        yaml_layout.addWidget(self.yaml_editor)

        center_splitter.addWidget(yaml_panel)

        bottom_container = QWidget()
        bottom_layout = QVBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(6)

        self.bottom_tabs = SegmentedControl(["File Templates", "Custom Tokens"])
        bottom_layout.addWidget(self.bottom_tabs)

        self.bottom_stack = QStackedWidget()
        self.file_templates_panel = FileTemplatesPanel()
        self.bottom_stack.addWidget(self.file_templates_panel)
        self.custom_tokens_panel = CustomTokensPanel()
        self.bottom_stack.addWidget(self.custom_tokens_panel)
        bottom_layout.addWidget(self.bottom_stack, 1)

        center_splitter.addWidget(bottom_container)
        center_splitter.setSizes([350, 300])

        main_splitter.addWidget(center_splitter)

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        self.details_panel = DetailsPanel()
        self.details_panel.setFixedHeight(200)
        right_layout.addWidget(self.details_panel)

        self.preview_panel = PreviewPanel()
        right_layout.addWidget(self.preview_panel, 1)

        generate_bar = QFrame()
        generate_layout = QHBoxLayout(generate_bar)
        generate_layout.setContentsMargins(12, 12, 12, 12)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        generate_layout.addWidget(self.progress_bar)

        generate_layout.addStretch()

        self.generate_btn = QPushButton("Generate Project")
        self.generate_btn.setObjectName("primaryButton")
        self.generate_btn.setMinimumWidth(150)
        self.generate_btn.clicked.connect(self._generate_project)
        generate_layout.addWidget(self.generate_btn)

        right_layout.addWidget(generate_bar)

        main_splitter.addWidget(right_container)
        main_splitter.setCollapsible(1, False)
        main_splitter.setCollapsible(2, False)
        main_splitter.setSizes([220, 500, 400])

        content_layout.addWidget(main_splitter)
        main_layout.addWidget(content)

    def _setup_signals(self):
        """Connect signals between components."""
        self.title_bar.close_clicked.connect(self.close)
        self.title_bar.maximize_clicked.connect(self._toggle_maximize)
        self.title_bar.minimize_clicked.connect(self.showMinimized)
        self.title_bar.dark_mode_toggle.toggled.connect(self._toggle_dark_mode)

        self.project_templates_panel.template_selected.connect(self._load_project_template)
        self.project_templates_panel.save_requested.connect(self._save_project)
        self.project_templates_panel.new_template_requested.connect(self._new_project_template)
        self.project_templates_panel.clear_requested.connect(self._clear_project_view)
        self.project_templates_panel.template_renamed.connect(self._on_project_template_renamed)
        self.project_templates_panel.template_delete_requested.connect(
            self._on_project_template_delete_requested
        )
        self.project_templates_panel.show_in_finder_requested.connect(
            self._show_project_template_in_finder
        )

        self.yaml_editor.textChanged.connect(self._queue_yaml_history_entry)
        self.yaml_editor.textChanged.connect(self._schedule_preview_update)
        self.yaml_editor.textChanged.connect(self._track_unsaved_changes)

        self.details_panel.values_changed.connect(self._schedule_preview_update)

        self.bottom_tabs.index_changed.connect(self.bottom_stack.setCurrentIndex)

        self.file_templates_panel.insert_reference.connect(self._insert_template_reference)
        self.file_templates_panel.template_delete_requested.connect(
            self._on_file_template_delete_requested
        )

        self.custom_tokens_panel.tokens_changed.connect(self._schedule_preview_update)
        self.custom_tokens_panel.token_action.connect(self._on_custom_token_action)

    def _apply_theme(self):
        """Apply the current theme stylesheet."""
        theme = "dark" if self._dark_mode else "light"
        qss = load_qss(theme)
        self.setStyleSheet(qss)

        self.yaml_editor.set_dark_mode(self._dark_mode)
        self.file_templates_panel.editor.set_dark_mode(self._dark_mode)
        self.preview_panel.set_dark_mode(self._dark_mode)

    def _toggle_dark_mode(self, checked: bool):
        """Toggle between dark and light mode."""
        self._dark_mode = checked
        self._apply_theme()
        library.set_preference("dark_mode", checked)

    def _toggle_maximize(self):
        """Toggle window maximized state."""
        if self._is_maximized:
            self.showNormal()
        else:
            self.showMaximized()
        self._is_maximized = not self._is_maximized

    def _save_current(self):
        """Save based on the current focus context."""
        focus_widget = QApplication.focusWidget()
        if (
            self.bottom_stack.currentWidget() == self.file_templates_panel
            and focus_widget is not None
            and self.file_templates_panel.isAncestorOf(focus_widget)
        ):
            self.file_templates_panel.save_current_template()
            return
        self._save_project()

    def _reset_yaml_history(self):
        """Reset the YAML history tracking baseline."""
        self._yaml_history_timer.stop()
        self._yaml_history_pending = False
        if hasattr(self, "yaml_editor"):
            self._yaml_history_last = self.yaml_editor.toPlainText()

    def _queue_yaml_history_entry(self):
        """Debounce YAML edits into a single undoable action."""
        if self._history_suspended:
            return
        self._yaml_history_pending = True
        self._yaml_history_timer.start()

    def _commit_yaml_history_entry(self):
        """Commit a pending YAML edit into the history stack."""
        if self._history_suspended or not self._yaml_history_pending:
            return
        new_text = self.yaml_editor.toPlainText()
        if new_text == self._yaml_history_last:
            self._yaml_history_pending = False
            return
        old_text = self._yaml_history_last
        self._yaml_history_last = new_text
        self._yaml_history_pending = False
        self._push_history_action(HistoryAction(
            undo=lambda text=old_text: self._apply_yaml_text(text),
            redo=lambda text=new_text: self._apply_yaml_text(text),
            label="Edit YAML"
        ))

    def _apply_yaml_text(self, text: str):
        """Apply YAML without creating a history entry."""
        was_suspended = self._history_suspended
        self._history_suspended = True
        try:
            self.yaml_editor.setPlainText(text)
        finally:
            self._history_suspended = was_suspended
        self._reset_yaml_history()

    def _set_yaml_text(self, text: str, *, block_signals: bool):
        """Set YAML text, optionally blocking change signals."""
        was_suspended = self._history_suspended
        self._history_suspended = True
        try:
            if block_signals:
                self.yaml_editor.blockSignals(True)
            self.yaml_editor.setPlainText(text)
            if block_signals:
                self.yaml_editor.blockSignals(False)
        finally:
            self._history_suspended = was_suspended
        self._reset_yaml_history()

    def _push_history_action(self, action: HistoryAction):
        """Append a history action and update undo/redo state."""
        if self._history_suspended:
            return
        if self._history_index < len(self._history):
            self._history = self._history[:self._history_index]
        self._history.append(action)
        self._history_index += 1
        self._update_edit_actions()

    def _update_edit_actions(self):
        """Enable or disable the Edit menu actions."""
        if hasattr(self, "undo_action"):
            self.undo_action.setEnabled(self._history_index > 0)
        if hasattr(self, "redo_action"):
            self.redo_action.setEnabled(self._history_index < len(self._history))

    def _undo(self):
        """Undo the last action in history."""
        self._commit_yaml_history_entry()
        if self._history_index == 0:
            return
        self._history_suspended = True
        try:
            action = self._history[self._history_index - 1]
            action.undo()
            self._history_index -= 1
        finally:
            self._history_suspended = False
        self._update_edit_actions()

    def _redo(self):
        """Redo the next action in history."""
        self._commit_yaml_history_entry()
        if self._history_index >= len(self._history):
            return
        self._history_suspended = True
        try:
            action = self._history[self._history_index]
            action.redo()
            self._history_index += 1
        finally:
            self._history_suspended = False
        self._update_edit_actions()

    def _on_project_template_renamed(self, old_name: str, new_name: str):
        """Update draft bookkeeping for a renamed project template."""
        if old_name in self._project_template_drafts:
            self._project_template_drafts[new_name] = self._project_template_drafts.pop(old_name)
        last_template = library.get_preference("last_template")
        if last_template == old_name:
            library.set_preference("last_template", new_name)

    def _on_project_template_delete_requested(self, name: str):
        if self._history_suspended:
            return
        content = library.load_project_template(name)
        if content is None:
            return
        self._project_template_drafts.pop(name, None)
        was_current = self.project_templates_panel.is_current_template(name)
        prev_name = self.project_templates_panel.get_previous_template_name(name)
        yaml_content = self.yaml_editor.toPlainText()
        title = self.details_panel.get_title()
        desc = self.details_panel.get_description()
        self._commit_yaml_history_entry()
        self._push_history_action(HistoryAction(
            undo=lambda n=name, c=content, wc=was_current, y=yaml_content, t=title, d=desc:
                self._undo_delete_project_template(n, c, wc, y, t, d),
            redo=lambda n=name, wc=was_current, pn=prev_name:
                self._redo_delete_project_template(n, wc, pn),
            label="Delete Project Template"
        ))

    def _undo_delete_project_template(
        self,
        name: str,
        content: str,
        was_current: bool,
        yaml_content: str,
        title: str,
        desc: str,
    ):
        library.save_project_template(name, content)
        if was_current:
            self.project_templates_panel.set_current_template(name, content)
            self.yaml_editor.setPlainText(yaml_content)
            self._reset_yaml_history()
            self.details_panel.title_input.setText(title)
            self.details_panel.desc_input.setPlainText(desc)
            self._schedule_preview_update()
            library.set_preference("last_template", name)
        else:
            self.project_templates_panel.refresh_list()

    def _redo_delete_project_template(self, name: str, was_current: bool, prev_name: str):
        library.delete_project_template(name)
        if was_current:
            if prev_name and prev_name in library.list_project_templates():
                self._load_project_template(prev_name)
            else:
                self.project_templates_panel.clear_current_template()
                self._clear_project_view()
        else:
            self.project_templates_panel.refresh_list()

    def _on_file_template_delete_requested(self, name: str):
        if self._history_suspended:
            return
        content = library.get_file_template(name)
        if content is None:
            return
        was_current = self.file_templates_panel.is_current_template(name)
        editor_content = self.file_templates_panel.editor.toPlainText()
        self._commit_yaml_history_entry()
        self._push_history_action(HistoryAction(
            undo=lambda n=name, c=content, wc=was_current, e=editor_content:
                self._undo_delete_file_template(n, c, wc, e),
            redo=lambda n=name, wc=was_current: self._redo_delete_file_template(n, wc),
            label="Delete File Template"
        ))

    def _undo_delete_file_template(
        self,
        name: str,
        content: str,
        was_current: bool,
        editor_content: str,
    ):
        library.save_file_template(name, content)
        if was_current:
            self.file_templates_panel.set_current_template_state(
                name, content, editor_content
            )
        else:
            self.file_templates_panel.refresh_list()

    def _redo_delete_file_template(self, name: str, was_current: bool):
        library.delete_file_template(name)
        if was_current:
            self.file_templates_panel.clear_current_template_state()
        else:
            self.file_templates_panel.refresh_list()

    def _on_custom_token_action(self, action: str, name: str, old_value: str, new_value: str):
        if self._history_suspended:
            return
        self._commit_yaml_history_entry()
        if action == "add":
            self._push_history_action(HistoryAction(
                undo=lambda n=name: self._apply_custom_token_delete(n),
                redo=lambda n=name, v=new_value: self._apply_custom_token_set(n, v),
                label="Add Token"
            ))
        elif action == "update":
            self._push_history_action(HistoryAction(
                undo=lambda n=name, v=old_value: self._apply_custom_token_set(n, v),
                redo=lambda n=name, v=new_value: self._apply_custom_token_set(n, v),
                label="Update Token"
            ))
        elif action == "delete":
            self._push_history_action(HistoryAction(
                undo=lambda n=name, v=old_value: self._apply_custom_token_set(n, v),
                redo=lambda n=name: self._apply_custom_token_delete(n),
                label="Delete Token"
            ))

    def _apply_custom_token_set(self, name: str, value: str):
        """Apply a token add/update without recording history."""
        library.update_custom_token(name, value)
        self.custom_tokens_panel.refresh_table()
        self.custom_tokens_panel.tokens_changed.emit()
        if self.custom_tokens_panel.has_tokens():
            self.custom_tokens_panel.table.selectRow(0)

    def _apply_custom_token_delete(self, name: str):
        """Apply a token delete without recording history."""
        library.delete_custom_token(name)
        self.custom_tokens_panel.refresh_table()
        self.custom_tokens_panel.tokens_changed.emit()
        if self.custom_tokens_panel.has_tokens():
            self.custom_tokens_panel.table.selectRow(0)

    def _show_project_template_in_finder(self, name: str):
        """Reveal a project template file in the OS file manager."""
        path = library.PROJECT_TEMPLATES_DIR / f"{name}.yaml"
        if not path.exists():
            QMessageBox.warning(self, "File Not Found", f"Could not find: {path.name}")
            return
        if sys.platform == "darwin":
            os.system(f'open -R "{path}"')
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))

    def _save_all_changes(self):
        """Persist all pending template edits to disk."""
        if self.project_templates_panel.has_unsaved_changes():
            self._save_project()
        for name, content in list(self._project_template_drafts.items()):
            library.save_project_template(name, content)
            if self.project_templates_panel.is_current_template(name):
                self.project_templates_panel.mark_saved(name, content)
            self._project_template_drafts.pop(name, None)
        self.file_templates_panel.save_all_unsaved()

    def _has_any_unsaved_changes(self) -> bool:
        """Return True when any panel has unsaved edits."""
        if self.project_templates_panel.has_unsaved_changes():
            return True
        if self.file_templates_panel.has_unsaved_changes():
            return True
        if self._project_template_drafts:
            return True
        return False

    def closeEvent(self, event):
        if not self._has_any_unsaved_changes():
            event.accept()
            return
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle("Unsaved Changes")
        dialog.setText("You have unsaved changes.")
        dialog.setInformativeText("Do you want to save your changes before quitting?")
        save_btn = dialog.addButton("Save All", QMessageBox.ButtonRole.AcceptRole)
        discard_btn = dialog.addButton("Quit Without Saving", QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = dialog.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        save_btn.setProperty("class", "keepButton")
        discard_btn.setProperty("class", "dangerButton")
        cancel_btn.setProperty("class", "cancelButton")
        dialog.setDefaultButton(save_btn)
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked == cancel_btn:
            event.ignore()
            return
        if clicked == save_btn:
            self._save_all_changes()
        event.accept()

    def _show_status(self, message: str, duration=3000):
        """Show a status message (no-op, status bar removed)."""
        pass

    def _clear_status(self):
        """Clear status message (no-op, status bar removed)."""
        pass

    def _new_project(self):
        """Create a new project with default YAML content."""
        self._set_yaml_text(DEFAULT_YAML, block_signals=False)
        self.details_panel.title_input.clear()
        self.details_panel.desc_input.clear()
        self._show_status("New project created")

    def _open_project(self):
        """Open a YAML file from disk."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project YAML",
            str(Path.home()),
            "YAML Files (*.yaml *.yml);;All Files (*)"
        )
        if path:
            try:
                content = Path(path).read_text(encoding="utf-8")
                self._set_yaml_text(content, block_signals=False)
                self._show_status(f"Opened: {Path(path).name}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to open file: {e}")

    def _save_project(self):
        """Save the current YAML into the project templates library."""
        if self.project_templates_panel.is_editing_new():
            name = self.project_templates_panel.finalize_new_template_name()
            if not name:
                return
        else:
            name = self.project_templates_panel.get_template_name()
        if not name:
            name = "untitled project"
            if (
                name in library.list_project_templates()
                and not self.project_templates_panel.is_current_template(name)
            ):
                name = self.project_templates_panel.get_unique_template_name(name)
        elif (
            name == "untitled project"
            and name in library.list_project_templates()
            and not self.project_templates_panel.is_current_template(name)
        ):
            name = self.project_templates_panel.get_unique_template_name(name)

        content = self.yaml_editor.toPlainText()
        library.save_project_template(name, content)
        self._project_template_drafts.pop(name, None)
        self.project_templates_panel.mark_saved(name, content)
        self._show_status(f"Saved: {name}")

    def _save_project_as(self):
        """Save the current YAML under a new template name."""
        name = self.project_templates_panel.get_template_name()
        if not name:
            QMessageBox.information(
                self,
                "Save Template",
                "Please enter a template name in the Project Templates panel."
            )
            return

        self._save_project()

    def _new_project_template(self):
        """Start a new project template with default YAML."""
        self._stash_current_project_template()
        self._set_yaml_text(DEFAULT_YAML, block_signals=False)

    def _clear_project_view(self):
        """Clear all project-specific panels (no template selected)."""
        self._set_yaml_text("", block_signals=True)
        self.details_panel.title_input.clear()
        self.details_panel.desc_input.clear()
        self.preview_panel.tree.clear()
        self.preview_panel.content_view.clear()
        self.preview_panel.status_label.setText("")
        library.set_preference("last_template", None)

    def _stash_current_project_template(self):
        """Cache unsaved YAML edits for the current template."""
        name = self.project_templates_panel.get_current_template_name()
        if not name:
            return
        content = self.yaml_editor.toPlainText()
        saved = library.load_project_template(name) or ""
        if content != saved:
            self._project_template_drafts[name] = content
        else:
            self._project_template_drafts.pop(name, None)

    def _track_unsaved_changes(self):
        """Update the unsaved indicator for project templates."""
        content = self.yaml_editor.toPlainText()
        self.project_templates_panel.mark_unsaved_changes(content)

    def _restore_last_template(self):
        """Restore the last opened project template at startup."""
        last_template = library.get_preference("last_template")
        if last_template:
            templates = library.list_project_templates()
            if last_template in templates:
                self._load_project_template(last_template)
                return
        self._update_preview()

    def _load_project_template(self, name: str):
        """Load a project template into the editor and details panel."""
        self._stash_current_project_template()
        content = library.load_project_template(name)
        if content:
            draft = self._project_template_drafts.get(name)
            editor_content = draft if draft is not None else content
            self.project_templates_panel.set_current_template(name, content)
            self._set_yaml_text(editor_content, block_signals=True)
            self.project_templates_panel.mark_unsaved_changes(editor_content)
            self._schedule_preview_update()
            self._show_status(f"Loaded: {name}")
            library.set_preference("last_template", name)

    def _insert_template_reference(self, template_name: str):
        """Insert a file template reference at the current YAML cursor."""
        cursor = self.yaml_editor.textCursor()
        current_block = cursor.block()
        line_text = current_block.text()
        base_indent = self._find_template_insert_indent(current_block, line_text)
        child_indent = f"{base_indent}  "
        snippet = (
            f"{base_indent}- file: {template_name}\n"
            f"{child_indent}template: {template_name}"
        )

        cursor.beginEditBlock()
        if not line_text.strip():
            cursor.select(QTextCursor.SelectionType.LineUnderCursor)
            cursor.removeSelectedText()
            cursor.insertText(snippet + "\n")
        else:
            if not cursor.atBlockStart():
                cursor.insertText("\n")
            cursor.insertText(snippet + "\n")
        cursor.endEditBlock()
        self.yaml_editor.setTextCursor(cursor)

    def _find_template_insert_indent(self, current_block, current_line: str) -> str:
        """Derive indentation for inserting a file template entry."""
        if current_line.strip():
            indent = len(current_line) - len(current_line.lstrip(" "))
            return " " * indent
        prev_block = current_block.previous()
        if not prev_block.isValid():
            return ""
        prev_text = prev_block.text()
        indent = len(prev_text) - len(prev_text.lstrip(" "))
        stripped = prev_text.strip()
        if stripped.startswith("template:") and indent >= 2:
            indent = max(0, indent - 2)
        return " " * indent

    def _schedule_preview_update(self):
        """Schedule a debounced preview refresh."""
        if self._preview_timer.isActive():
            self._preview_timer.stop()
        self._preview_timer.start(250)

    def _update_preview(self):
        """Refresh the preview panel based on YAML and details."""
        yaml_text = self.yaml_editor.toPlainText()
        title = self.details_panel.get_title()
        desc = self.details_panel.get_description()

        data, error = parse_yaml(yaml_text)
        if error:
            self.preview_panel.update_tree(self._last_valid_tree, error)
            return

        context = build_token_context(data, title, desc)
        try:
            tree = build_file_tree(data, context)
        except Exception as exc:
            self.preview_panel.update_tree(self._last_valid_tree, str(exc))
            return
        if tree:
            self._last_valid_tree = tree
        self.preview_panel.update_tree(tree)

    def _generate_project(self):
        """Generate the project on disk using the current YAML."""
        yaml_text = self.yaml_editor.toPlainText()
        data, error = parse_yaml(yaml_text)
        if error:
            QMessageBox.warning(self, "Invalid YAML", error)
            return

        output_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            str(Path.home())
        )
        if not output_dir:
            return
        output_path = Path(output_dir)

        context = build_token_context(
            data,
            self.details_panel.get_title(),
            self.details_panel.get_description()
        )
        try:
            tree = build_file_tree(data, context)
        except Exception as exc:
            QMessageBox.warning(self, "Invalid Template", str(exc))
            return
        if not tree:
            QMessageBox.warning(self, "No Files", "No files defined in the YAML.")
            return

        def on_progress(current, total):
            if total > 0:
                self.progress_bar.setValue(int((current / total) * 100))

        overwrite_all = False

        def on_conflict(path: Path, output_root: Path, is_folder: bool):
            nonlocal overwrite_all
            if overwrite_all:
                return "overwrite"
            decision = self._prompt_file_conflict(path, output_root, is_folder)
            if decision == "overwrite_all":
                overwrite_all = True
                return "overwrite"
            return decision

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        success, message = generate_project(tree, output_path, on_progress, on_conflict)

        if success:
            self.progress_bar.setValue(100)
            QTimer.singleShot(500, lambda: self.progress_bar.setVisible(False))
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(output_path))):
                if sys.platform == "darwin":
                    os.system(f'open "{output_path}"')
        else:
            self.progress_bar.setVisible(False)

        if success:
            self._show_status(message)
        elif message != "Generation cancelled.":
            QMessageBox.warning(self, "Error", message)

    def _prompt_file_conflict(self, path: Path, output_root: Path, is_folder: bool) -> str:
        """Prompt the user on file/folder conflicts during generation."""
        try:
            display_path = str(path.relative_to(output_root))
        except ValueError:
            display_path = str(path)

        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Question)
        if is_folder:
            dialog.setWindowTitle("Folder Conflict")
            dialog.setText(f"\"{display_path}\" already exists.")
            dialog.setInformativeText("Choose what to do with this folder.")

            overwrite_btn = dialog.addButton("Overwrite", QMessageBox.ButtonRole.DestructiveRole)
            overwrite_all_btn = dialog.addButton("Overwrite All", QMessageBox.ButtonRole.DestructiveRole)
            merge_btn = dialog.addButton("Merge", QMessageBox.ButtonRole.AcceptRole)
            skip_btn = dialog.addButton("Skip", QMessageBox.ButtonRole.RejectRole)
            cancel_btn = dialog.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            overwrite_btn.setProperty("class", "dangerButton")
            overwrite_all_btn.setProperty("class", "dangerButton")
            merge_btn.setProperty("class", "keepButton")
            skip_btn.setProperty("class", "cancelButton")
            cancel_btn.setProperty("class", "cancelButton")
            dialog.setDefaultButton(merge_btn)
        else:
            dialog.setWindowTitle("File Conflict")
            dialog.setText(f"\"{display_path}\" already exists.")
            dialog.setInformativeText("Choose what to do with this file.")

            overwrite_btn = dialog.addButton("Overwrite", QMessageBox.ButtonRole.DestructiveRole)
            overwrite_all_btn = dialog.addButton("Overwrite All", QMessageBox.ButtonRole.DestructiveRole)
            keep_btn = dialog.addButton("Keep Both", QMessageBox.ButtonRole.AcceptRole)
            cancel_btn = dialog.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            overwrite_btn.setProperty("class", "dangerButton")
            overwrite_all_btn.setProperty("class", "dangerButton")
            keep_btn.setProperty("class", "keepButton")
            cancel_btn.setProperty("class", "cancelButton")
            dialog.setDefaultButton(keep_btn)

        dialog.exec()
        clicked = dialog.clickedButton()
        if is_folder:
            if clicked == cancel_btn:
                return "cancel"
            if clicked == skip_btn:
                return "skip"
            if clicked == merge_btn:
                return "merge"
            if clicked == overwrite_all_btn:
                return "overwrite_all"
            return "overwrite"

        if clicked == cancel_btn:
            return "cancel"
        if clicked == keep_btn:
            return "keep"
        if clicked == overwrite_all_btn:
            return "overwrite_all"
        return "overwrite"

    def _check_for_updates(self, manual=False):
        """Check for updates from GitHub."""
        self.update_checker = UpdateChecker()
        self.update_checker.update_available.connect(
            lambda v, u: self._on_update_available(v, u, manual)
        )
        self.update_checker.no_update.connect(
            lambda: self._on_no_update(manual)
        )
        self.update_checker.error.connect(
            lambda e: self._on_update_error(e, manual)
        )
        self.update_checker.start()

        if manual:
            self._show_status("Checking for updates...")

    def _on_update_available(self, version: str, url: str, manual: bool):
        """Handle the update-available flow."""
        reply = QMessageBox.question(
            self,
            "Update Available",
            f"A new version ({version}) is available. Download and install?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._download_update(url)

    def _on_no_update(self, manual: bool):
        """Handle a successful update check with no updates."""
        if manual:
            QMessageBox.information(
                self,
                "No Updates",
                "You're running the latest version."
            )
            self._clear_status()

    def _on_update_error(self, error: str, manual: bool):
        """Handle update check errors."""
        if manual:
            QMessageBox.warning(
                self,
                "Update Check Failed",
                f"Could not check for updates: {error}"
            )
            self._clear_status()

    def _download_update(self, url: str):
        """Download and install the update bundle."""
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        self.update_downloader = UpdateDownloader(url)
        self.update_downloader.progress.connect(self.progress_bar.setValue)
        self.update_downloader.status.connect(self._show_status)
        self.update_downloader.finished.connect(self._on_update_finished)
        self.update_downloader.start()

    def _on_update_finished(self, success: bool, message: str):
        """Handle update completion."""
        self.progress_bar.setVisible(False)

        if success:
            self._show_status("Update complete!")
        else:
            QMessageBox.warning(self, "Update Failed", message)

    def paintEvent(self, event):
        """Paint rounded corners for frameless window."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(self.rect().toRectF(), 12, 12)

        painter.setClipPath(path)

        super().paintEvent(event)
