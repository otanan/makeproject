"""
Main application window and orchestration logic.
"""

import os
import sys
import re
import shutil
import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import (
    QAction, QDesktopServices, QKeySequence, QPainter, QPainterPath,
    QTextCursor
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QFrame, QLabel, QPushButton, QFileDialog, QMessageBox, QStackedWidget,
    QProgressBar, QDialog
)

from ..styles import load_qss, get_code_font
from ..constants import Timing, CacheLimits
from ..highlighter import YAMLHighlighter
from ..template_engine import (
    parse_yaml, build_token_context, build_file_tree,
    generate_project, DEFAULT_YAML, YAMLParseError,
    substitute_tokens, collect_template_references,
    parse_template_metadata, parse_template_metadata_with_error,
)
from .. import library
from ..updater import (
    UpdateChecker,
    UpdateDownloader,
    cleanup_updates,
    get_app_path,
    relaunch_app,
)
from .title_bar import TitleBar
from .panels import (
    ProjectTemplatesPanel, FileTemplatesPanel, DetailsPanel, PreviewPanel,
    CustomTokensPanel, SegmentedControl
)
from .editors import CodeEditor
from .update_dialog import UpdateDialog
from .template_paths_dialog import TemplatePathsDialog
from .unsaved_changes_dialog import UnsavedChangesDialog
from .empty_title_dialog import EmptyTitleDialog
from .dialog_utils import style_default_dialog_button


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

        # YAML parsing cache - reduces re-parsing overhead during preview updates
        self._yaml_parse_cache = {}  # hash -> (data, error)
        self._yaml_parse_cache_max_size = CacheLimits.YAML_PARSE_CACHE

        self._preview_timer = QTimer()
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._update_preview)
        self._animate_fields_next = False
        self._suppress_yaml_animation = False

        self._history = []
        self._history_index = 0
        self._history_suspended = False
        self._update_dialog = None
        self._force_quit = False
        self._project_template_drafts = {}
        self._yaml_history_last = ""
        self._yaml_history_pending = False
        self._yaml_history_timer = QTimer()
        self._yaml_history_timer.setSingleShot(True)
        self._yaml_history_timer.setInterval(Timing.HISTORY_COMMIT_MS)
        self._yaml_history_timer.timeout.connect(self._commit_yaml_history_entry)

        self._setup_window()
        self._setup_menu()
        self._setup_ui()
        self._restore_splitter_states()
        self._setup_signals()
        self._apply_theme()
        self._reset_yaml_history()

        self.title_bar.dark_mode_toggle.blockSignals(True)
        self.title_bar.dark_mode_toggle._checked = self._dark_mode
        self.title_bar.dark_mode_toggle._thumb_position = 1.0 if self._dark_mode else 0.0
        self.title_bar.dark_mode_toggle.update()
        self.title_bar.dark_mode_toggle.blockSignals(False)

        QTimer.singleShot(Timing.RESTORE_DELAY_MS, self._restore_last_template)
        QTimer.singleShot(Timing.UPDATE_CHECK_DELAY_MS, self._check_for_updates)

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

        new_action = QAction("New", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        new_action.triggered.connect(self._new_project)
        self.addAction(new_action)

        open_action = QAction("Open...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        open_action.triggered.connect(self._open_project)
        self.addAction(open_action)

        save_action = QAction("Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        save_action.triggered.connect(self._save_current)
        self.addAction(save_action)

        save_as_action = QAction("Save As...", self)
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        save_as_action.triggered.connect(self._save_project_as)
        self.addAction(save_as_action)

        close_action = QAction("Close", self)
        close_action.setShortcut(QKeySequence.StandardKey.Close)
        close_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        close_action.triggered.connect(self.close)
        self.addAction(close_action)

        template_paths_action = QAction("Template Locations...", self)
        template_paths_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        template_paths_action.triggered.connect(self._configure_template_locations)

        quit_action = QAction("Quit MakeProject", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.setMenuRole(QAction.MenuRole.QuitRole)
        quit_action.triggered.connect(self.close)

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

        edit_menu.addSeparator()

        find_action = QAction("Find Template...", self)
        find_action.setShortcut(QKeySequence.StandardKey.Find)
        find_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        find_action.triggered.connect(self._focus_template_search)
        edit_menu.addAction(find_action)

        help_menu = menubar.addMenu("Help")

        if sys.platform == "darwin":
            help_menu.addAction(template_paths_action)
            help_menu.addAction(quit_action)
        else:
            app_menu = menubar.addMenu("MakeProject")
            app_menu.addAction(template_paths_action)
            app_menu.addSeparator()
            app_menu.addAction(quit_action)

        update_action = QAction("Check for Updates...", self)
        update_action.triggered.connect(lambda: self._check_for_updates(manual=True))
        help_menu.addAction(update_action)

        # Font size shortcuts (Cmd+/Cmd- on macOS, Ctrl+/Ctrl- on other platforms)
        increase_font_action = QAction("Increase Font Size", self)
        increase_font_action.setShortcut(QKeySequence("Ctrl+="))
        increase_font_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        increase_font_action.triggered.connect(self._increase_font_size)
        self.addAction(increase_font_action)

        # Also bind Cmd+Shift+= (Cmd++) for convenience
        increase_font_action2 = QAction("Increase Font Size Alt", self)
        increase_font_action2.setShortcut(QKeySequence("Ctrl++"))
        increase_font_action2.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        increase_font_action2.triggered.connect(self._increase_font_size)
        self.addAction(increase_font_action2)

        decrease_font_action = QAction("Decrease Font Size", self)
        decrease_font_action.setShortcut(QKeySequence("Ctrl+-"))
        decrease_font_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        decrease_font_action.triggered.connect(self._decrease_font_size)
        self.addAction(decrease_font_action)

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
        self._main_splitter = main_splitter

        self.project_templates_panel = ProjectTemplatesPanel(
            draft_store=self._project_template_drafts
        )
        self.project_templates_panel.setMinimumWidth(200)
        self.project_templates_panel.setMaximumWidth(300)
        main_splitter.addWidget(self.project_templates_panel)
        main_splitter.setCollapsible(0, False)

        center_splitter = QSplitter(Qt.Orientation.Vertical)
        self._center_splitter = center_splitter

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
            preamble_newlines=True,
        )
        # Don't set DEFAULT_YAML here - let _restore_last_template handle it to avoid flicker
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

    def _restore_splitter_state(self, splitter: QSplitter, state_b64: str | None):
        if not splitter or not state_b64:
            return
        try:
            state = base64.b64decode(state_b64.encode("ascii"))
        except (ValueError, UnicodeDecodeError):
            return
        splitter.restoreState(state)

    def _restore_splitter_states(self):
        prefs = library.load_preferences()
        self._restore_splitter_state(
            self._main_splitter,
            prefs.get("splitter_main"),
        )
        self._restore_splitter_state(
            self._center_splitter,
            prefs.get("splitter_center"),
        )
        self._restore_splitter_state(
            self.preview_panel.splitter,
            prefs.get("splitter_preview"),
        )
        self._restore_splitter_state(
            self.file_templates_panel.splitter,
            prefs.get("splitter_file_templates"),
        )
        self._restore_splitter_state(
            self.custom_tokens_panel.splitter,
            prefs.get("splitter_custom_tokens"),
        )

    def _save_splitter_states(self):
        prefs = library.load_preferences()
        prefs["splitter_main"] = base64.b64encode(
            self._main_splitter.saveState()
        ).decode("ascii")
        prefs["splitter_center"] = base64.b64encode(
            self._center_splitter.saveState()
        ).decode("ascii")
        prefs["splitter_preview"] = base64.b64encode(
            self.preview_panel.splitter.saveState()
        ).decode("ascii")
        prefs["splitter_file_templates"] = base64.b64encode(
            self.file_templates_panel.splitter.saveState()
        ).decode("ascii")
        prefs["splitter_custom_tokens"] = base64.b64encode(
            self.custom_tokens_panel.splitter.saveState()
        ).decode("ascii")
        library.save_preferences(prefs)

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
        self.yaml_editor.textChanged.connect(self._schedule_preview_update_from_yaml)
        self.yaml_editor.textChanged.connect(self._track_unsaved_changes)

        self.details_panel.values_changed.connect(self._schedule_preview_update_without_animation)

        self.bottom_tabs.index_changed.connect(self.bottom_stack.setCurrentIndex)

        self.file_templates_panel.insert_reference.connect(self._insert_template_reference)
        self.file_templates_panel.template_delete_requested.connect(
            self._on_file_template_delete_requested
        )
        self.file_templates_panel.templates_changed.connect(self._schedule_preview_update_without_animation)
        self.file_templates_panel.generate_file_requested.connect(self._generate_file_from_template)

        self.custom_tokens_panel.tokens_changed.connect(self._schedule_preview_update_without_animation)
        self.custom_tokens_panel.token_action.connect(self._on_custom_token_action)

        self.preview_panel.generate_item_requested.connect(self._generate_item)

    def _apply_theme(self):
        """Apply the current theme stylesheet."""
        theme = "dark" if self._dark_mode else "light"
        ui_font_size = library.get_ui_font_size()
        qss = load_qss(theme, ui_font_size)
        # Apply to application level so context menus inherit styles properly
        app = QApplication.instance()
        if app:
            app.setStyleSheet(qss)
        else:
            self.setStyleSheet(qss)

        self.yaml_editor.set_dark_mode(self._dark_mode)
        self.file_templates_panel.editor.set_dark_mode(self._dark_mode)
        self.custom_tokens_panel.set_dark_mode(self._dark_mode)
        self.preview_panel.set_dark_mode(self._dark_mode)

    def _toggle_dark_mode(self, checked: bool):
        """Toggle between dark and light mode."""
        self._dark_mode = checked
        self._apply_theme()
        library.set_preference("dark_mode", checked)

    def _increase_font_size(self):
        """Increase the editor font size by 1pt."""
        current_size = library.get_editor_font_size()
        if current_size < 36:
            self._set_editor_font_size(current_size + 1)

    def _decrease_font_size(self):
        """Decrease the editor font size by 1pt."""
        current_size = library.get_editor_font_size()
        if current_size > 8:
            self._set_editor_font_size(current_size - 1)

    def _set_editor_font_size(self, size: int):
        """Set the editor font size and update editors."""
        library.set_editor_font_size(size)
        self._apply_editor_font_size(size)

    def _set_ui_font_size(self, size: int):
        """Set the UI font size and refresh the theme."""
        library.set_ui_font_size(size)
        self._apply_ui_font_size(size)

    def _apply_editor_font_size(self, size: int):
        """Apply the editor font size to code editors."""
        font = get_code_font(size)
        self.yaml_editor.setFont(font)
        self.file_templates_panel.editor.setFont(font)
        self.custom_tokens_panel.apply_font_size(size)

    def _apply_ui_font_size(self, size: int):
        """Apply the UI font size by refreshing the theme stylesheet."""
        theme = "dark" if self._dark_mode else "light"
        qss = load_qss(theme, size)
        # Apply to application level so context menus inherit styles properly
        app = QApplication.instance()
        if app:
            app.setStyleSheet(qss)
        else:
            self.setStyleSheet(qss)

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
        if (
            self.bottom_stack.currentWidget() == self.custom_tokens_panel
            and focus_widget is not None
            and self.custom_tokens_panel.isAncestorOf(focus_widget)
        ):
            self.custom_tokens_panel.save_current_token()
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
        was_suppressed = self._suppress_yaml_animation
        self._suppress_yaml_animation = True
        try:
            self.yaml_editor.setPlainText(text)
        finally:
            self._history_suspended = was_suspended
            self._suppress_yaml_animation = was_suppressed
        self._reset_yaml_history()

    def _set_yaml_text(self, text: str, *, block_signals: bool):
        """Set YAML text, optionally blocking change signals."""
        was_suspended = self._history_suspended
        self._history_suspended = True
        was_suppressed = self._suppress_yaml_animation
        self._suppress_yaml_animation = True
        try:
            if block_signals:
                self.yaml_editor.blockSignals(True)
            self.yaml_editor.setPlainText(text)
            if block_signals:
                self.yaml_editor.blockSignals(False)
        finally:
            self._history_suspended = was_suspended
            self._suppress_yaml_animation = was_suppressed
        self._reset_yaml_history()

    @staticmethod
    def _normalize_yaml_text(text: str) -> str:
        """Normalize line endings to avoid false dirty states."""
        return text.replace("\r\n", "\n").replace("\r", "\n")

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
        self._update_dialog = None
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
        self._update_dialog = None
        self._update_edit_actions()

    def _on_project_template_renamed(self, old_name: str, new_name: str):
        """Update draft bookkeeping for a renamed project template."""
        if old_name in self._project_template_drafts:
            self._project_template_drafts[new_name] = self._project_template_drafts.pop(old_name)
        last_template = library.get_preference("last_template")
        if last_template == old_name:
            library.set_preference("last_template", new_name)
        if self.project_templates_panel.is_current_template(new_name):
            self.preview_panel.set_project_name(new_name)

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
        custom_values = self.details_panel.get_custom_field_values()
        self._commit_yaml_history_entry()
        self._push_history_action(HistoryAction(
            undo=lambda n=name, c=content, wc=was_current, y=yaml_content,
                t=title, cv=custom_values:
                self._undo_delete_project_template(n, c, wc, y, t, cv),
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
        custom_values: dict[str, str],
    ):
        library.save_project_template(name, content)
        if was_current:
            self.project_templates_panel.set_current_template(name, content)
            self.yaml_editor.setPlainText(yaml_content)
            self._reset_yaml_history()
            self.details_panel.title_input.setText(title)
            self.details_panel.set_custom_field_values(custom_values)
            self._schedule_preview_update_without_animation()
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

    def _on_custom_token_action(self, action: str, name: str, old_token: dict, new_token: dict):
        if self._history_suspended:
            return
        self._commit_yaml_history_entry()
        if action == "add":
            self._push_history_action(HistoryAction(
                undo=lambda n=name: self._apply_custom_token_delete(n),
                redo=lambda n=name, t=new_token: self._apply_custom_token_set(n, t),
                label="Add Token"
            ))
        elif action == "update":
            self._push_history_action(HistoryAction(
                undo=lambda n=name, t=old_token: self._apply_custom_token_set(n, t),
                redo=lambda n=name, t=new_token: self._apply_custom_token_set(n, t),
                label="Update Token"
            ))
        elif action == "delete":
            self._push_history_action(HistoryAction(
                undo=lambda n=name, t=old_token: self._apply_custom_token_set(n, t),
                redo=lambda n=name: self._apply_custom_token_delete(n),
                label="Delete Token"
            ))

    def _apply_custom_token_set(self, name: str, token: dict):
        """Apply a token add/update without recording history."""
        if not token:
            return
        library.update_custom_token(
            name,
            token.get("value", ""),
            token.get("type", "text"),
        )
        self.custom_tokens_panel.refresh_list()
        self.custom_tokens_panel.tokens_changed.emit()
        if self.custom_tokens_panel.has_tokens():
            self.custom_tokens_panel.select_first_token()

    def _apply_custom_token_delete(self, name: str):
        """Apply a token delete without recording history."""
        library.delete_custom_token(name)
        self.custom_tokens_panel.refresh_list()
        self.custom_tokens_panel.tokens_changed.emit()
        if self.custom_tokens_panel.has_tokens():
            self.custom_tokens_panel.select_first_token()

    def _show_project_template_in_finder(self, name: str):
        """Reveal a project template file in the OS file manager."""
        path = library.get_project_template_path(name)
        if not path.exists():
            QMessageBox.warning(self, "File Not Found", f"Could not find: {name}.yaml")
            return
        if sys.platform == "darwin":
            os.system(f'open -R "{path}"')
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))

    def _configure_template_locations(self):
        project_path = library.get_project_templates_dir()
        file_path = library.get_file_templates_dir()
        custom_tokens_path = library.get_custom_tokens_path()
        project_generation_path = library.get_project_generation_dir()
        python_interpreter_path = library.get_python_interpreter_path()
        python_preamble = library.get_python_preamble()
        ui_font_size = library.get_ui_font_size()
        editor_font_size = library.get_editor_font_size()
        old_python_interpreter_path = python_interpreter_path
        old_python_preamble = python_preamble or ""
        dialog = TemplatePathsDialog(
            project_path,
            file_path,
            custom_tokens_path,
            project_generation_path,
            library.DEFAULT_PROJECT_TEMPLATES_DIR,
            library.DEFAULT_FILE_TEMPLATES_DIR,
            library.CUSTOM_TOKENS_PATH,
            library.DEFAULT_PROJECT_GENERATION_DIR,
            python_interpreter_path,
            library.DEFAULT_PYTHON_INTERPRETER,
            python_preamble,
            ui_font_size,
            editor_font_size,
            dark_mode=self._dark_mode,
            parent=self,
        )
        # Apply font size changes in real-time as user adjusts the spinboxes
        dialog.ui_font_size_changed.connect(self._apply_ui_font_size)
        dialog.editor_font_size_changed.connect(self._apply_editor_font_size)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            # Revert font sizes if dialog was cancelled
            self._apply_ui_font_size(ui_font_size)
            self._apply_editor_font_size(editor_font_size)
            return

        # Save font sizes if changed
        if dialog.ui_font_size_was_changed():
            library.set_ui_font_size(dialog.ui_font_size())
        if dialog.editor_font_size_was_changed():
            library.set_editor_font_size(dialog.editor_font_size())

        new_project_path = self._normalize_template_path(
            dialog.project_path_text(),
            library.DEFAULT_PROJECT_TEMPLATES_DIR,
        )
        new_file_path = self._normalize_template_path(
            dialog.file_path_text(),
            library.DEFAULT_FILE_TEMPLATES_DIR,
        )
        new_custom_tokens_path = self._normalize_custom_tokens_path(
            dialog.custom_tokens_path_text(),
            library.CUSTOM_TOKENS_PATH,
        )
        new_project_generation_path = self._normalize_template_path(
            dialog.project_generation_path_text(),
            library.DEFAULT_PROJECT_GENERATION_DIR,
        )
        new_python_interpreter_path = self._normalize_python_interpreter_path(
            dialog.python_interpreter_text(),
            library.DEFAULT_PYTHON_INTERPRETER,
        )
        new_python_preamble = dialog.python_preamble_text()

        if not self._validate_template_path(new_project_path, "Project templates"):
            return
        if not self._validate_template_path(new_file_path, "File templates"):
            return
        if not self._validate_custom_tokens_path(
            new_custom_tokens_path, "Custom tokens"
        ):
            return
        if not self._validate_generation_path(
            new_project_generation_path, "Project generation"
        ):
            return
        if not self._validate_python_interpreter_path(
            new_python_interpreter_path, "Python interpreter"
        ):
            return
        if not self._ensure_template_dir(new_project_path, "Project templates"):
            return
        if not self._ensure_template_dir(new_file_path, "File templates"):
            return
        if not self._ensure_custom_tokens_parent(new_custom_tokens_path, "Custom tokens"):
            return

        old_project_path = library.get_project_templates_dir()
        old_file_path = library.get_file_templates_dir()
        old_custom_tokens_path = library.get_custom_tokens_path()

        interpreter_text = dialog.python_interpreter_text()
        python_interpreter_changed = True
        try:
            python_interpreter_changed = (
                new_python_interpreter_path.resolve()
                != old_python_interpreter_path.resolve()
            )
        except Exception:
            python_interpreter_changed = (
                str(new_python_interpreter_path) != str(old_python_interpreter_path)
            )
        python_settings_changed = (
            python_interpreter_changed or new_python_preamble != old_python_preamble
        )
        if interpreter_text:
            library.set_python_interpreter_path(new_python_interpreter_path)
        else:
            library.set_python_interpreter_path(None)
        library.set_python_preamble(new_python_preamble)
        library.set_project_generation_dir(new_project_generation_path)

        template_paths_changed = not (
            old_project_path.resolve() == new_project_path.resolve()
            and old_file_path.resolve() == new_file_path.resolve()
            and old_custom_tokens_path.resolve() == new_custom_tokens_path.resolve()
        )
        if not template_paths_changed:
            if python_settings_changed:
                self._schedule_preview_update_without_animation()
            return

        if self._has_any_unsaved_changes():
            decision = QMessageBox.question(
                self,
                "Save Changes",
                "Save template changes before switching locations?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Cancel,
            )
            if decision != QMessageBox.StandardButton.Save:
                if python_settings_changed:
                    self._schedule_preview_update_without_animation()
                return
            self._save_all_changes()

        if dialog.should_move_existing():
            project_conflicts = self._move_template_directory(
                old_project_path, new_project_path
            )
            file_conflicts = self._move_template_directory(
                old_file_path, new_file_path
            )
            tokens_conflict = self._move_custom_tokens_file(
                old_custom_tokens_path, new_custom_tokens_path
            )
            self._notify_template_move_conflicts(
                project_conflicts, file_conflicts, tokens_conflict
            )

        library.set_template_paths(new_project_path, new_file_path)
        library.set_custom_tokens_path(new_custom_tokens_path)
        library.ensure_directories()
        library.set_preference("last_template", None)

        self._project_template_drafts.clear()
        self.project_templates_panel.clear_current_template()
        self.file_templates_panel.clear_all_state()
        self.custom_tokens_panel.clear_all_state()
        if self.custom_tokens_panel.has_tokens():
            self.custom_tokens_panel.select_first_token()
        self._schedule_preview_update_without_animation()

    def _normalize_template_path(self, raw_path: str, default_path: Path) -> Path:
        if not raw_path:
            return default_path
        return Path(raw_path).expanduser().resolve()

    def _normalize_custom_tokens_path(
        self, raw_path: str, default_path: Path
    ) -> Path:
        if not raw_path:
            return default_path
        return Path(raw_path).expanduser().resolve()

    def _normalize_python_interpreter_path(
        self, raw_path: str, default_path: Path
    ) -> Path:
        if not raw_path:
            return default_path
        return Path(raw_path).expanduser().resolve()

    def _validate_template_path(self, path: Path, label: str) -> bool:
        if path.exists() and not path.is_dir():
            QMessageBox.warning(
                self,
                "Invalid Folder",
                f"{label} path is not a folder.\n\n{path}",
            )
            return False
        return True

    def _validate_custom_tokens_path(self, path: Path, label: str) -> bool:
        if path.exists() and path.is_dir():
            QMessageBox.warning(
                self,
                "Invalid File",
                f"{label} path must be a file.\n\n{path}",
            )
            return False
        return True

    def _validate_generation_path(self, path: Path, label: str) -> bool:
        if not path.exists():
            QMessageBox.warning(
                self,
                "Folder Unavailable",
                f"{label} folder does not exist.\n\n{path}",
            )
            return False
        if not path.is_dir():
            QMessageBox.warning(
                self,
                "Invalid Folder",
                f"{label} path is not a folder.\n\n{path}",
            )
            return False
        return True

    def _validate_python_interpreter_path(self, path: Path, label: str) -> bool:
        if path.exists() and path.is_dir():
            QMessageBox.warning(
                self,
                "Invalid File",
                f"{label} path must be an executable file.\n\n{path}",
            )
            return False
        if not path.exists():
            QMessageBox.warning(
                self,
                "File Not Found",
                f"{label} path does not exist.\n\n{path}",
            )
            return False
        return True

    def _ensure_template_dir(self, path: Path, label: str) -> bool:
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError:
            QMessageBox.warning(
                self,
                "Folder Unavailable",
                f"Could not access the {label} folder.\n\n{path}",
            )
            return False
        return True

    def _ensure_custom_tokens_parent(self, path: Path, label: str) -> bool:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            QMessageBox.warning(
                self,
                "Folder Unavailable",
                f"Could not access the {label} folder.\n\n{path.parent}",
            )
            return False
        return True

    def _move_template_directory(self, source: Path, destination: Path) -> list[str]:
        if not source.exists():
            return []
        try:
            if source.resolve() == destination.resolve():
                return []
        except Exception:
            if source == destination:
                return []

        destination.mkdir(parents=True, exist_ok=True)
        conflicts = []
        for item in source.rglob("*"):
            if not item.is_file():
                continue
            rel = item.relative_to(source)
            if any(part.startswith(".") for part in rel.parts):
                continue
            target = destination / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                conflicts.append(rel.as_posix())
                continue
            shutil.move(str(item), str(target))

        for root, dirs, files in os.walk(source, topdown=False):
            if not dirs and not files:
                try:
                    Path(root).rmdir()
                except OSError:
                    pass
        return conflicts

    def _move_custom_tokens_file(self, source: Path, destination: Path) -> bool:
        if not source.exists():
            return False
        try:
            if source.resolve() == destination.resolve():
                return False
        except Exception:
            if source == destination:
                return False
        if destination.exists():
            return True
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
        except OSError:
            return True
        return False

    def _notify_template_move_conflicts(
        self,
        project_conflicts: list[str],
        file_conflicts: list[str],
        tokens_conflict: bool = False,
    ):
        total = len(project_conflicts) + len(file_conflicts)
        if tokens_conflict:
            total += 1
        if total == 0:
            return
        messages = []
        if project_conflicts or file_conflicts:
            messages.append(
                "Some templates were not moved because they already exist in the destination folder."
            )
        if tokens_conflict:
            messages.append(
                "The custom tokens file was not moved because it already exists at the destination."
            )
        QMessageBox.warning(
            self,
            "Template Move Conflicts",
            "\n\n".join(messages),
        )

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
        self.custom_tokens_panel.save_all_unsaved()

    def _has_any_unsaved_changes(self) -> bool:
        """Return True when any panel has unsaved edits."""
        if self.project_templates_panel.has_unsaved_changes():
            return True
        if self.file_templates_panel.has_unsaved_changes():
            return True
        if self.custom_tokens_panel.has_unsaved_changes():
            return True
        if self._project_template_drafts:
            return True
        return False

    def closeEvent(self, event):
        if self._force_quit:
            self._save_splitter_states()
            event.accept()
            return
        if not self._has_any_unsaved_changes():
            self._save_splitter_states()
            event.accept()
            return
        dialog = UnsavedChangesDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            event.ignore()
            return
        if dialog.choice == UnsavedChangesDialog.Choice.SAVE:
            self._save_all_changes()
        self._save_splitter_states()
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
        self.details_panel.clear_custom_field_values()
        self.preview_panel.set_project_name(self.project_templates_panel.get_template_name())
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
                self.preview_panel.set_project_name(self.project_templates_panel.get_template_name())
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
        original_name = name
        library.save_project_template(name, content)
        self._project_template_drafts.pop(name, None)
        self.project_templates_panel.mark_saved(name, content)
        self.preview_panel.set_project_name(name)
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
        self.preview_panel.set_project_name(self.project_templates_panel.get_template_name())

    def _clear_project_view(self):
        """Clear all project-specific panels (no template selected)."""
        self._set_yaml_text("", block_signals=True)
        self.details_panel.title_input.clear()
        self.details_panel.set_custom_fields([], animate=False)
        self.details_panel.clear_custom_field_values()
        self.preview_panel.tree.clear()
        self.preview_panel.content_view.clear()
        self.preview_panel.status_label.setText("")
        self.preview_panel.set_project_name(None)
        library.set_preference("last_template", None)

    def _focus_template_search(self):
        """Focus the template search box."""
        self.project_templates_panel.search_box.setFocus()
        self.project_templates_panel.search_box.selectAll()

    def _stash_current_project_template(self):
        """Cache unsaved YAML edits for the current template."""
        name = self.project_templates_panel.get_current_template_name()
        if not name:
            return
        content = self._normalize_yaml_text(self.yaml_editor.toPlainText())
        saved = self._normalize_yaml_text(self.project_templates_panel.get_original_content())
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
        templates = library.list_project_templates()
        if last_template:
            if last_template in templates:
                self._load_project_template(last_template)
                return
        if templates:
            # Templates exist but no last_template - show empty view
            self.project_templates_panel.clear_current_template()
            self._clear_project_view()
            return
        # No templates exist - show default YAML for new users
        self._set_yaml_text(DEFAULT_YAML, block_signals=False)
        self._update_preview()

    def _load_project_template(self, name: str):
        """Load a project template into the editor and details panel."""
        self._stash_current_project_template()
        content = library.load_project_template(name)
        if content is None:
            return
        normalized_content = self._normalize_yaml_text(content)
        draft = self._project_template_drafts.get(name)
        editor_content = draft if draft is not None else normalized_content
        self._set_yaml_text(editor_content, block_signals=True)
        if draft is None:
            original_content = self._normalize_yaml_text(self.yaml_editor.toPlainText())
        else:
            original_content = normalized_content
        self.project_templates_panel.set_current_template(name, original_content)
        self.project_templates_panel.mark_unsaved_changes(editor_content)
        self._schedule_preview_update_without_animation()
        self.preview_panel.set_project_name(name)
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

    def _schedule_preview_update_with_animation(self, animate_fields: bool):
        self._animate_fields_next = animate_fields
        self._schedule_preview_update()

    def _schedule_preview_update_from_yaml(self):
        if self._suppress_yaml_animation:
            self._schedule_preview_update_with_animation(False)
        else:
            self._schedule_preview_update_with_animation(True)

    def _schedule_preview_update_without_animation(self):
        self._schedule_preview_update_with_animation(False)

    def _schedule_preview_update(self):
        """Schedule a debounced preview refresh."""
        if self._preview_timer.isActive():
            self._preview_timer.stop()
        self._preview_timer.start(250)

    def _extract_error_line(self, message: str) -> int | None:
        match = re.search(r'line\s+(\d+)', message, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None

    def _find_token_line(self, yaml_text: str, token_name: str) -> int | None:
        if not token_name:
            return None
        token_re = re.compile(
            r'\{[mM][pP]\s*:\s*[^}]*\b' + re.escape(token_name) + r'\b',
            re.IGNORECASE,
        )
        alt_re = re.compile(
            r'\bmp\s*:\s*' + re.escape(token_name) + r'\b',
            re.IGNORECASE,
        )
        for index, line in enumerate(yaml_text.splitlines(), start=1):
            if token_re.search(line) or alt_re.search(line):
                return index
        return None

    def _find_line_for_key(self, yaml_text: str, key: str) -> int | None:
        if not key:
            return None
        token_match = re.search(r'[mM][pP]\s*:\s*([^\}\s]+)', key)
        if token_match:
            token_line = self._find_token_line(yaml_text, token_match.group(1))
            if token_line:
                return token_line
        for index, line in enumerate(yaml_text.splitlines(), start=1):
            if key in line:
                return index
        return None

    def _ensure_line_in_message(self, message: str, line: int | None) -> str:
        if line and not re.search(r'line\s+\d+', message, re.IGNORECASE):
            return f"{message} (line {line})"
        return message

    def _describe_yaml_error(self, exc: Exception, yaml_text: str) -> tuple[str, int | None]:
        if isinstance(exc, YAMLParseError) and exc.template_name:
            return str(exc), None
        if isinstance(exc, YAMLParseError):
            message = exc.message
            line = exc.line
        else:
            message = str(exc)
            line = None

        if line is None:
            line = self._extract_error_line(message)

        if line is None:
            token_match = re.search(r'Unknown token "([^"]+)"', message)
            if token_match:
                token_name = token_match.group(1)
                line = self._find_token_line(yaml_text, token_name)
                message = f'Unknown token "{token_name}".'

        if line is None:
            shorthand_match = re.search(
                r'Invalid shorthand folder for "([^"]+)"',
                message,
            )
            if shorthand_match:
                key = shorthand_match.group(1)
                line = self._find_line_for_key(yaml_text, key)
                message = f'Invalid shorthand folder for "{key}".'

        message = self._ensure_line_in_message(message, line)
        return message, line

    def _collect_missing_template_warnings(
        self,
        yaml_text: str,
        context,
    ) -> list[tuple[str, int | None]]:
        references = collect_template_references(yaml_text)
        if not references:
            return []
        project_templates = set(library.list_project_templates())
        file_templates = set(library.list_file_template_names())
        warnings: list[tuple[str, int | None]] = []
        for ref in references:
            raw_value = (ref.raw_value or "").strip()
            if not raw_value:
                continue
            if ref.key == "project_template":
                try:
                    template_name = substitute_tokens(raw_value, context).strip()
                except YAMLParseError:
                    continue
                if not template_name:
                    continue
                if template_name not in project_templates:
                    message = self._ensure_line_in_message(
                        f'Missing project template "{template_name}"',
                        ref.line,
                    )
                    warnings.append((message, ref.line))
            elif ref.key in ("file_template", "template"):
                if ref.key == "file_template":
                    try:
                        template_name = substitute_tokens(raw_value, context).strip()
                    except YAMLParseError:
                        continue
                else:
                    template_name = raw_value.strip()
                if not template_name:
                    continue
                if template_name not in file_templates:
                    message = self._ensure_line_in_message(
                        f'Missing file template "{template_name}"',
                        ref.line,
                    )
                    warnings.append((message, ref.line))
        return warnings

    def _get_yaml_hash(self, text: str) -> str:
        """Generate a fast hash for YAML content for cache keying."""
        import hashlib
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def _update_preview(self):
        """Refresh the preview panel based on YAML and details."""
        yaml_text = self.yaml_editor.toPlainText()
        title = self.details_panel.get_title()
        metadata, meta_error, meta_line = parse_template_metadata_with_error(yaml_text)
        if meta_error:
            self.yaml_editor.set_error_line(meta_line)
            self.yaml_editor.set_warning_line(None)
            self.preview_panel.update_tree(self._last_valid_tree, meta_error)
            return
        animate_fields = self._animate_fields_next
        self._animate_fields_next = False
        self.details_panel.set_custom_fields(
            metadata.fields if metadata else [],
            animate=animate_fields,
        )
        extra_tokens = self.details_panel.get_custom_field_values(apply_defaults=True)

        # Check YAML parse cache
        yaml_hash = self._get_yaml_hash(yaml_text)
        if yaml_hash in self._yaml_parse_cache:
            # Cache hit - use cached parse result
            data, error = self._yaml_parse_cache[yaml_hash]
        else:
            # Cache miss - parse and cache result
            data, error = parse_yaml(yaml_text)

            # Add to cache with LRU eviction
            if len(self._yaml_parse_cache) >= self._yaml_parse_cache_max_size:
                # Remove oldest entry (first inserted)
                oldest_hash = next(iter(self._yaml_parse_cache))
                del self._yaml_parse_cache[oldest_hash]

            self._yaml_parse_cache[yaml_hash] = (data, error)

        if error:
            self.yaml_editor.set_error_line(self._extract_error_line(error))
            self.yaml_editor.set_warning_line(None)
            self.preview_panel.update_tree(self._last_valid_tree, error)
            return

        context = build_token_context(
            data,
            title,
            "",
            extra_tokens,
            resolve_extra_tokens=True,
        )
        warnings = self._collect_missing_template_warnings(yaml_text, context)
        warning_message, warning_line = (warnings[0] if warnings else (None, None))
        try:
            tree = build_file_tree(data, context, allow_missing_templates=True)
        except Exception as exc:
            message, line = self._describe_yaml_error(exc, yaml_text)
            self.yaml_editor.set_error_line(line)
            self.yaml_editor.set_warning_line(None)
            self.preview_panel.update_tree(self._last_valid_tree, message)
            return
        self.yaml_editor.set_error_line(None)
        if warning_message:
            self.yaml_editor.set_warning_line(warning_line)
        else:
            self.yaml_editor.set_warning_line(None)
        if tree:
            self._last_valid_tree = tree
        if warning_message:
            self.preview_panel.update_tree(tree, warning_message, status_kind="warning")
        else:
            self.preview_panel.update_tree(tree)

    def _generate_project(self):
        """Generate the project on disk using the current YAML."""
        yaml_text = self.yaml_editor.toPlainText()
        data, error = parse_yaml(yaml_text)
        if error:
            self.yaml_editor.set_error_line(self._extract_error_line(error))
            QMessageBox.warning(self, "Invalid YAML", error)
            return
        if not self.details_panel.get_title().strip():
            dialog = EmptyTitleDialog(self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

        output_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            str(library.get_project_generation_dir())
        )
        if not output_dir:
            return
        output_path = Path(output_dir)

        context = build_token_context(
            data,
            self.details_panel.get_title(),
            "",
            self.details_panel.get_custom_field_values(apply_defaults=True),
            resolve_extra_tokens=True,
        )
        try:
            tree = build_file_tree(data, context)
        except Exception as exc:
            message, line = self._describe_yaml_error(exc, yaml_text)
            self.yaml_editor.set_error_line(line)
            QMessageBox.warning(self, "Invalid Template", message)
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

    def _find_node_by_path(self, root, target_path: str):
        """Find a FileNode by its path within the tree."""
        parts = target_path.split("/")

        def find_in_children(node, remaining_parts, current_path=""):
            if not remaining_parts:
                return None

            target_name = remaining_parts[0]
            for child in node.children:
                if child.name == target_name:
                    child_path = f"{current_path}/{child.name}".lstrip("/")
                    if len(remaining_parts) == 1:
                        return child
                    if child.is_folder:
                        return find_in_children(child, remaining_parts[1:], child_path)
            return None

        return find_in_children(root, parts)

    def _generate_item(self, item_path: str):
        """Generate a specific file or folder from the preview."""
        yaml_text = self.yaml_editor.toPlainText()
        data, error = parse_yaml(yaml_text)
        if error:
            self.yaml_editor.set_error_line(self._extract_error_line(error))
            QMessageBox.warning(self, "Invalid YAML", error)
            return

        context = build_token_context(
            data,
            self.details_panel.get_title(),
            "",
            self.details_panel.get_custom_field_values(apply_defaults=True),
            resolve_extra_tokens=True,
        )
        try:
            tree = build_file_tree(data, context)
        except Exception as exc:
            message, line = self._describe_yaml_error(exc, yaml_text)
            self.yaml_editor.set_error_line(line)
            QMessageBox.warning(self, "Invalid Template", message)
            return

        if not tree:
            QMessageBox.warning(self, "No Files", "No files defined in the YAML.")
            return

        # Find the specific node to generate
        target_node = self._find_node_by_path(tree, item_path)
        if not target_node:
            QMessageBox.warning(
                self, "Item Not Found", f"Could not find '{item_path}' in the project."
            )
            return

        output_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            str(library.get_project_generation_dir())
        )
        if not output_dir:
            return
        output_path = Path(output_dir)

        # Create a wrapper node with the target as its only child
        # This allows generate_project to work with a single item
        from dataclasses import replace
        wrapper = replace(tree, children=[target_node])

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

        success, message = generate_project(wrapper, output_path, on_progress, on_conflict)

        if success:
            self.progress_bar.setValue(100)
            QTimer.singleShot(500, lambda: self.progress_bar.setVisible(False))
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(output_path))):
                if sys.platform == "darwin":
                    os.system(f'open "{output_path}"')
        else:
            self.progress_bar.setVisible(False)

        if success:
            item_name = item_path.split("/")[-1]
            self._show_status(f"Generated: {item_name}")
        elif message != "Generation cancelled.":
            QMessageBox.warning(self, "Error", message)

    def _generate_file_from_template(self, template_name: str, content: str):
        """Generate a file from a file template using current project details."""
        from makeproject.template_engine import build_token_context, substitute_tokens
        from PyQt6.QtWidgets import QFileDialog

        # Build token context from current project details
        context = build_token_context(
            None,  # No YAML data for file templates
            self.details_panel.get_title(),
            "",
            self.details_panel.get_custom_field_values(apply_defaults=True),
            resolve_extra_tokens=True,
        )

        # Add filename token (defaults to template's filename)
        filename = Path(template_name).name
        context['filename'] = filename
        context['filename'.lower()] = filename  # Case-insensitive alias

        # Substitute tokens in the template
        try:
            generated_content = substitute_tokens(content, context)
        except Exception as e:
            QMessageBox.warning(self, "Template Error", f"Error processing template: {e}")
            return

        # Ask user where to save the file
        suggested_name = Path(template_name).name  # Get filename without folder
        output_file, _ = QFileDialog.getSaveFileName(
            self,
            "Save Generated File",
            str(library.get_project_generation_dir() / suggested_name),
            "All Files (*)"
        )

        if not output_file:
            return

        # Save the file
        try:
            Path(output_file).write_text(generated_content, encoding="utf-8")
            self._show_status(f"Generated: {Path(output_file).name}")

            # Open the file location
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(output_file).parent))):
                if sys.platform == "darwin":
                    os.system(f'open -R "{output_file}"')
        except Exception as e:
            QMessageBox.warning(self, "Save Error", f"Failed to save file: {e}")

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
            style_default_dialog_button(merge_btn)
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
            style_default_dialog_button(keep_btn)
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
        if self._update_dialog:
            self._update_dialog.close()

        self._update_dialog = UpdateDialog(version, self)
        self._update_dialog.update_requested.connect(
            lambda: self._download_update(url)
        )
        self._update_dialog.rejected.connect(self._on_update_dialog_closed)
        self._update_dialog.open()

    def _on_update_dialog_closed(self):
        self._update_dialog = None

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
        dialog = self._update_dialog
        if not dialog:
            return

        dialog.set_progress(0)
        dialog.set_status("Downloading update...")

        self.update_downloader = UpdateDownloader(url)
        self.update_downloader.progress.connect(dialog.set_progress)
        self.update_downloader.status.connect(dialog.set_status)
        self.update_downloader.finished.connect(self._on_update_finished)
        self.update_downloader.start()

    def _on_update_finished(self, success: bool, message: str):
        """Handle update completion."""
        dialog = self._update_dialog
        if not dialog:
            return

        if success:
            dialog.mark_finished(True, "Update installed. Relaunching...")
            self._relaunch_updated_app()
        else:
            dialog.mark_finished(False, message)

    def _relaunch_updated_app(self):
        app_path = get_app_path()
        if not app_path:
            if self._update_dialog:
                self._update_dialog.set_status(
                    "Update installed. Please relaunch the app."
                )
            return

        def relaunch_and_quit():
            if relaunch_app(app_path):
                self._force_quit = True
                if self._update_dialog:
                    self._update_dialog.close()
                self.close()
                QApplication.instance().quit()
            elif self._update_dialog:
                self._update_dialog.set_status(
                    "Update installed. Please relaunch the app."
                )

        QTimer.singleShot(300, relaunch_and_quit)

    def paintEvent(self, event):
        """Paint rounded corners for frameless window."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(self.rect().toRectF(), 12, 12)

        painter.setClipPath(path)

        super().paintEvent(event)
