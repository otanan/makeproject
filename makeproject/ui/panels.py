"""
Panels and controls used by the main MakeProject window.
"""

import sys
import subprocess
from pathlib import Path, PurePosixPath

from PyQt6.QtCore import (
    Qt, QSize, QPoint, pyqtSignal, QTimer, QPropertyAnimation,
    QEasingCurve, QUrl
)
from PyQt6.QtGui import (
    QColor, QDesktopServices, QTextCursor, QPainter,
    QPainterPath, QPixmap
)
from PyQt6.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QTextEdit, QTreeWidget,
    QTreeWidgetItem, QMessageBox, QMenu, QSplitter, QSizePolicy
)

from ..styles import get_code_font
from .. import library
from ..highlighter import PythonHighlighter
from ..widgets import ToggleSwitch
from .editors import CodeEditor
from .dialog_utils import style_default_dialog_button
from .template_items import TemplateListItem, AddTemplateButton


def _create_disclosure_icons():
    """Create and save disclosure triangle icons, returning file paths."""
    from tempfile import gettempdir

    icons_dir = Path(gettempdir()) / "makeproject_icons"
    icons_dir.mkdir(exist_ok=True)

    paths = {}

    for mode in ("dark", "light"):
        color = QColor("#6C7086") if mode == "dark" else QColor("#9CA3AF")

        closed_pixmap = QPixmap(12, 12)
        closed_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(closed_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        path = QPainterPath()
        path.moveTo(3, 1)
        path.lineTo(9, 6)
        path.lineTo(3, 11)
        path.closeSubpath()
        painter.drawPath(path)
        painter.end()

        closed_path = icons_dir / f"disclosure_closed_{mode}.png"
        closed_pixmap.save(str(closed_path))

        open_pixmap = QPixmap(12, 12)
        open_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(open_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        path = QPainterPath()
        path.moveTo(1, 3)
        path.lineTo(11, 3)
        path.lineTo(6, 9)
        path.closeSubpath()
        painter.drawPath(path)
        painter.end()

        open_path = icons_dir / f"disclosure_open_{mode}.png"
        open_pixmap.save(str(open_path))

        paths[mode] = (str(closed_path), str(open_path))

    return paths


_DISCLOSURE_ICON_PATHS = None


def _get_disclosure_icon_paths():
    """Get or create disclosure icon paths."""
    global _DISCLOSURE_ICON_PATHS
    if _DISCLOSURE_ICON_PATHS is None:
        _DISCLOSURE_ICON_PATHS = _create_disclosure_icons()
    return _DISCLOSURE_ICON_PATHS


def get_disclosure_stylesheet(dark_mode: bool = True) -> str:
    """Build a stylesheet string for tree disclosure icons."""
    paths = _get_disclosure_icon_paths()
    mode = "dark" if dark_mode else "light"
    closed_path, open_path = paths[mode]

    return f"""
        QTreeWidget::branch:has-children:!has-siblings:closed,
        QTreeWidget::branch:closed:has-children:has-siblings {{
            image: url({closed_path});
        }}
        QTreeWidget::branch:open:has-children:!has-siblings,
        QTreeWidget::branch:open:has-children:has-siblings {{
            image: url({open_path});
        }}
    """


class ProjectTemplatesPanel(QFrame):
    """Left panel: list of project templates with create/rename/delete."""

    template_selected = pyqtSignal(str)
    save_requested = pyqtSignal()
    new_template_requested = pyqtSignal()
    template_renamed = pyqtSignal(str, str)
    clear_requested = pyqtSignal()
    template_delete_requested = pyqtSignal(str)
    show_in_finder_requested = pyqtSignal(str)

    def __init__(self, parent=None, draft_store=None):
        super().__init__(parent)
        self.setObjectName("projectTemplatesPanel")
        self.setProperty("class", "panel")

        self._current_template = None
        self._has_unsaved_changes = False
        self._original_content = ""
        self._draft_store = draft_store if draft_store is not None else {}
        self._editing_new = False
        self._renaming_template = None
        self._draft_name_seed = ""
        self._refreshing = False
        self._refresh_pending = False
        self._click_timer = QTimer()
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(250)
        self._pending_click_name = None
        self._mouse_click_in_progress = False
        self._mouse_clear_timer = QTimer()
        self._mouse_clear_timer.setSingleShot(True)
        self._mouse_clear_timer.timeout.connect(self._clear_mouse_click_flag)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QLabel("PROJECT TEMPLATES")
        header.setProperty("class", "panelHeader")
        header.setToolTip("Saved project template configurations")
        layout.addWidget(header)

        self.template_list = QListWidget()
        self.template_list.itemClicked.connect(self._on_item_clicked)
        self.template_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.template_list.currentItemChanged.connect(self._on_current_item_changed)
        self.template_list.installEventFilter(self)
        self.template_list.viewport().installEventFilter(self)
        self.template_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.template_list.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.template_list)

        self.refresh_list()

    def refresh_list(self):
        """Refresh the template list from disk."""
        if self._refreshing:
            self._refresh_pending = True
            return
        self._refreshing = True
        self.template_list.clear()
        templates = library.list_project_templates()
        unsaved_names = set(self._draft_store.keys())
        if self._has_unsaved_changes and self._current_template:
            unsaved_names.add(self._current_template)

        for name in templates:
            if name == self._renaming_template:
                item = QListWidgetItem()
                widget = TemplateListItem(
                    name,
                    editable=True,
                    placeholder="Template name...",
                )
                widget.name_edited.connect(self._on_rename_confirmed)
                widget.name_canceled.connect(self._on_rename_canceled)
                widget.name_edit.setText(name)
                item.setSizeHint(widget.sizeHint())
                self.template_list.addItem(item)
                self.template_list.setItemWidget(item, widget)
                self.template_list.setCurrentItem(item)
                QTimer.singleShot(50, widget.focus_edit)
            else:
                item = QListWidgetItem()
                widget = TemplateListItem(
                    name,
                    allow_delete=True,
                )
                tooltip = self._get_template_tooltip(name)
                if tooltip:
                    widget.setToolTip(tooltip)
                widget.rename_requested.connect(self._start_rename_template)
                widget.delete_clicked.connect(self._delete_template)
                if name in unsaved_names:
                    widget.set_unsaved(True)
                item.setSizeHint(widget.sizeHint())
                self.template_list.addItem(item)
                self.template_list.setItemWidget(item, widget)

                if name == self._current_template:
                    self.template_list.setCurrentItem(item)

        if self._editing_new:
            item = QListWidgetItem()
            widget = TemplateListItem(
                "",
                editable=True,
                placeholder="Template name...",
            )
            widget.name_edited.connect(self._on_new_name_confirmed)
            widget.name_canceled.connect(self._on_new_name_canceled)
            if self._draft_name_seed:
                widget.name_edit.setText(self._draft_name_seed)
            item.setSizeHint(widget.sizeHint())
            self.template_list.addItem(item)
            self.template_list.setItemWidget(item, widget)
            self.template_list.setCurrentItem(item)
            QTimer.singleShot(50, widget.focus_edit)
        elif self._current_template is None and self._has_unsaved_changes:
            item = QListWidgetItem()
            widget = TemplateListItem(
                "untitled project",
                allow_delete=False,
            )
            widget.set_unsaved(True)
            widget.rename_requested.connect(self._start_draft_naming)
            item.setSizeHint(widget.sizeHint())
            self.template_list.addItem(item)
            self.template_list.setItemWidget(item, widget)
            self.template_list.setCurrentItem(item)

        add_item = QListWidgetItem()
        add_widget = AddTemplateButton()
        add_widget.clicked.connect(self._create_new_template)
        add_item.setSizeHint(QSize(0, add_widget.sizeHint().height()))
        add_item.setFlags(
            add_item.flags()
            & ~Qt.ItemFlag.ItemIsSelectable
            & ~Qt.ItemFlag.ItemIsEnabled
        )
        self.template_list.addItem(add_item)
        self.template_list.setItemWidget(add_item, add_widget)

        self._refreshing = False
        if self._refresh_pending:
            self._refresh_pending = False
            QTimer.singleShot(0, self.refresh_list)

    def _get_template_tooltip(self, name: str) -> str | None:
        content = library.load_project_template(name)
        if not content:
            return None
        lines = content.splitlines()
        if not lines:
            return None
        first_line = lines[0].strip()
        if not first_line.startswith("#"):
            return None
        return first_line

    def eventFilter(self, obj, event):
        """Handle keyboard events for template list."""
        from PyQt6.QtCore import QEvent
        if obj in (self.template_list, self.template_list.viewport()):
            if event.type() == QEvent.Type.MouseButtonPress:
                self._mouse_click_in_progress = True
            elif event.type() in (QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick):
                self._mouse_clear_timer.start(0)
            elif event.type() == QEvent.Type.FocusOut:
                self._finalize_pending_click()
            elif event.type() == QEvent.Type.KeyPress:
                if self._pending_click_name or self._click_timer.isActive():
                    self._finalize_pending_click()
                key = event.key()

                if key == Qt.Key.Key_Down:
                    current_row = self.template_list.currentRow()
                    if current_row >= self.template_list.count() - 2:
                        return True
                elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    current = self.template_list.currentItem()
                    if current:
                        widget = self.template_list.itemWidget(current)
                        if isinstance(widget, TemplateListItem) and not widget._editable:
                            name = widget.get_name()
                            if name:
                                if widget._allow_delete:
                                    self._renaming_template = name
                                    self.refresh_list()
                                elif self._current_template is None and self._has_unsaved_changes:
                                    self._start_draft_naming(name)
                                return True
        return super().eventFilter(obj, event)

    def _on_current_item_changed(self, current, previous):
        if self._refreshing or current is None:
            return
        if self._mouse_click_in_progress or self._pending_click_name or self._click_timer.isActive():
            return
        widget = self.template_list.itemWidget(current)
        if isinstance(widget, TemplateListItem):
            name = widget.get_name()
            if name and widget._allow_delete and not widget._editable and name != self._current_template:
                self.template_selected.emit(name)

    def _clear_mouse_click_flag(self):
        self._mouse_click_in_progress = False

    def _finalize_pending_click(self):
        if self._click_timer.isActive():
            self._click_timer.stop()
        if self._pending_click_name:
            self.template_selected.emit(self._pending_click_name)
            self._pending_click_name = None
        self._mouse_click_in_progress = False

    def _show_context_menu(self, pos):
        item = self.template_list.itemAt(pos)
        if item is None:
            return
        widget = self.template_list.itemWidget(item)
        if not isinstance(widget, TemplateListItem) or widget._editable:
            return
        name = widget.get_name()
        if not name:
            return
        content = library.load_project_template(name)
        if content is None:
            return
        self.template_list.setCurrentItem(item)
        menu = QMenu(self)
        rename_action = menu.addAction("Rename")
        duplicate_action = menu.addAction("Duplicate")
        show_action = menu.addAction("Show in Finder")
        menu.addSeparator()
        delete_action = menu.addAction("Delete")
        action = menu.exec(self.template_list.viewport().mapToGlobal(pos))
        if action == rename_action:
            self._start_rename_template(name)
        elif action == duplicate_action:
            self._duplicate_template(name)
        elif action == show_action:
            self.show_in_finder_requested.emit(name)
        elif action == delete_action:
            self._delete_template(name)

    def _start_rename_template(self, name: str):
        self._click_timer.stop()
        self._pending_click_name = None
        self._renaming_template = name
        self.refresh_list()

    def _duplicate_template(self, name: str):
        content = library.load_project_template(name)
        if content is None:
            return
        new_name = self._next_available_template_name(name)
        library.save_project_template(new_name, content)
        self.refresh_list()
        self.template_selected.emit(new_name)

    def _on_item_clicked(self, item: QListWidgetItem):
        widget = self.template_list.itemWidget(item)
        if isinstance(widget, TemplateListItem):
            name = widget.get_name()
            if name and widget._allow_delete and not widget._editable:
                if name == self._current_template:
                    return
                self._pending_click_name = name
                if self._click_timer.receivers(self._click_timer.timeout) > 0:
                    self._click_timer.timeout.disconnect()
                self._click_timer.timeout.connect(self._process_single_click)
                self._click_timer.start()

    def _process_single_click(self):
        if self._pending_click_name:
            self.template_selected.emit(self._pending_click_name)
        self._pending_click_name = None

    def _on_item_double_clicked(self, item: QListWidgetItem):
        self._click_timer.stop()
        self._pending_click_name = None

        widget = self.template_list.itemWidget(item)
        if isinstance(widget, TemplateListItem) and not widget._editable:
            name = widget.get_name()
            if name:
                if widget._allow_delete:
                    self._renaming_template = name
                    self.refresh_list()
                elif self._current_template is None and self._has_unsaved_changes:
                    self._start_draft_naming(name)

    def _create_new_template(self):
        """Start creating a new template with inline name editing."""
        self._current_template = None
        self._has_unsaved_changes = False
        self._original_content = ""
        self._editing_new = True
        self._renaming_template = None
        self._draft_name_seed = ""
        self.new_template_requested.emit()
        self.refresh_list()

    def _on_new_name_confirmed(self, old_name: str, new_name: str):
        """Finalize a new template name entry."""
        self._draft_name_seed = ""
        name = new_name.strip()
        if name == "untitled project":
            name = self.get_unique_template_name(name)
        elif name in library.list_project_templates():
            decision = self._prompt_template_name_conflict(name)
            if decision == "cancel":
                self._editing_new = False
                self.refresh_list()
                return
            if decision == "keep":
                name = self._next_available_template_name(name)
        self._editing_new = False
        self._current_template = name
        self.save_requested.emit()

    def _on_new_name_canceled(self, old_name: str):
        if self._editing_new and not self._draft_name_seed:
            pending_name = self.get_template_name().strip()
            if not pending_name:
                self._draft_name_seed = ""
                self._on_new_name_confirmed(old_name, "untitled project")
                return
        self._draft_name_seed = ""
        self._editing_new = False
        self.refresh_list()

    def _start_draft_naming(self, name: str):
        """Start naming an unsaved draft without clearing its content."""
        self._editing_new = True
        self._renaming_template = None
        self._draft_name_seed = name
        self.refresh_list()

    def _on_rename_confirmed(self, old_name: str, new_name: str):
        self._renaming_template = None
        name = new_name.strip()
        if not name or old_name == name:
            self.refresh_list()
            return

        old_path = library.get_project_template_path(old_name)
        if old_path.exists():
            if library.rename_project_template(old_name, name):
                if self._current_template == old_name:
                    self._current_template = name
                if old_name in self._draft_store:
                    self._draft_store[name] = self._draft_store.pop(old_name)
                self.template_renamed.emit(old_name, name)
            self.refresh_list()
            return

        if old_name in self._draft_store:
            self._draft_store[name] = self._draft_store.pop(old_name)
        self._current_template = name
        self._has_unsaved_changes = True
        self.save_requested.emit()
        self.refresh_list()

    def _on_rename_canceled(self, old_name: str):
        self._renaming_template = None
        self.refresh_list()

    def _next_available_template_name(self, name: str) -> str:
        existing = set(library.list_project_templates())
        index = 1
        while True:
            candidate = f"{name} ({index})"
            if candidate not in existing:
                return candidate
            index += 1

    def get_unique_template_name(self, name: str) -> str:
        if not name:
            return name
        if name in library.list_project_templates():
            return self._next_available_template_name(name)
        return name

    def _prompt_template_name_conflict(self, name: str) -> str:
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setWindowTitle("Template Exists")
        dialog.setText(f"\"{name}\" already exists.")
        dialog.setInformativeText("Choose what to do with this template.")
        overwrite_btn = dialog.addButton("Overwrite", QMessageBox.ButtonRole.DestructiveRole)
        keep_btn = dialog.addButton("Keep Both", QMessageBox.ButtonRole.AcceptRole)
        cancel_btn = dialog.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        overwrite_btn.setProperty("class", "dangerButton")
        style_default_dialog_button(keep_btn)
        cancel_btn.setProperty("class", "cancelButton")
        dialog.setDefaultButton(keep_btn)
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked == cancel_btn:
            return "cancel"
        if clicked == keep_btn:
            return "keep"
        return "overwrite"

    def _delete_template(self, name: str):
        """Delete a template with slide animation."""
        prev_name = self.get_previous_template_name(name)
        for i in range(self.template_list.count()):
            item = self.template_list.item(i)
            widget = self.template_list.itemWidget(item)
            if isinstance(widget, TemplateListItem) and widget.get_name() == name:
                start_pos = widget.pos()
                end_pos = QPoint(-widget.width(), start_pos.y())

                animation = QPropertyAnimation(widget, b"pos")
                animation.setDuration(200)
                animation.setStartValue(start_pos)
                animation.setEndValue(end_pos)
                animation.setEasingCurve(QEasingCurve.Type.InQuad)

                def on_finished():
                    self.template_delete_requested.emit(name)
                    library.delete_project_template(name)
                    if name == self._current_template:
                        self._current_template = None
                        self._has_unsaved_changes = False
                        self._original_content = ""
                        if prev_name:
                            self.template_selected.emit(prev_name)
                        else:
                            self.clear_requested.emit()
                    self.refresh_list()

                animation.finished.connect(on_finished)
                animation.start()
                widget._delete_animation = animation
                return

        self.template_delete_requested.emit(name)
        library.delete_project_template(name)
        if name == self._current_template:
            self._current_template = None
            self._has_unsaved_changes = False
            self._original_content = ""
            if prev_name:
                self.template_selected.emit(prev_name)
            else:
                self.clear_requested.emit()
        self.refresh_list()

    def set_current_template(self, name: str, content: str = ""):
        self._current_template = name
        self._original_content = content
        self._has_unsaved_changes = False
        self._editing_new = False
        self.refresh_list()

    def mark_unsaved_changes(self, current_content: str):
        """Update the unsaved indicator based on editor content."""
        has_changes = current_content != self._original_content
        if has_changes != self._has_unsaved_changes:
            self._has_unsaved_changes = has_changes
            self.refresh_list()

    def mark_saved(self, name: str, content: str):
        """Mark the current template as saved."""
        self._current_template = name
        self._original_content = content
        self._has_unsaved_changes = False
        self._editing_new = False
        self.refresh_list()

    def clear_current_template(self):
        """Clear selection and reset edit state."""
        self._current_template = None
        self._original_content = ""
        self._has_unsaved_changes = False
        self._editing_new = False
        self._renaming_template = None
        self.refresh_list()

    def is_current_template(self, name: str) -> bool:
        return self._current_template == name

    def has_unsaved_changes(self) -> bool:
        return self._has_unsaved_changes

    def get_current_template_name(self) -> str:
        return self._current_template or ""

    def is_editing_new(self) -> bool:
        return self._editing_new

    def get_previous_template_name(self, name: str) -> str:
        templates = library.list_project_templates()
        try:
            index = templates.index(name)
        except ValueError:
            return ""
        if index > 0:
            return templates[index - 1]
        return ""

    def finalize_new_template_name(self, default_name: str = "untitled project") -> str | None:
        """Finalize the inline new-template name, returning the resolved name."""
        if not self._editing_new:
            return self._current_template or ""

        name = ""
        for i in range(self.template_list.count()):
            widget = self.template_list.itemWidget(self.template_list.item(i))
            if isinstance(widget, TemplateListItem) and widget._editable:
                name = widget.get_name()
                break

        if not name:
            name = default_name

        if name == "untitled project":
            name = self.get_unique_template_name(name)
        elif name in library.list_project_templates():
            decision = self._prompt_template_name_conflict(name)
            if decision == "cancel":
                return None
            if decision == "keep":
                name = self._next_available_template_name(name)

        self._editing_new = False
        self._current_template = name
        return name

    def get_template_name(self) -> str:
        """Return the editable name when creating a new template."""
        if self._editing_new:
            for i in range(self.template_list.count()):
                widget = self.template_list.itemWidget(self.template_list.item(i))
                if isinstance(widget, TemplateListItem) and widget._editable:
                    return widget.get_name()
        return self._current_template or ""


class DetailsPanel(QFrame):
    """Right top panel: title and description inputs."""

    values_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("detailsPanel")
        self.setProperty("class", "panel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QLabel("DETAILS")
        header.setProperty("class", "panelHeader")
        header.setToolTip("Project title and description for token substitution")
        layout.addWidget(header)

        title_label = QLabel("Title")
        layout.addWidget(title_label)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("My Project")
        self.title_input.textChanged.connect(self.values_changed.emit)
        layout.addWidget(self.title_input)

        desc_label = QLabel("Description")
        layout.addWidget(desc_label)

        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("A brief description...")
        self.desc_input.textChanged.connect(self.values_changed.emit)
        self.desc_input.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self.desc_input, 1)

    def get_title(self) -> str:
        return self.title_input.text()

    def get_description(self) -> str:
        return self.desc_input.toPlainText()


class PreviewPanel(QFrame):
    """Right middle panel: file tree preview and content viewer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("previewPanel")
        self.setProperty("class", "panel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header_layout = QHBoxLayout()

        self.header_label = QLabel("PREVIEW")
        self.header_label.setProperty("class", "panelHeader")
        self.header_label.setToolTip("Preview of the generated project structure")
        header_layout.addWidget(self.header_label)

        header_layout.addStretch()

        self.status_label = QLabel("")
        self.status_label.setProperty("class", "muted")
        header_layout.addWidget(self.status_label)

        layout.addLayout(header_layout)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter = splitter

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.currentItemChanged.connect(self._on_current_item_changed)
        self.tree.setIndentation(14)
        self.tree.setRootIsDecorated(True)
        self.tree.setAnimated(True)
        self.tree.installEventFilter(self)
        self._last_nav_direction = None

        self._dark_mode = True
        self._apply_disclosure_icons()

        splitter.addWidget(self.tree)

        self.content_view = QTextEdit()
        self.content_view.setReadOnly(True)
        self.content_view.setFont(get_code_font())
        self.content_view.setPlaceholderText("Empty file.")
        line_height = self.content_view.fontMetrics().height()
        self.content_view.setMinimumHeight((line_height * 3) + 16)
        splitter.addWidget(self.content_view)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setSizes([260, 200])

        layout.addWidget(splitter, 1)

        self._file_contents = {}
        self._expansion_states = {}

    def set_project_name(self, name: str | None):
        if name:
            self.header_label.setText(f"PREVIEW - {name.upper()}")
        else:
            self.header_label.setText("PREVIEW")

    def update_tree(self, root_node, error_message: str = None):
        """Update the preview tree with file nodes."""
        if error_message:
            self.status_label.setText(error_message)
            self.status_label.setProperty("class", "error")
            self.status_label.style().polish(self.status_label)
            return

        if self.tree.topLevelItemCount():
            self._expansion_states = self._collect_expansion_states()

        selected_path = None
        current_item = self.tree.currentItem()
        if current_item:
            is_placeholder = current_item.data(0, Qt.ItemDataRole.UserRole + 2)
            if not is_placeholder:
                selected_path = current_item.data(0, Qt.ItemDataRole.UserRole)

        self.tree.blockSignals(True)
        self.tree.setUpdatesEnabled(False)
        self.tree.clearSelection()
        self.tree.setCurrentItem(None)

        if not root_node:
            self.status_label.setText("No files")
            self.tree.clear()
            self._file_contents = {}
            self._clear_content_view()
            self.tree.setUpdatesEnabled(True)
            self.tree.blockSignals(False)
            return

        file_count = root_node.file_count()
        self.status_label.setText(f"{file_count} file{'s' if file_count != 1 else ''}")
        self.status_label.setProperty("class", "muted")
        self.status_label.style().polish(self.status_label)

        self.tree.clear()
        self._file_contents = {}
        expanded_paths = {
            path for path, expanded in self._expansion_states.items() if expanded
        }

        def add_node(parent_item, node, parent_path=""):
            display_name = node.name + "/" if node.is_folder else node.name
            item = QTreeWidgetItem([display_name])
            full_path = f"{parent_path}/{node.name}".lstrip("/")
            item.setData(0, Qt.ItemDataRole.UserRole, full_path)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, node.is_folder)
            if node.source_template:
                item.setForeground(0, QColor("#1ABC9D"))
                font = item.font(0)
                font.setBold(True)
                item.setFont(0, font)

            if parent_item:
                parent_item.addChild(item)
            else:
                self.tree.addTopLevelItem(item)

            if node.is_folder:
                for child in node.children:
                    add_node(item, child, full_path)
                if not node.children:
                    self._add_empty_folder_placeholder(item)
                if full_path in self._expansion_states:
                    item.setExpanded(self._expansion_states[full_path])
                else:
                    item.setExpanded(True)
            else:
                self._file_contents[full_path] = node.content

        for child in root_node.children:
            add_node(None, child)

        if selected_path and self._is_path_visible(selected_path, expanded_paths):
            item = self._find_item_by_path(selected_path)
            if item:
                self.tree.setCurrentItem(item)
                self._update_content_for_item(item)
            else:
                self._clear_content_view()
        else:
            self._clear_content_view()

        self.tree.setUpdatesEnabled(True)
        self.tree.blockSignals(False)

    def _collect_expansion_states(self):
        states = {}

        def walk(item):
            if item.data(0, Qt.ItemDataRole.UserRole + 1):
                path = item.data(0, Qt.ItemDataRole.UserRole)
                if path:
                    states[path] = item.isExpanded()
                for i in range(item.childCount()):
                    walk(item.child(i))

        for i in range(self.tree.topLevelItemCount()):
            walk(self.tree.topLevelItem(i))

        return states

    def _is_path_visible(self, path: str, expanded_paths: set) -> bool:
        if not path:
            return False
        parts = path.split("/")
        if len(parts) <= 1:
            return True
        current = ""
        for part in parts[:-1]:
            current = part if not current else f"{current}/{part}"
            if current not in expanded_paths:
                return False
        return True

    def _find_item_by_path(self, path: str):
        def search(item):
            if item.data(0, Qt.ItemDataRole.UserRole) == path:
                return item
            for i in range(item.childCount()):
                result = search(item.child(i))
                if result:
                    return result
            return None

        for i in range(self.tree.topLevelItemCount()):
            result = search(self.tree.topLevelItem(i))
            if result:
                return result
        return None

    def _add_empty_folder_placeholder(self, parent_item):
        placeholder = QTreeWidgetItem(["Empty folder"])
        placeholder.setData(0, Qt.ItemDataRole.UserRole, None)
        placeholder.setData(0, Qt.ItemDataRole.UserRole + 1, False)
        placeholder.setData(0, Qt.ItemDataRole.UserRole + 2, True)
        font = placeholder.font(0)
        font.setItalic(True)
        placeholder.setFont(0, font)
        placeholder.setForeground(0, QColor(128, 128, 128))
        placeholder.setFlags(placeholder.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        parent_item.addChild(placeholder)

    def eventFilter(self, obj, event):
        """Intercept key events to handle navigation over Empty folder placeholders."""
        from PyQt6.QtCore import QEvent
        if obj == self.tree and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            current = self.tree.currentItem()

            if current and key == Qt.Key.Key_Down:
                is_folder = current.data(0, Qt.ItemDataRole.UserRole + 1)
                if is_folder and current.isExpanded() and current.childCount() > 0:
                    first_child = current.child(0)
                    if first_child and first_child.data(0, Qt.ItemDataRole.UserRole + 2):
                        next_item = self._get_next_item_after(current)
                        if next_item:
                            self.tree.setCurrentItem(next_item)
                            self._update_content_for_item(next_item)
                            return True

            elif current and key == Qt.Key.Key_Up:
                prev_item = self._get_previous_visible_item(current)
                if prev_item and prev_item.data(0, Qt.ItemDataRole.UserRole + 2):
                    parent = prev_item.parent()
                    if parent:
                        self.tree.setCurrentItem(parent)
                        self._update_content_for_item(parent)
                        return True

        return super().eventFilter(obj, event)

    def _get_previous_visible_item(self, item):
        return self.tree.itemAbove(item)

    def _clear_content_view(self):
        self.content_view.clear()
        self.content_view.setPlaceholderText("Select a file to preview its contents.")

    def _update_content_for_item(self, item):
        """ Updates the Preview panel with the content for the active item. """
        if item is None:
            return
        is_folder = item.data(0, Qt.ItemDataRole.UserRole + 1)
        path = item.data(0, Qt.ItemDataRole.UserRole)

        self.content_view.clear()

        if is_folder:
            self.content_view.setPlaceholderText("Select a file to preview its contents.")
            return
        
        # Get the file contents and show the preview.
        content = self._file_contents.get(path, "")
        if content == "":
            # Remove plain text that might appear.
            self.content_view.setPlaceholderText("Empty file.")
        else:
            self.content_view.setPlainText(content)

    def _on_item_clicked(self, item: QTreeWidgetItem):
        if item is None:
            return
        is_placeholder = item.data(0, Qt.ItemDataRole.UserRole + 2)
        if is_placeholder:
            return
        is_folder = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if is_folder:
            item.setExpanded(not item.isExpanded())
        self._update_content_for_item(item)

    def _on_current_item_changed(self, current: QTreeWidgetItem, previous: QTreeWidgetItem):
        if current is None:
            return
        is_placeholder = current.data(0, Qt.ItemDataRole.UserRole + 2)
        if is_placeholder:
            parent = current.parent()
            if parent:
                self.tree.setCurrentItem(parent)
            return
        self._update_content_for_item(current)

    def _get_next_item_after(self, item):
        parent = item.parent()
        if parent:
            index = parent.indexOfChild(item)
            for i in range(index + 1, parent.childCount()):
                sibling = parent.child(i)
                if not sibling.data(0, Qt.ItemDataRole.UserRole + 2):
                    return sibling
            return self._get_next_item_after(parent)
        else:
            index = self.tree.indexOfTopLevelItem(item)
            if index + 1 < self.tree.topLevelItemCount():
                return self.tree.topLevelItem(index + 1)
        return None

    def _apply_disclosure_icons(self):
        self.tree.setStyleSheet(get_disclosure_stylesheet(self._dark_mode))

    def set_dark_mode(self, dark_mode: bool):
        self._dark_mode = dark_mode
        self._apply_disclosure_icons()
        self.tree.update()


class FileTemplatesPanel(QFrame):
    """Bottom center panel: file templates list and editor."""

    insert_reference = pyqtSignal(str)
    template_delete_requested = pyqtSignal(str)
    templates_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("fileTemplatesPanel")
        self.setProperty("class", "panel")

        self._current_template = None
        self._has_unsaved_changes = False
        self._original_content = ""
        self._drafts = {}
        self._editing_new = False
        self._renaming_template = None
        self._refreshing = False
        self._refresh_pending = False
        self._click_timer = QTimer()
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(250)
        self._pending_click_name = None
        self._mouse_click_in_progress = False
        self._mouse_clear_timer = QTimer()
        self._mouse_clear_timer.setSingleShot(True)
        self._mouse_clear_timer.timeout.connect(self._clear_mouse_click_flag)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        header = QLabel("FILE TEMPLATES")
        header.setProperty("class", "panelHeader")
        header.setToolTip("Reusable file content templates with token support")
        main_layout.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter = splitter

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(8)

        self.template_list = QListWidget()
        self.template_list.setMinimumWidth(140)
        self.template_list.itemClicked.connect(self._on_item_clicked)
        self.template_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.template_list.currentItemChanged.connect(self._on_current_item_changed)
        self.template_list.installEventFilter(self)
        self.template_list.viewport().installEventFilter(self)
        self.template_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.template_list.customContextMenuRequested.connect(self._show_context_menu)
        left_layout.addWidget(self.template_list, 1)

        splitter.addWidget(left_widget)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        self.editor = CodeEditor(
            indent_size=4,
            placeholder="Template content\nSupports {mp:Token} syntax...",
        )
        self.editor.textChanged.connect(self._track_unsaved_changes)
        right_layout.addWidget(self.editor, 1)

        ref_layout = QHBoxLayout()
        self.reference_label = QLabel("Reference: template: <name>")
        self.reference_label.setProperty("class", "reference")
        ref_layout.addWidget(self.reference_label)

        ref_layout.addStretch()

        self.insert_btn = QPushButton("Insert File Template")
        self.insert_btn.clicked.connect(self._insert_reference)
        ref_layout.addWidget(self.insert_btn)

        right_layout.addLayout(ref_layout)
        splitter.addWidget(right_widget)

        splitter.setSizes([180, 400])

        main_layout.addWidget(splitter, 1)

        self.refresh_list()

    def _reset_editor_scroll(self):
        self.editor.horizontalScrollBar().setValue(0)
        self.editor.verticalScrollBar().setValue(0)

    def refresh_list(self):
        """Refresh the template list from disk."""
        if self._refreshing:
            self._refresh_pending = True
            return
        self._refreshing = True
        self.template_list.clear()
        template_names = library.list_file_template_names()
        unsaved_names = set(self._drafts.keys())
        if self._has_unsaved_changes and self._current_template:
            unsaved_names.add(self._current_template)

        for name in template_names:
            if name == self._renaming_template:
                item = QListWidgetItem()
                widget = TemplateListItem(
                    name,
                    editable=True,
                    placeholder="filename.ext",
                    delete_square=True,
                )
                widget.name_edited.connect(self._on_rename_confirmed)
                widget.name_canceled.connect(self._on_rename_canceled)
                widget.name_edit.setText(name)
                item.setSizeHint(widget.sizeHint())
                self.template_list.addItem(item)
                self.template_list.setItemWidget(item, widget)
                self.template_list.setCurrentItem(item)
                QTimer.singleShot(50, widget.focus_edit)
            else:
                item = QListWidgetItem()
                widget = TemplateListItem(
                    name,
                    delete_square=True,
                    delete_tooltip="Delete template",
                )
                widget.rename_requested.connect(self._start_rename_template)
                widget.delete_clicked.connect(self._delete_template)
                if name in unsaved_names:
                    widget.set_unsaved(True)
                item.setSizeHint(widget.sizeHint())
                self.template_list.addItem(item)
                self.template_list.setItemWidget(item, widget)

                if name == self._current_template:
                    self.template_list.setCurrentItem(item)

        if self._editing_new:
            item = QListWidgetItem()
            widget = TemplateListItem(
                "",
                editable=True,
                placeholder="filename.ext",
                delete_square=True,
            )
            widget.name_edited.connect(self._on_new_name_confirmed)
            widget.name_canceled.connect(self._on_new_name_canceled)
            item.setSizeHint(widget.sizeHint())
            self.template_list.addItem(item)
            self.template_list.setItemWidget(item, widget)
            self.template_list.setCurrentItem(item)
            QTimer.singleShot(50, widget.focus_edit)

        add_item = QListWidgetItem()
        add_widget = AddTemplateButton()
        add_widget.clicked.connect(self._create_new_template)
        add_item.setSizeHint(QSize(0, add_widget.sizeHint().height()))
        add_item.setFlags(
            add_item.flags()
            & ~Qt.ItemFlag.ItemIsSelectable
            & ~Qt.ItemFlag.ItemIsEnabled
        )
        self.template_list.addItem(add_item)
        self.template_list.setItemWidget(add_item, add_widget)

        self._refreshing = False
        if self._refresh_pending:
            self._refresh_pending = False
            QTimer.singleShot(0, self.refresh_list)

    def has_unsaved_changes(self) -> bool:
        return self._has_unsaved_changes or bool(self._drafts)

    def _stash_current_template(self):
        """Cache unsaved edits for the current file template."""
        if not self._current_template:
            return
        content = self.editor.toPlainText()
        if content != self._original_content:
            self._drafts[self._current_template] = content
        else:
            self._drafts.pop(self._current_template, None)

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj in (self.template_list, self.template_list.viewport()):
            if event.type() == QEvent.Type.MouseButtonPress:
                self._mouse_click_in_progress = True
            elif event.type() in (QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick):
                self._mouse_clear_timer.start(0)
            elif event.type() == QEvent.Type.FocusOut:
                self._finalize_pending_click()
            elif event.type() == QEvent.Type.KeyPress:
                if self._pending_click_name or self._click_timer.isActive():
                    self._finalize_pending_click()
                key = event.key()

                if key == Qt.Key.Key_Down:
                    current_row = self.template_list.currentRow()
                    if current_row >= self.template_list.count() - 2:
                        return True
                elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    current = self.template_list.currentItem()
                    if current:
                        widget = self.template_list.itemWidget(current)
                        if isinstance(widget, TemplateListItem) and not widget._editable:
                            name = widget.get_name()
                            if name:
                                self._renaming_template = name
                                self.refresh_list()
                                return True
        return super().eventFilter(obj, event)

    def _on_current_item_changed(self, current, previous):
        if self._refreshing or current is None:
            return
        if self._mouse_click_in_progress or self._pending_click_name or self._click_timer.isActive():
            return
        widget = self.template_list.itemWidget(current)
        if isinstance(widget, TemplateListItem):
            name = widget.get_name()
            if name and not widget._editable and name != self._current_template:
                self._load_template(name)

    def _clear_mouse_click_flag(self):
        self._mouse_click_in_progress = False

    def _finalize_pending_click(self):
        if self._click_timer.isActive():
            self._click_timer.stop()
        if self._pending_click_name:
            self._load_template(self._pending_click_name)
            self._pending_click_name = None
        self._mouse_click_in_progress = False

    def _show_context_menu(self, pos):
        item = self.template_list.itemAt(pos)
        if item is None:
            return
        widget = self.template_list.itemWidget(item)
        if not isinstance(widget, TemplateListItem) or widget._editable:
            return
        name = widget.get_name()
        if not name:
            return
        content = library.get_file_template(name)
        if content is None:
            return
        self.template_list.setCurrentItem(item)
        menu = QMenu(self)
        rename_action = menu.addAction("Rename")
        duplicate_action = menu.addAction("Duplicate")
        show_action = menu.addAction("Show in Finder")
        menu.addSeparator()
        delete_action = menu.addAction("Delete")
        action = menu.exec(self.template_list.viewport().mapToGlobal(pos))
        if action == rename_action:
            self._start_rename_template(name)
        elif action == duplicate_action:
            self._duplicate_template(name)
        elif action == show_action:
            self._show_in_finder(name)
        elif action == delete_action:
            self._delete_template(name)

    def _start_rename_template(self, name: str):
        self._click_timer.stop()
        self._pending_click_name = None
        self._renaming_template = name
        self.refresh_list()

    def _duplicate_template(self, name: str):
        content = library.get_file_template(name)
        if content is None:
            return
        new_name = self._next_available_template_name(name)
        library.save_file_template(new_name, content)
        self._drafts.pop(new_name, None)
        self._current_template = new_name
        self._original_content = content
        self._has_unsaved_changes = False
        self.editor.blockSignals(True)
        self.editor.setPlainText(content)
        self.editor.blockSignals(False)
        self._reset_editor_scroll()
        self.reference_label.setText(f"Reference: template: {new_name}")
        self.refresh_list()
        self.templates_changed.emit()

    def _show_in_finder(self, name: str):
        path = None
        if name:
            path = library.get_file_template_path(name)
        if not path:
            path = library.get_file_templates_dir()
        if not path.exists():
            QMessageBox.warning(self, "File Not Found", "Could not find file templates.")
            return
        if sys.platform == "darwin":
            if path.is_file():
                subprocess.run(["open", "-R", str(path)])
            else:
                subprocess.run(["open", str(path)])
        else:
            target = path.parent if path.is_file() else path
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def _on_item_clicked(self, item: QListWidgetItem):
        widget = self.template_list.itemWidget(item)
        if isinstance(widget, TemplateListItem):
            name = widget.get_name()
            if name and not widget._editable:
                if name == self._current_template:
                    return
                self._pending_click_name = name
                if self._click_timer.receivers(self._click_timer.timeout) > 0:
                    self._click_timer.timeout.disconnect()
                self._click_timer.timeout.connect(self._process_single_click)
                self._click_timer.start()

    def _process_single_click(self):
        if self._pending_click_name:
            self._load_template(self._pending_click_name)
        self._pending_click_name = None

    def _on_item_double_clicked(self, item: QListWidgetItem):
        self._click_timer.stop()
        self._pending_click_name = None

        widget = self.template_list.itemWidget(item)
        if isinstance(widget, TemplateListItem) and not widget._editable:
            name = widget.get_name()
            if name:
                self._renaming_template = name
                self.refresh_list()

    def _load_template(self, name: str):
        """Load a file template by name."""
        self._stash_current_template()
        content = library.get_file_template(name)
        if content is not None:
            draft = self._drafts.get(name)
            editor_content = draft if draft is not None else content
            self._current_template = name
            self._original_content = content
            self._has_unsaved_changes = editor_content != content
            self.editor.blockSignals(True)
            self.editor.setPlainText(editor_content)
            self.editor.blockSignals(False)
            self._reset_editor_scroll()
            self.reference_label.setText(f"Reference: template: {name}")
            self.refresh_list()

    def _create_new_template(self):
        self._stash_current_template()
        self._current_template = None
        self._has_unsaved_changes = False
        self._original_content = ""
        self._editing_new = True
        self._renaming_template = None
        self.editor.clear()
        self._reset_editor_scroll()
        self.reference_label.setText("Reference: template: <name>")
        self.refresh_list()

    def _on_new_name_confirmed(self, old_name: str, new_name: str):
        name = new_name.strip()
        if name in library.list_file_template_names():
            decision = self._prompt_template_name_conflict(name)
            if decision == "cancel":
                self._editing_new = False
                self.refresh_list()
                self.template_list.setFocus()
                return
            if decision == "keep":
                name = self._next_available_template_name(name)
        self._editing_new = False
        self._current_template = name
        self._save_template()
        self.template_list.setFocus()

    def _on_new_name_canceled(self, old_name: str):
        self._editing_new = False
        self.refresh_list()

    def _on_rename_confirmed(self, old_name: str, new_name: str):
        self._renaming_template = None
        if old_name != new_name and new_name:
            content = library.get_file_template(old_name)
            if content is not None:
                library.delete_file_template(old_name)
                library.save_file_template(new_name, content)
                if self._current_template == old_name:
                    self._current_template = new_name
                self.reference_label.setText(f"Reference: template: {new_name}")
            if old_name in self._drafts:
                self._drafts[new_name] = self._drafts.pop(old_name)
            if self._current_template == new_name:
                self._original_content = content or ""
                self._has_unsaved_changes = self.editor.toPlainText() != self._original_content
        self.refresh_list()
        self.template_list.setFocus()

    def _on_rename_canceled(self, old_name: str):
        self._renaming_template = None
        self.refresh_list()
        self.template_list.setFocus()

    def _next_available_template_name(self, name: str) -> str:
        path = PurePosixPath(name)
        parent = path.parent if path.parent != PurePosixPath(".") else PurePosixPath("")
        stem = path.stem
        suffix = path.suffix
        existing = set(library.list_file_template_names())
        index = 1
        while True:
            candidate_name = f"{stem} ({index}){suffix}"
            if parent != PurePosixPath(""):
                candidate = (parent / candidate_name).as_posix()
            else:
                candidate = candidate_name
            if candidate not in existing:
                return candidate
            index += 1

    def _prompt_template_name_conflict(self, name: str) -> str:
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setWindowTitle("Template Exists")
        dialog.setText(f"\"{name}\" already exists.")
        dialog.setInformativeText("Choose what to do with this template.")
        overwrite_btn = dialog.addButton("Overwrite", QMessageBox.ButtonRole.DestructiveRole)
        keep_btn = dialog.addButton("Keep Both", QMessageBox.ButtonRole.AcceptRole)
        cancel_btn = dialog.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        overwrite_btn.setProperty("class", "dangerButton")
        style_default_dialog_button(keep_btn)
        cancel_btn.setProperty("class", "cancelButton")
        dialog.setDefaultButton(keep_btn)
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked == cancel_btn:
            return "cancel"
        if clicked == keep_btn:
            return "keep"
        return "overwrite"

    def _track_unsaved_changes(self):
        content = self.editor.toPlainText()
        if not content:
            self._reset_editor_scroll()
        self.mark_unsaved_changes(content)

    def _save_template(self):
        """Persist the current file template to disk."""
        if not self._current_template:
            return
        content = self.editor.toPlainText()
        library.save_file_template(self._current_template, content)
        self._original_content = content
        self._has_unsaved_changes = False
        self._drafts.pop(self._current_template, None)
        self.reference_label.setText(f"Reference: template: {self._current_template}")
        self.refresh_list()
        self.templates_changed.emit()

    def save_current_template(self):
        self._save_template()

    def set_current_template_state(self, name: str, saved_content: str, editor_content: str):
        self._current_template = name
        self._original_content = saved_content
        self._has_unsaved_changes = editor_content != saved_content
        self._editing_new = False
        self._renaming_template = None
        self.editor.blockSignals(True)
        self.editor.setPlainText(editor_content)
        self.editor.blockSignals(False)
        self._reset_editor_scroll()
        self.reference_label.setText(f"Reference: template: {name}")
        if editor_content != saved_content:
            self._drafts[name] = editor_content
        else:
            self._drafts.pop(name, None)
        self.refresh_list()

    def clear_current_template_state(self):
        if self._current_template:
            self._drafts.pop(self._current_template, None)
        self._current_template = None
        self._has_unsaved_changes = False
        self._original_content = ""
        self.editor.clear()
        self._reset_editor_scroll()
        self.reference_label.setText("Reference: template: <name>")
        self.refresh_list()

    def clear_all_state(self):
        """Clear all file template state and drafts."""
        self._drafts.clear()
        self._current_template = None
        self._has_unsaved_changes = False
        self._original_content = ""
        self._editing_new = False
        self._renaming_template = None
        self.editor.clear()
        self._reset_editor_scroll()
        self.reference_label.setText("Reference: template: <name>")
        self.refresh_list()

    def mark_unsaved_changes(self, current_content: str):
        """Update unsaved state based on editor content."""
        has_changes = current_content != self._original_content
        if has_changes != self._has_unsaved_changes:
            self._has_unsaved_changes = has_changes
            self.refresh_list()

    def is_current_template(self, name: str) -> bool:
        return self._current_template == name

    def save_all_unsaved(self):
        """Persist all cached file template drafts to disk."""
        changed = False
        if self._current_template and self._has_unsaved_changes:
            self._drafts[self._current_template] = self.editor.toPlainText()
        for name, content in list(self._drafts.items()):
            library.save_file_template(name, content)
            changed = True
            if name == self._current_template:
                self._original_content = content
                self._has_unsaved_changes = False
                self.reference_label.setText(f"Reference: template: {name}")
            self._drafts.pop(name, None)
        self.refresh_list()
        if changed:
            self.templates_changed.emit()

    def _delete_template(self, name: str):
        """Delete a file template with slide animation."""
        for i in range(self.template_list.count()):
            item = self.template_list.item(i)
            widget = self.template_list.itemWidget(item)
            if isinstance(widget, TemplateListItem) and widget.get_name() == name:
                start_pos = widget.pos()
                end_pos = QPoint(-widget.width(), start_pos.y())

                animation = QPropertyAnimation(widget, b"pos")
                animation.setDuration(200)
                animation.setStartValue(start_pos)
                animation.setEndValue(end_pos)
                animation.setEasingCurve(QEasingCurve.Type.InQuad)

                def on_finished():
                    self.template_delete_requested.emit(name)
                    library.delete_file_template(name)
                    self._drafts.pop(name, None)
                    if name == self._current_template:
                        self._current_template = None
                        self._has_unsaved_changes = False
                        self._original_content = ""
                        self.editor.clear()
                        self.reference_label.setText("Reference: template: <name>")
                    self.refresh_list()
                    self.templates_changed.emit()

                animation.finished.connect(on_finished)
                animation.start()
                widget._delete_animation = animation
                return

        self.template_delete_requested.emit(name)
        library.delete_file_template(name)
        self._drafts.pop(name, None)
        if name == self._current_template:
            self._current_template = None
            self._has_unsaved_changes = False
            self._original_content = ""
            self.editor.clear()
            self.reference_label.setText("Reference: template: <name>")
        self.refresh_list()
        self.templates_changed.emit()

    def _insert_reference(self):
        if self._current_template:
            self.insert_reference.emit(self._current_template)


class CustomTokensPanel(QFrame):
    """Custom tokens list and editor panel."""

    tokens_changed = pyqtSignal()
    token_action = pyqtSignal(str, str, object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("customTokensPanel")
        self.setProperty("class", "panel")

        self._current_token = None
        self._has_unsaved_changes = False
        self._original_value = ""
        self._original_type = "text"
        self._drafts = {}
        self._editing_new = False
        self._renaming_token = None
        self._refreshing = False
        self._refresh_pending = False
        self._click_timer = QTimer()
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(250)
        self._pending_click_name = None
        self._mouse_click_in_progress = False
        self._mouse_clear_timer = QTimer()
        self._mouse_clear_timer.setSingleShot(True)
        self._mouse_clear_timer.timeout.connect(self._clear_mouse_click_flag)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._header_label = QLabel("CUSTOM TOKENS")
        self._header_label.setProperty("class", "panelHeader")
        self._header_label.setToolTip("Global tokens available across all projects")
        layout.addWidget(self._header_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter = splitter

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(8)

        self.token_list = QListWidget()
        self.token_list.setMinimumWidth(160)
        self.token_list.itemClicked.connect(self._on_item_clicked)
        self.token_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.token_list.currentItemChanged.connect(self._on_current_item_changed)
        self.token_list.installEventFilter(self)
        self.token_list.viewport().installEventFilter(self)
        self.token_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.token_list.customContextMenuRequested.connect(self._show_context_menu)
        left_layout.addWidget(self.token_list, 1)

        splitter.addWidget(left_widget)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        self.editor = CodeEditor(
            indent_size=4,
            placeholder="Token value",
        )
        self.editor.textChanged.connect(self._track_unsaved_changes)
        right_layout.addWidget(self.editor, 1)

        footer_layout = QHBoxLayout()
        self.reference_label = QLabel("Reference: {mp:<name>}")
        self.reference_label.setProperty("class", "reference")
        footer_layout.addWidget(self.reference_label)
        footer_layout.addStretch()

        toggle_label = QLabel("Python Token")
        toggle_label.setToolTip(
            "Single line = expression, multi-line = block."
        )
        footer_layout.addWidget(toggle_label)

        self.python_toggle = ToggleSwitch(checked=False)
        self.python_toggle.setToolTip(
            "Use Python for this token. Single line = expression, multi-line = block."
        )
        self.python_toggle.toggled.connect(self._on_python_toggled)
        footer_layout.addWidget(self.python_toggle)

        right_layout.addLayout(footer_layout)
        splitter.addWidget(right_widget)

        splitter.setSizes([200, 420])
        layout.addWidget(splitter, 1)

        self._token_count = 0
        self._apply_python_mode(False)
        self.refresh_list()

    def has_tokens(self) -> bool:
        """Return True when the list has real token rows."""
        return self._token_count > 0

    def set_dark_mode(self, dark_mode: bool):
        self.editor.set_dark_mode(dark_mode)

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj in (self.token_list, self.token_list.viewport()):
            if event.type() == QEvent.Type.MouseButtonPress:
                self._mouse_click_in_progress = True
            elif event.type() in (QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick):
                self._mouse_clear_timer.start(0)
            elif event.type() == QEvent.Type.FocusOut:
                self._finalize_pending_click()
            elif event.type() == QEvent.Type.KeyPress:
                if self._pending_click_name or self._click_timer.isActive():
                    self._finalize_pending_click()
                key = event.key()

                if key == Qt.Key.Key_Down:
                    current_row = self.token_list.currentRow()
                    if current_row >= self.token_list.count() - 2:
                        return True
                elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    current = self.token_list.currentItem()
                    if current:
                        widget = self.token_list.itemWidget(current)
                        if isinstance(widget, TemplateListItem) and not widget._editable:
                            name = widget.get_name()
                            if name:
                                self._renaming_token = name
                                self.refresh_list()
                                return True
                elif key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
                    current = self.token_list.currentItem()
                    if current:
                        widget = self.token_list.itemWidget(current)
                        if isinstance(widget, TemplateListItem) and not widget._editable:
                            name = widget.get_name()
                            if name:
                                self._delete_token(name)
                                return True
        return super().eventFilter(obj, event)

    def _current_state(self) -> dict:
        return {
            "type": "python" if self.python_toggle.isChecked() else "text",
            "value": self.editor.toPlainText(),
        }

    def _apply_python_mode(self, is_python: bool):
        self.editor.set_highlighter(PythonHighlighter if is_python else None)
        if is_python:
            self.editor.setPlaceholderText(
                """# Single-line expression:
context["title"].lower().replace(" ", "-")

# Multi-line block (set result or print):
words = context["description"].split()
result = "-".join(words)
                """)
        else:
            self.editor.setPlaceholderText("Token value")

    def _on_python_toggled(self, checked: bool):
        self._apply_python_mode(checked)
        self._track_unsaved_changes()

    def _reset_editor_scroll(self):
        self.editor.horizontalScrollBar().setValue(0)
        self.editor.verticalScrollBar().setValue(0)

    def refresh_list(self):
        if self._refreshing:
            self._refresh_pending = True
            return
        self._refreshing = True
        self.token_list.clear()
        tokens = library.load_custom_tokens()
        token_names = sorted(tokens.keys(), key=lambda name: name.lower())
        self._token_count = len(token_names)
        unsaved_names = set(self._drafts.keys())
        if self._has_unsaved_changes and self._current_token:
            unsaved_names.add(self._current_token)

        for name in token_names:
            if name == self._renaming_token:
                item = QListWidgetItem()
                widget = TemplateListItem(
                    name,
                    editable=True,
                    placeholder="TokenName",
                    delete_square=True,
                )
                widget.name_edited.connect(self._on_rename_confirmed)
                widget.name_canceled.connect(self._on_rename_canceled)
                widget.name_edit.setText(name)
                item.setSizeHint(widget.sizeHint())
                self.token_list.addItem(item)
                self.token_list.setItemWidget(item, widget)
                self.token_list.setCurrentItem(item)
                QTimer.singleShot(50, widget.focus_edit)
            else:
                token_state = None
                if name == self._current_token and self._has_unsaved_changes:
                    token_state = self._current_state()
                if token_state is None:
                    token_state = self._drafts.get(name) or tokens.get(name, {})
                token_type = token_state.get("type", "text")
                badge_text = "py" if token_type == "python" else ""
                item = QListWidgetItem()
                widget = TemplateListItem(
                    name,
                    delete_square=True,
                    delete_tooltip="Delete token",
                    badge_text=badge_text,
                    badge_tooltip="Python token" if badge_text else "",
                )
                widget.rename_requested.connect(self._start_rename_token)
                widget.delete_clicked.connect(self._delete_token)
                if name in unsaved_names:
                    widget.set_unsaved(True)
                item.setSizeHint(widget.sizeHint())
                self.token_list.addItem(item)
                self.token_list.setItemWidget(item, widget)

                if name == self._current_token:
                    self.token_list.setCurrentItem(item)

        if self._editing_new:
            item = QListWidgetItem()
            widget = TemplateListItem(
                "",
                editable=True,
                placeholder="TokenName",
                delete_square=True,
            )
            widget.name_edited.connect(self._on_new_name_confirmed)
            widget.name_canceled.connect(self._on_new_name_canceled)
            item.setSizeHint(widget.sizeHint())
            self.token_list.addItem(item)
            self.token_list.setItemWidget(item, widget)
            self.token_list.setCurrentItem(item)
            QTimer.singleShot(50, widget.focus_edit)

        add_item = QListWidgetItem()
        add_widget = AddTemplateButton()
        add_widget.clicked.connect(self._create_new_token)
        add_item.setSizeHint(QSize(0, add_widget.sizeHint().height()))
        add_item.setFlags(
            add_item.flags()
            & ~Qt.ItemFlag.ItemIsSelectable
            & ~Qt.ItemFlag.ItemIsEnabled
        )
        self.token_list.addItem(add_item)
        self.token_list.setItemWidget(add_item, add_widget)

        self._refreshing = False
        if self._refresh_pending:
            self._refresh_pending = False
            QTimer.singleShot(0, self.refresh_list)

    def _clear_mouse_click_flag(self):
        self._mouse_click_in_progress = False

    def _finalize_pending_click(self):
        if self._click_timer.isActive():
            self._click_timer.stop()
        if self._pending_click_name:
            self._load_token(self._pending_click_name)
            self._pending_click_name = None
        self._mouse_click_in_progress = False

    def _on_current_item_changed(self, current, previous):
        if self._refreshing or current is None:
            return
        if self._mouse_click_in_progress or self._pending_click_name or self._click_timer.isActive():
            return
        widget = self.token_list.itemWidget(current)
        if isinstance(widget, TemplateListItem):
            name = widget.get_name()
            if name and not widget._editable and name != self._current_token:
                self._load_token(name)

    def _on_item_clicked(self, item: QListWidgetItem):
        widget = self.token_list.itemWidget(item)
        if isinstance(widget, TemplateListItem):
            name = widget.get_name()
            if name and not widget._editable:
                if name == self._current_token:
                    return
                self._pending_click_name = name
                if self._click_timer.receivers(self._click_timer.timeout) > 0:
                    self._click_timer.timeout.disconnect()
                self._click_timer.timeout.connect(self._process_single_click)
                self._click_timer.start()

    def _process_single_click(self):
        if self._pending_click_name:
            self._load_token(self._pending_click_name)
        self._pending_click_name = None

    def _on_item_double_clicked(self, item: QListWidgetItem):
        self._click_timer.stop()
        self._pending_click_name = None

        widget = self.token_list.itemWidget(item)
        if isinstance(widget, TemplateListItem) and not widget._editable:
            name = widget.get_name()
            if name:
                self._renaming_token = name
                self.refresh_list()

    def _show_context_menu(self, pos):
        item = self.token_list.itemAt(pos)
        if item is None:
            return
        widget = self.token_list.itemWidget(item)
        if not isinstance(widget, TemplateListItem) or widget._editable:
            return
        name = widget.get_name()
        if not name:
            return
        self.token_list.setCurrentItem(item)
        menu = QMenu(self)
        rename_action = menu.addAction("Rename")
        duplicate_action = menu.addAction("Duplicate")
        menu.addSeparator()
        delete_action = menu.addAction("Delete")
        action = menu.exec(self.token_list.viewport().mapToGlobal(pos))
        if action == rename_action:
            self._start_rename_token(name)
        elif action == duplicate_action:
            self._duplicate_token(name)
        elif action == delete_action:
            self._delete_token(name)

    def _start_rename_token(self, name: str):
        self._click_timer.stop()
        self._pending_click_name = None
        self._renaming_token = name
        self.refresh_list()

    def _duplicate_token(self, name: str):
        tokens = library.load_custom_tokens()
        token = tokens.get(name)
        if not token:
            return
        new_name = self._next_available_token_name(name, set(tokens.keys()))
        library.update_custom_token(new_name, token.get("value", ""), token.get("type", "text"))
        self._drafts.pop(new_name, None)
        self._current_token = new_name
        self._original_value = token.get("value", "")
        self._original_type = token.get("type", "text")
        self._has_unsaved_changes = False
        self._set_editor_state(self._original_type, self._original_value)
        self.reference_label.setText(f"Reference: {{mp:{new_name}}}")
        self.refresh_list()
        self.tokens_changed.emit()
        self.token_action.emit("add", new_name, None, token)

    def _stash_current_token(self):
        if not self._current_token:
            return
        current_state = self._current_state()
        if (
            current_state["value"] != self._original_value
            or current_state["type"] != self._original_type
        ):
            self._drafts[self._current_token] = current_state
        else:
            self._drafts.pop(self._current_token, None)

    def _set_editor_state(self, token_type: str, value: str):
        self.python_toggle.blockSignals(True)
        self.editor.blockSignals(True)
        is_python = token_type == "python"
        self.python_toggle.setChecked(is_python)
        self._apply_python_mode(is_python)
        self.editor.setPlainText(value)
        self.editor.blockSignals(False)
        self.python_toggle.blockSignals(False)
        self._reset_editor_scroll()

    def _load_token(self, name: str):
        self._stash_current_token()
        tokens = library.load_custom_tokens()
        token = tokens.get(name)
        if token is None:
            return
        draft = self._drafts.get(name)
        token_type = token.get("type", "text")
        value = token.get("value", "")
        editor_value = draft["value"] if draft else value
        editor_type = draft["type"] if draft else token_type

        self._current_token = name
        self._original_value = value
        self._original_type = token_type
        self._has_unsaved_changes = (
            editor_value != value or editor_type != token_type
        )
        self._set_editor_state(editor_type, editor_value)
        self.reference_label.setText(f"Reference: {{mp:{name}}}")
        self.refresh_list()

    def _create_new_token(self):
        self._stash_current_token()
        self._current_token = None
        self._has_unsaved_changes = False
        self._original_value = ""
        self._original_type = "text"
        self._editing_new = True
        self._renaming_token = None
        self._set_editor_state("text", "")
        self.reference_label.setText("Reference: {mp:<name>}")
        self.refresh_list()

    def _on_new_name_confirmed(self, old_name: str, new_name: str):
        name = new_name.strip()
        tokens = library.load_custom_tokens()
        if name in tokens:
            decision = self._prompt_token_name_conflict(name)
            if decision == "cancel":
                self._editing_new = False
                self.refresh_list()
                self.token_list.setFocus()
                return
            if decision == "keep":
                name = self._next_available_token_name(name, set(tokens.keys()))
        self._editing_new = False
        self._current_token = name
        self._save_token()
        self.token_list.setFocus()

    def _on_new_name_canceled(self, old_name: str):
        self._editing_new = False
        self.refresh_list()

    def _on_rename_confirmed(self, old_name: str, new_name: str):
        self._renaming_token = None
        name = new_name.strip()
        if old_name != name and name:
            tokens = library.load_custom_tokens()
            if name in tokens:
                decision = self._prompt_token_name_conflict(name)
                if decision == "cancel":
                    self.refresh_list()
                    self.token_list.setFocus()
                    return
                if decision == "keep":
                    name = self._next_available_token_name(name, set(tokens.keys()))
            token_data = tokens.pop(old_name, None)
            if token_data is not None:
                tokens[name] = token_data
                library.save_custom_tokens(tokens)
                if self._current_token == old_name:
                    self._current_token = name
                    self.reference_label.setText(f"Reference: {{mp:{name}}}")
                if old_name in self._drafts:
                    self._drafts[name] = self._drafts.pop(old_name)
                if self._current_token == name:
                    self._original_value = token_data.get("value", "")
                    self._original_type = token_data.get("type", "text")
                    self._has_unsaved_changes = (
                        self._current_state()["value"] != self._original_value
                        or self._current_state()["type"] != self._original_type
                    )
                self.tokens_changed.emit()
        self.refresh_list()
        self.token_list.setFocus()

    def _on_rename_canceled(self, old_name: str):
        self._renaming_token = None
        self.refresh_list()
        self.token_list.setFocus()

    def _next_available_token_name(self, name: str, existing: set[str]) -> str:
        index = 1
        candidate = name
        while candidate in existing:
            candidate = f"{name} ({index})"
            index += 1
        return candidate

    def _prompt_token_name_conflict(self, name: str) -> str:
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setWindowTitle("Token Exists")
        dialog.setText(f"\"{name}\" already exists.")
        dialog.setInformativeText("Choose what to do with this token.")
        overwrite_btn = dialog.addButton("Overwrite", QMessageBox.ButtonRole.DestructiveRole)
        keep_btn = dialog.addButton("Keep Both", QMessageBox.ButtonRole.AcceptRole)
        cancel_btn = dialog.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        overwrite_btn.setProperty("class", "dangerButton")
        style_default_dialog_button(keep_btn)
        cancel_btn.setProperty("class", "cancelButton")
        dialog.setDefaultButton(keep_btn)
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked == cancel_btn:
            return "cancel"
        if clicked == keep_btn:
            return "keep"
        return "overwrite"

    def _track_unsaved_changes(self):
        if not self._current_token:
            return
        content = self.editor.toPlainText()
        if not content:
            self._reset_editor_scroll()
        self.mark_unsaved_changes(self._current_state())

    def mark_unsaved_changes(self, current_state: dict):
        has_changes = (
            current_state["value"] != self._original_value
            or current_state["type"] != self._original_type
        )
        if has_changes != self._has_unsaved_changes:
            self._has_unsaved_changes = has_changes
            self.refresh_list()

    def _save_token(self):
        if not self._current_token:
            return
        current_state = self._current_state()
        tokens = library.load_custom_tokens()
        old_token = tokens.get(self._current_token)
        library.update_custom_token(
            self._current_token,
            current_state["value"],
            current_state["type"],
        )
        new_token = {
            "type": current_state["type"],
            "value": current_state["value"],
        }
        self._original_value = current_state["value"]
        self._original_type = current_state["type"]
        self._has_unsaved_changes = False
        self._drafts.pop(self._current_token, None)
        self.reference_label.setText(f"Reference: {{mp:{self._current_token}}}")
        self.refresh_list()
        if old_token != new_token:
            action = "add" if old_token is None else "update"
            self.tokens_changed.emit()
            self.token_action.emit(action, self._current_token, old_token, new_token)

    def save_current_token(self):
        self._save_token()

    def save_all_unsaved(self):
        if self._current_token and self._has_unsaved_changes:
            self._drafts[self._current_token] = self._current_state()
        if not self._drafts:
            return
        tokens = library.load_custom_tokens()
        changed = False
        for name, state in list(self._drafts.items()):
            old_token = tokens.get(name)
            tokens[name] = {
                "type": state.get("type", "text"),
                "value": state.get("value", ""),
            }
            if old_token != tokens[name]:
                changed = True
            if name == self._current_token:
                self._original_value = state.get("value", "")
                self._original_type = state.get("type", "text")
                self._has_unsaved_changes = False
            self._drafts.pop(name, None)
        if changed:
            library.save_custom_tokens(tokens)
            self.tokens_changed.emit()
        self.refresh_list()

    def has_unsaved_changes(self) -> bool:
        return self._has_unsaved_changes or bool(self._drafts)

    def clear_all_state(self):
        self._drafts.clear()
        self._current_token = None
        self._has_unsaved_changes = False
        self._original_value = ""
        self._original_type = "text"
        self._editing_new = False
        self._renaming_token = None
        self._set_editor_state("text", "")
        self.reference_label.setText("Reference: {mp:<name>}")
        self.refresh_list()

    def _delete_token(self, name: str):
        tokens = library.load_custom_tokens()
        token = tokens.get(name)
        if token is None:
            return
        library.delete_custom_token(name)
        self._drafts.pop(name, None)
        if name == self._current_token:
            self._current_token = None
            self._has_unsaved_changes = False
            self._original_value = ""
            self._original_type = "text"
            self._set_editor_state("text", "")
            self.reference_label.setText("Reference: {mp:<name>}")
        self.refresh_list()
        self.tokens_changed.emit()
        self.token_action.emit("delete", name, token, None)

    def select_first_token(self):
        for i in range(self.token_list.count()):
            item = self.token_list.item(i)
            widget = self.token_list.itemWidget(item)
            if isinstance(widget, TemplateListItem) and not widget._editable:
                self.token_list.setCurrentItem(item)
                return


class SegmentedControl(QFrame):
    """Segmented control for switching bottom panels."""

    index_changed = pyqtSignal(int)

    def __init__(self, labels: list, parent=None):
        super().__init__(parent)
        self.setObjectName("segmentedControl")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        self.buttons = []
        for i, label in enumerate(labels):
            btn = QPushButton(label)
            btn.setProperty("class", "segmentButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, idx=i: self._on_button_clicked(idx))
            layout.addWidget(btn)
            self.buttons.append(btn)

        if self.buttons:
            self.buttons[0].setChecked(True)

    def _on_button_clicked(self, index: int):
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == index)
        self.index_changed.emit(index)
