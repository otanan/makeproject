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
    QDialog, QFrame, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QTextEdit, QTreeWidget,
    QTreeWidgetItem, QMessageBox, QMenu, QSplitter, QSizePolicy
)

from ..styles import get_code_font
from .. import library
from ..highlighter import PythonHighlighter
from ..widgets import ToggleSwitch
from ..template_engine import parse_template_metadata
from .editors import CodeEditor
from .dialog_utils import style_default_dialog_button
from .delete_confirmation_dialog import DeleteConfirmationDialog, DeleteFolderConfirmationDialog
from .template_items import TemplateListItem, AddTemplateButton, FolderListItem


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


# Data roles for template tree items
ROLE_ITEM_TYPE = Qt.ItemDataRole.UserRole  # "template", "folder", or "add_button"
ROLE_ITEM_PATH = Qt.ItemDataRole.UserRole + 1  # Full path (e.g., "folder/template")
ROLE_FOLDER_EXPANDED = Qt.ItemDataRole.UserRole + 2  # Folder expanded state


class ProjectTemplatesPanel(QFrame):
    """Left panel: list of project templates with create/rename/delete and folder support."""

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
        self._new_template_folder = None  # Folder to create new template in
        self._renaming_template = None
        self._renaming_folder = None
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
        
        # Folder expansion states
        self._folder_expanded = {}
        
        # Drag and drop state
        self._drag_start_pos = None
        self._drag_source_name = None
        self._drop_indicator_index = -1
        self._drop_target_folder = None
        self._drag_hover_item = None  # Currently highlighted drop target

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QLabel("PROJECT TEMPLATES")
        header.setProperty("class", "panelHeader")
        header.setToolTip("Saved project template configurations")
        layout.addWidget(header)

        self.template_list = QListWidget()
        self.template_list.setSpacing(0)
        self.template_list.setViewportMargins(0, 0, 0, 0)
        self.template_list.itemClicked.connect(self._on_item_clicked)
        self.template_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.template_list.currentItemChanged.connect(self._on_current_item_changed)
        self.template_list.installEventFilter(self)
        self.template_list.viewport().installEventFilter(self)
        self.template_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.template_list.customContextMenuRequested.connect(self._show_context_menu)
        
        # Enable drag and drop (use DragDrop mode, not InternalMove, to prevent Qt's auto-reordering)
        self.template_list.setDragEnabled(True)
        self.template_list.setAcceptDrops(True)
        self.template_list.setDragDropMode(QListWidget.DragDropMode.DragDrop)
        self.template_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.template_list.viewport().setAcceptDrops(True)
        
        layout.addWidget(self.template_list)

        self.refresh_list()

    def _get_folder_display_name(self, folder: str) -> str:
        """Get display name for a folder (last component of path)."""
        return Path(folder).name

    def _get_template_display_name(self, name: str) -> str:
        """Get display name for a template (last component without folder)."""
        return Path(name).name

    def _get_template_folder(self, name: str) -> str | None:
        """Get the folder a template is in, or None if at root."""
        path = Path(name)
        if len(path.parts) > 1:
            return path.parts[0]
        return None

    def refresh_list(self):
        """Refresh the template list from disk with folder support."""
        if self._refreshing:
            self._refresh_pending = True
            return
        self._refreshing = True
        if self._editing_new:
            self._capture_new_template_name()
        self.template_list.clear()
        
        templates = library.list_project_templates()
        folders = library.list_project_template_folders()
        unsaved_names = set(self._draft_store.keys())
        if self._has_unsaved_changes and self._current_template:
            unsaved_names.add(self._current_template)

        # Track which templates are in folders
        templates_in_folders = set()
        for folder in folders:
            for t in templates:
                if t.startswith(f"{folder}/"):
                    templates_in_folders.add(t)

        # Add folders first
        for folder in folders:
            if folder == self._renaming_folder:
                item = QListWidgetItem()
                widget = FolderListItem(
                    folder,
                    editable=True,
                    placeholder="Folder name...",
                    expanded=self._folder_expanded.get(folder, True),
                )
                widget.name_edited.connect(self._on_folder_rename_confirmed)
                widget.name_canceled.connect(self._on_folder_rename_canceled)
                widget.name_edit.setText(folder)
                item.setData(ROLE_ITEM_TYPE, "folder")
                item.setData(ROLE_ITEM_PATH, folder)
                item.setSizeHint(widget.sizeHint())
                self.template_list.addItem(item)
                self.template_list.setItemWidget(item, widget)
                QTimer.singleShot(50, widget.focus_edit)
            else:
                expanded = self._folder_expanded.get(folder, True)
                item = QListWidgetItem()
                widget = FolderListItem(
                    folder,
                    expanded=expanded,
                )
                widget.rename_requested.connect(self._start_rename_folder)
                widget.delete_clicked.connect(self._delete_folder)
                widget.toggled.connect(self._on_folder_toggled)
                item.setData(ROLE_ITEM_TYPE, "folder")
                item.setData(ROLE_ITEM_PATH, folder)
                item.setSizeHint(widget.sizeHint())
                self.template_list.addItem(item)
                self.template_list.setItemWidget(item, widget)

            # Add templates inside folder if expanded
            if self._folder_expanded.get(folder, True):
                folder_templates = [t for t in templates if t.startswith(f"{folder}/")]
                for name in folder_templates:
                    self._add_template_item(name, unsaved_names, indent=True)
                
                # Add new template input inside this folder if creating here
                if self._editing_new and self._new_template_folder == folder:
                    item = QListWidgetItem()
                    widget = TemplateListItem(
                        "",
                        editable=True,
                        placeholder="Template name...",
                        auto_confirm_on_focus_out=False,
                    )
                    widget.name_edited.connect(self._on_new_name_confirmed)
                    widget.name_canceled.connect(self._on_new_name_canceled)
                    if self._draft_name_seed:
                        widget.name_edit.setText(self._draft_name_seed)
                    item.setData(ROLE_ITEM_TYPE, "template")
                    item.setData(ROLE_ITEM_PATH, "")
                    item.setSizeHint(widget.sizeHint())
                    # Add indentation for folder context
                    layout = widget.layout()
                    if layout:
                        margins = layout.contentsMargins()
                        layout.setContentsMargins(margins.left() + 20, margins.top(), margins.right(), margins.bottom())
                    self.template_list.addItem(item)
                    self.template_list.setItemWidget(item, widget)
                    self.template_list.setCurrentItem(item)
                    QTimer.singleShot(50, widget.focus_edit)

        # Add templates at root level (not in any folder)
        for name in templates:
            if name not in templates_in_folders:
                self._add_template_item(name, unsaved_names, indent=False)

        # Handle editing new template (only at root level)
        if self._editing_new and not self._new_template_folder:
            item = QListWidgetItem()
            widget = TemplateListItem(
                "",
                editable=True,
                placeholder="Template name...",
                auto_confirm_on_focus_out=False,
            )
            widget.name_edited.connect(self._on_new_name_confirmed)
            widget.name_canceled.connect(self._on_new_name_canceled)
            if self._draft_name_seed:
                widget.name_edit.setText(self._draft_name_seed)
            item.setData(ROLE_ITEM_TYPE, "template")
            item.setData(ROLE_ITEM_PATH, "")
            item.setSizeHint(widget.sizeHint())
            self.template_list.addItem(item)
            self.template_list.setItemWidget(item, widget)
            self.template_list.setCurrentItem(item)
            QTimer.singleShot(50, widget.focus_edit)
        elif self._current_template is None and self._has_unsaved_changes:
            item = QListWidgetItem()
            widget = TemplateListItem(
                "untitled project",
                auto_confirm_on_focus_out=False,
            )
            widget.set_unsaved(True)
            widget.rename_requested.connect(self._start_draft_naming)
            item.setData(ROLE_ITEM_TYPE, "template")
            item.setData(ROLE_ITEM_PATH, "untitled project")
            item.setSizeHint(widget.sizeHint())
            self.template_list.addItem(item)
            self.template_list.setItemWidget(item, widget)
            self.template_list.setCurrentItem(item)

        add_item = QListWidgetItem()
        add_widget = AddTemplateButton()
        add_widget.clicked.connect(self._create_new_template)
        add_widget.folder_clicked.connect(self._create_new_folder)
        add_item.setData(ROLE_ITEM_TYPE, "add_button")
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

    def _create_new_folder(self):
        """Create a new folder and show rename input."""
        folder_name = self._generate_unique_folder_name("New Folder")
        library.create_project_template_folder(folder_name)
        self._folder_expanded[folder_name] = True
        self._renaming_folder = folder_name
        self.refresh_list()
        self._select_item_by_path(folder_name)
        self.template_list.setFocus()

    def _add_template_item(self, name: str, unsaved_names: set, indent: bool = False):
        """Add a template item to the list."""
        display_name = self._get_template_display_name(name)
        
        if name == self._renaming_template:
            item = QListWidgetItem()
            widget = TemplateListItem(
                display_name,
                editable=True,
                placeholder="Template name...",
            )
            widget.name_edited.connect(
                lambda old, new, n=name: self._on_rename_confirmed(n, new)
            )
            widget.name_canceled.connect(lambda old: self._on_rename_canceled(name))
            widget.name_edit.setText(display_name)
            if indent:
                widget.setContentsMargins(20, 0, 0, 0)
            item.setData(ROLE_ITEM_TYPE, "template")
            item.setData(ROLE_ITEM_PATH, name)
            item.setSizeHint(widget.sizeHint())
            self.template_list.addItem(item)
            self.template_list.setItemWidget(item, widget)
            self.template_list.setCurrentItem(item)
            QTimer.singleShot(50, widget.focus_edit)
        else:
            item = QListWidgetItem()
            widget = TemplateListItem(
                display_name,
            )
            tooltip = self._get_template_tooltip(name)
            if tooltip:
                widget.setToolTip(tooltip)
            widget.rename_requested.connect(lambda n=name: self._start_rename_template(n))
            widget.delete_clicked.connect(lambda n=name: self._delete_template(n))
            if name in unsaved_names:
                widget.set_unsaved(True)
            if indent:
                # Add left margin for indentation
                layout = widget.layout()
                if layout:
                    margins = layout.contentsMargins()
                    layout.setContentsMargins(20, margins.top(), margins.right(), margins.bottom())
            item.setData(ROLE_ITEM_TYPE, "template")
            item.setData(ROLE_ITEM_PATH, name)
            item.setSizeHint(widget.sizeHint())
            self.template_list.addItem(item)
            self.template_list.setItemWidget(item, widget)

            if name == self._current_template:
                self.template_list.setCurrentItem(item)

    def _on_folder_toggled(self, folder: str, expanded: bool):
        """Handle folder expand/collapse."""
        self._folder_expanded[folder] = expanded
        self.refresh_list()
        self._select_item_by_path(folder)

    def _select_item_by_path(self, path: str):
        """Select an item in the list by its path."""
        for i in range(self.template_list.count()):
            item = self.template_list.item(i)
            if item and item.data(ROLE_ITEM_PATH) == path:
                self.template_list.setCurrentItem(item)
                return

    def _start_rename_folder(self, folder: str):
        """Start renaming a folder."""
        self._renaming_folder = folder
        self.refresh_list()

    def _on_folder_rename_confirmed(self, old_name: str, new_name: str):
        """Handle folder rename confirmation."""
        self._renaming_folder = None
        if old_name != new_name and new_name:
            if library.rename_project_template_folder(old_name, new_name):
                # Update expansion state
                if old_name in self._folder_expanded:
                    self._folder_expanded[new_name] = self._folder_expanded.pop(old_name)
                # Update current template path if it was in this folder
                if self._current_template and self._current_template.startswith(f"{old_name}/"):
                    new_template = new_name + self._current_template[len(old_name):]
                    self._current_template = new_template
        self.refresh_list()

    def _on_folder_rename_canceled(self, old_name: str):
        """Handle folder rename cancellation."""
        self._renaming_folder = None
        self.refresh_list()

    def _delete_folder(self, folder: str):
        """Delete a folder and all its contents."""
        templates_in_folder = library.get_project_templates_in_folder(folder)
        dialog = DeleteFolderConfirmationDialog(
            folder, len(templates_in_folder), parent=self
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        
        library.delete_project_template_folder(folder)
        self._folder_expanded.pop(folder, None)
        
        # Clear current template if it was in the deleted folder
        if self._current_template and self._current_template.startswith(f"{folder}/"):
            self._current_template = None
            self._has_unsaved_changes = False
            self._original_content = ""
            self.clear_requested.emit()
        
        self.refresh_list()

    def _generate_unique_folder_name(self, base_name: str) -> str:
        """Generate a unique folder name."""
        existing = set(library.list_project_template_folders())
        if base_name not in existing:
            return base_name
        index = 1
        while True:
            candidate = f"{base_name} ({index})"
            if candidate not in existing:
                return candidate
            index += 1

    def _get_template_tooltip(self, name: str) -> str | None:
        content = library.load_project_template(name)
        if not content:
            return None
        metadata = parse_template_metadata(content)
        if metadata and metadata.description:
            return metadata.description
        lines = content.splitlines()
        if not lines:
            return None
        first_line = lines[0].strip()
        if not first_line.startswith("#") or first_line.lstrip().startswith("# ---"):
            return None
        return first_line.lstrip("#").strip() or None

    def eventFilter(self, obj, event):
        """Handle keyboard and drag-drop events for template list."""
        from PyQt6.QtCore import QEvent, QMimeData
        from PyQt6.QtGui import QDrag
        
        if obj in (self.template_list, self.template_list.viewport()):
            if event.type() == QEvent.Type.MouseButtonPress:
                self._mouse_click_in_progress = True
                if event.button() == Qt.MouseButton.LeftButton:
                    self._drag_start_pos = event.position().toPoint()
                    item = self.template_list.itemAt(self._drag_start_pos)
                    if item:
                        item_type = item.data(ROLE_ITEM_TYPE)
                        if item_type == "template":
                            self._drag_source_name = item.data(ROLE_ITEM_PATH)
                        else:
                            self._drag_source_name = None
                    else:
                        self._drag_source_name = None
                        
            elif event.type() == QEvent.Type.MouseMove:
                if (self._drag_start_pos is not None 
                    and self._drag_source_name is not None
                    and event.buttons() & Qt.MouseButton.LeftButton):
                    distance = (event.position().toPoint() - self._drag_start_pos).manhattanLength()
                    if distance >= 10:  # Drag threshold
                        self._start_drag()
                        return True
                        
            elif event.type() == QEvent.Type.MouseButtonRelease:
                self._drag_start_pos = None
                self._drag_source_name = None
                self._mouse_clear_timer.start(0)
                
            elif event.type() == QEvent.Type.DragEnter:
                if event.mimeData().hasFormat("application/x-makeproject-template"):
                    event.acceptProposedAction()
                    return True
                    
            elif event.type() == QEvent.Type.DragMove:
                if event.mimeData().hasFormat("application/x-makeproject-template"):
                    drop_pos = event.position().toPoint()
                    target_item = self.template_list.itemAt(drop_pos)
                    self._update_drag_hover(target_item)
                    event.acceptProposedAction()
                    return True
                    
            elif event.type() == QEvent.Type.Drop:
                if event.mimeData().hasFormat("application/x-makeproject-template"):
                    self._clear_drag_hover()
                    self._handle_drop(event)
                    return True
                    
            elif event.type() == QEvent.Type.DragLeave:
                self._clear_drag_hover()
                
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
                elif key == Qt.Key.Key_Left:
                    # Collapse folder when pressing left arrow
                    current = self.template_list.currentItem()
                    if current:
                        item_type = current.data(ROLE_ITEM_TYPE)
                        if item_type == "folder":
                            folder = current.data(ROLE_ITEM_PATH)
                            if folder and self._folder_expanded.get(folder, True):
                                self._folder_expanded[folder] = False
                                self.refresh_list()
                                self._select_item_by_path(folder)
                                return True
                elif key == Qt.Key.Key_Right:
                    # Expand folder when pressing right arrow
                    current = self.template_list.currentItem()
                    if current:
                        item_type = current.data(ROLE_ITEM_TYPE)
                        if item_type == "folder":
                            folder = current.data(ROLE_ITEM_PATH)
                            if folder and not self._folder_expanded.get(folder, True):
                                self._folder_expanded[folder] = True
                                self.refresh_list()
                                self._select_item_by_path(folder)
                                return True
                elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    current = self.template_list.currentItem()
                    if current:
                        item_type = current.data(ROLE_ITEM_TYPE)
                        widget = self.template_list.itemWidget(current)
                        if item_type == "template" and isinstance(widget, TemplateListItem) and not widget._editable:
                            path = current.data(ROLE_ITEM_PATH)
                            if path:
                                if path == "untitled project" and self._current_template is None and self._has_unsaved_changes:
                                    self._start_draft_naming(path)
                                else:
                                    self._renaming_template = path
                                    self.refresh_list()
                                return True
                        elif item_type == "folder" and isinstance(widget, FolderListItem) and not widget._editable:
                            folder = current.data(ROLE_ITEM_PATH)
                            if folder:
                                self._start_rename_folder(folder)
                                return True
        return super().eventFilter(obj, event)

    def _start_drag(self):
        """Initiate a drag operation for a template."""
        from PyQt6.QtCore import QMimeData
        from PyQt6.QtGui import QDrag, QPixmap, QPainter, QFont
        
        if not self._drag_source_name:
            return
            
        drag = QDrag(self.template_list)
        mime_data = QMimeData()
        mime_data.setData("application/x-makeproject-template", self._drag_source_name.encode())
        drag.setMimeData(mime_data)
        
        # Create visual drag feedback
        display_name = self._get_template_display_name(self._drag_source_name)
        font = self.template_list.font()
        metrics = self.template_list.fontMetrics()
        text_width = metrics.horizontalAdvance(display_name) + 24
        text_height = metrics.height() + 12
        
        pixmap = QPixmap(text_width, text_height)
        pixmap.fill(QColor(26, 188, 157, 200))  # Teal with transparency
        
        painter = QPainter(pixmap)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, display_name)
        painter.end()
        
        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(text_width // 2, text_height // 2))
        
        # Execute drag
        drag.exec(Qt.DropAction.MoveAction)
        
        self._drag_start_pos = None
        self._drag_source_name = None

    def _handle_drop(self, event):
        """Handle a drop event for folder creation or moving."""
        source_name = event.mimeData().data("application/x-makeproject-template").data().decode()
        drop_pos = event.position().toPoint()
        target_item = self.template_list.itemAt(drop_pos)
        
        if target_item is None:
            # Refresh to reset any Qt-internal reordering
            self.refresh_list()
            return
            
        target_type = target_item.data(ROLE_ITEM_TYPE)
        target_path = target_item.data(ROLE_ITEM_PATH)
        
        # Ignore drops on add_button - it should have no effect
        if target_type == "add_button":
            self.refresh_list()
            return
        
        if target_type == "folder":
            # Drop onto folder - move template into folder
            source_folder = self._get_template_folder(source_name)
            if source_folder == target_path:
                # Already in this folder
                self.refresh_list()
                return
            new_name = library.move_project_template_to_folder(source_name, target_path)
            if new_name:
                if self._current_template == source_name:
                    self._current_template = new_name
                    self.template_renamed.emit(source_name, new_name)
            self.refresh_list()
                
        elif target_type == "template":
            # Drop onto template - create new folder containing both OR move out of folder
            if source_name == target_path:
                self.refresh_list()
                return
            source_folder = self._get_template_folder(source_name)
            target_folder = self._get_template_folder(target_path)
            
            # If both templates are in the same folder (or both at root), create a new subfolder
            if source_folder == target_folder:
                # First, create folder with temporary name and move templates
                temp_folder = self._generate_unique_folder_name("New Folder")
                library.create_project_template_folder(temp_folder)
                self._folder_expanded[temp_folder] = True
                
                # Move both templates into the folder
                for template_name in [source_name, target_path]:
                    new_name = library.move_project_template_to_folder(template_name, temp_folder)
                    if new_name and self._current_template == template_name:
                        self._current_template = new_name
                        self.template_renamed.emit(template_name, new_name)
                
                # Now show rename input for the folder
                self._renaming_folder = temp_folder
                self.refresh_list()
                self._select_item_by_path(temp_folder)
                self.template_list.setFocus()
            else:
                # Move source to target's folder (or root if target has no folder)
                if target_folder:
                    new_name = library.move_project_template_to_folder(source_name, target_folder)
                else:
                    new_name = library.move_project_template_out_of_folder(source_name)
                if new_name:
                    if self._current_template == source_name:
                        self._current_template = new_name
                        self.template_renamed.emit(source_name, new_name)
                self.refresh_list()

    def _update_drag_hover(self, target_item):
        """Update the visual highlight for the current drag hover target."""
        if target_item == self._drag_hover_item:
            return
        
        # Clear previous highlights
        self._clear_drag_hover()
        
        if target_item is None:
            return
            
        # Don't highlight the source item being dragged
        target_path = target_item.data(ROLE_ITEM_PATH)
        if target_path == self._drag_source_name:
            return
            
        target_type = target_item.data(ROLE_ITEM_TYPE)
        
        # Don't highlight the add button
        if target_type == "add_button":
            return
        
        # Check if source is in a folder
        source_folder = self._get_template_folder(self._drag_source_name) if self._drag_source_name else None
        target_folder = None
        if target_type == "template":
            target_folder = self._get_template_folder(target_path)
        elif target_type == "folder":
            # Hovering over a folder means we'd move INTO it, not to root
            target_folder = target_path
        
        # If dragging from a folder to ROOT level, highlight all ROOT-LEVEL items
        # (templates not in any folder, plus folder headers - but not items inside other folders)
        if source_folder and target_folder is None:
            self._drag_hover_items = []
            for i in range(self.template_list.count()):
                item = self.template_list.item(i)
                item_type = item.data(ROLE_ITEM_TYPE)
                item_path = item.data(ROLE_ITEM_PATH)
                
                # Skip the source item and add button
                if item_path == self._drag_source_name or item_type == "add_button":
                    continue
                
                # Only highlight root-level items
                if item_type == "folder":
                    # Folder headers are at root level (but skip source's folder)
                    if item_path != source_folder:
                        widget = self.template_list.itemWidget(item)
                        if widget:
                            widget.setStyleSheet("background-color: rgba(26, 188, 157, 0.3); border-radius: 4px;")
                            self._drag_hover_items.append(item)
                elif item_type == "template":
                    # Only templates at root (not in any folder)
                    item_folder = self._get_template_folder(item_path)
                    if item_folder is None:
                        widget = self.template_list.itemWidget(item)
                        if widget:
                            widget.setStyleSheet("background-color: rgba(26, 188, 157, 0.3); border-radius: 4px;")
                            self._drag_hover_items.append(item)
        else:
            # Normal single-item highlight
            self._drag_hover_item = target_item
            widget = self.template_list.itemWidget(target_item)
            if widget:
                widget.setStyleSheet("background-color: rgba(26, 188, 157, 0.3); border-radius: 4px;")

    def _clear_drag_hover(self):
        """Clear the visual highlight from all drag hover targets."""
        # Clear single hover item
        if self._drag_hover_item is not None:
            widget = self.template_list.itemWidget(self._drag_hover_item)
            if widget:
                widget.setStyleSheet("")
            self._drag_hover_item = None
        
        # Clear multiple hover items (for "remove from folder" hint)
        if hasattr(self, '_drag_hover_items') and self._drag_hover_items:
            for item in self._drag_hover_items:
                widget = self.template_list.itemWidget(item)
                if widget:
                    widget.setStyleSheet("")
            self._drag_hover_items = []

    def _on_current_item_changed(self, current, previous):
        if self._refreshing or current is None:
            return
        if self._editing_new:
            return
        if self._mouse_click_in_progress or self._pending_click_name or self._click_timer.isActive():
            return
        
        item_type = current.data(ROLE_ITEM_TYPE)
        if item_type != "template":
            return
            
        path = current.data(ROLE_ITEM_PATH)
        widget = self.template_list.itemWidget(current)
        if isinstance(widget, TemplateListItem):
            if path and path != "untitled project" and not widget._editable and path != self._current_template:
                self.template_selected.emit(path)

    def _clear_mouse_click_flag(self):
        self._mouse_click_in_progress = False

    def _finalize_pending_click(self):
        if self._click_timer.isActive():
            self._click_timer.stop()
        if self._pending_click_name:
            if self._editing_new:
                self._pending_click_name = None
                self._mouse_click_in_progress = False
                return
            self.template_selected.emit(self._pending_click_name)
            self._pending_click_name = None
        self._mouse_click_in_progress = False

    def _show_context_menu(self, pos):
        item = self.template_list.itemAt(pos)
        if item is None:
            return
        
        item_type = item.data(ROLE_ITEM_TYPE)
        item_path = item.data(ROLE_ITEM_PATH)
        widget = self.template_list.itemWidget(item)
        
        if item_type == "folder":
            if not isinstance(widget, FolderListItem) or widget._editable:
                return
            self.template_list.setCurrentItem(item)
            menu = QMenu(self)
            new_template_action = menu.addAction("New Template")
            menu.addSeparator()
            rename_action = menu.addAction("Rename")
            show_action = menu.addAction("Show in Finder")
            menu.addSeparator()
            delete_action = menu.addAction("Delete")
            action = menu.exec(self.template_list.viewport().mapToGlobal(pos))
            if action == new_template_action:
                self._create_new_template(folder=item_path)
            elif action == rename_action:
                self._start_rename_folder(item_path)
            elif action == show_action:
                folder_path = library.get_project_templates_dir() / item_path
                if folder_path.exists():
                    if sys.platform == "darwin":
                        subprocess.run(["open", "-R", str(folder_path)])
                    else:
                        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder_path)))
            elif action == delete_action:
                self._delete_folder(item_path)
            return
            
        if item_type != "template":
            return
        if not isinstance(widget, TemplateListItem) or widget._editable:
            return
        if not item_path:
            return
        content = library.load_project_template(item_path)
        if content is None:
            return
        self.template_list.setCurrentItem(item)
        menu = QMenu(self)
        rename_action = menu.addAction("Rename")
        duplicate_action = menu.addAction("Duplicate")
        
        # Add move options
        folder = self._get_template_folder(item_path)
        folders = library.list_project_template_folders()
        if folder or folders:
            move_menu = menu.addMenu("Move to")
            if folder:
                move_root_action = move_menu.addAction("Root")
            else:
                move_root_action = None
            for f in folders:
                if f != folder:
                    move_menu.addAction(f)
        else:
            move_menu = None
            move_root_action = None
        
        show_action = menu.addAction("Show in Finder")
        menu.addSeparator()
        delete_action = menu.addAction("Delete")
        action = menu.exec(self.template_list.viewport().mapToGlobal(pos))
        if action == rename_action:
            self._start_rename_template(item_path)
        elif action == duplicate_action:
            self._duplicate_template(item_path)
        elif action == show_action:
            self.show_in_finder_requested.emit(item_path)
        elif action == delete_action:
            self._delete_template(item_path)
        elif move_menu and action:
            if action == move_root_action:
                new_name = library.move_project_template_out_of_folder(item_path)
                if new_name:
                    if self._current_template == item_path:
                        self._current_template = new_name
                        self.template_renamed.emit(item_path, new_name)
                    self.refresh_list()
            elif action.text() in folders:
                new_name = library.move_project_template_to_folder(item_path, action.text())
                if new_name:
                    if self._current_template == item_path:
                        self._current_template = new_name
                        self.template_renamed.emit(item_path, new_name)
                    self.refresh_list()

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
        item_type = item.data(ROLE_ITEM_TYPE)
        item_path = item.data(ROLE_ITEM_PATH)
        widget = self.template_list.itemWidget(item)
        
        if item_type == "template" and isinstance(widget, TemplateListItem):
            if item_path and item_path != "untitled project" and not widget._editable:
                if self._editing_new:
                    return
                if item_path == self._current_template:
                    return
                self._pending_click_name = item_path
                if self._click_timer.receivers(self._click_timer.timeout) > 0:
                    self._click_timer.timeout.disconnect()
                self._click_timer.timeout.connect(self._process_single_click)
                self._click_timer.start()

    def _process_single_click(self):
        if self._pending_click_name:
            if self._editing_new:
                self._pending_click_name = None
                return
            self.template_selected.emit(self._pending_click_name)
        self._pending_click_name = None

    def _on_item_double_clicked(self, item: QListWidgetItem):
        self._click_timer.stop()
        self._pending_click_name = None

        item_type = item.data(ROLE_ITEM_TYPE)
        item_path = item.data(ROLE_ITEM_PATH)
        widget = self.template_list.itemWidget(item)
        
        if item_type == "folder" and isinstance(widget, FolderListItem) and not widget._editable:
            if item_path:
                self._start_rename_folder(item_path)
        elif item_type == "template" and isinstance(widget, TemplateListItem) and not widget._editable:
            if item_path:
                if item_path == "untitled project" and self._current_template is None and self._has_unsaved_changes:
                    self._start_draft_naming(item_path)
                else:
                    self._renaming_template = item_path
                    self.refresh_list()

    def _create_new_template(self, folder: str = None):
        """Start creating a new template with inline name editing."""
        self._current_template = None
        self._has_unsaved_changes = False
        self._original_content = ""
        self._editing_new = True
        self._new_template_folder = folder
        self._renaming_template = None
        self._draft_name_seed = ""
        # Expand the folder if creating inside one
        if folder:
            self._folder_expanded[folder] = True
        self.new_template_requested.emit()
        self.refresh_list()

    def _on_new_name_confirmed(self, old_name: str, new_name: str):
        if self._refreshing:
            return
        """Finalize a new template name entry."""
        self._draft_name_seed = ""
        name = new_name.strip()
        
        # Prepend folder path if creating in a folder
        if self._new_template_folder:
            name = f"{self._new_template_folder}/{name}"
        
        if name == "untitled project":
            name = self.get_unique_template_name(name)
        elif name in library.list_project_templates():
            decision = self._prompt_template_name_conflict(name)
            if decision == "cancel":
                self._editing_new = False
                self._new_template_folder = None
                self.refresh_list()
                return
            if decision == "keep":
                name = self._next_available_template_name(name)
        self._editing_new = False
        self._new_template_folder = None
        self._current_template = name
        self.save_requested.emit()

    def _on_new_name_canceled(self, old_name: str):
        if self._refreshing:
            return
        if self._editing_new and not self._draft_name_seed:
            pending_name = self.get_template_name().strip()
            if not pending_name:
                self._draft_name_seed = ""
                self._on_new_name_confirmed(old_name, "untitled project")
                return
        self._draft_name_seed = ""
        self._editing_new = False
        self._new_template_folder = None
        self.refresh_list()

    def _start_draft_naming(self, name: str):
        """Start naming an unsaved draft without clearing its content."""
        self._editing_new = True
        self._renaming_template = None
        self._draft_name_seed = name
        self.refresh_list()

    def _capture_new_template_name(self):
        name = ""
        for i in range(self.template_list.count()):
            widget = self.template_list.itemWidget(self.template_list.item(i))
            if isinstance(widget, TemplateListItem) and widget._editable:
                name = widget.get_name()
                break
        if name:
            self._draft_name_seed = name

    def _on_rename_confirmed(self, old_name: str, new_name: str):
        self._renaming_template = None
        new_basename = new_name.strip()
        if not new_basename:
            self.refresh_list()
            return
        
        # Preserve folder path when renaming
        old_folder = self._get_template_folder(old_name)
        if old_folder:
            full_new_name = f"{old_folder}/{new_basename}"
        else:
            full_new_name = new_basename
        
        old_display = self._get_template_display_name(old_name)
        if old_display == new_basename:
            self.refresh_list()
            return

        old_path = library.get_project_template_path(old_name)
        if old_path.exists():
            if library.rename_project_template(old_name, full_new_name):
                if self._current_template == old_name:
                    self._current_template = full_new_name
                if old_name in self._draft_store:
                    self._draft_store[full_new_name] = self._draft_store.pop(old_name)
                self.template_renamed.emit(old_name, full_new_name)
            self.refresh_list()
            return

        if old_name in self._draft_store:
            self._draft_store[full_new_name] = self._draft_store.pop(old_name)
        self._current_template = full_new_name
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
        """Delete a template with confirmation dialog and slide animation."""
        # Show confirmation dialog
        display_name = self._get_template_display_name(name)
        dialog = DeleteConfirmationDialog(display_name, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        if dialog.choice != DeleteConfirmationDialog.Choice.DELETE:
            return

        prev_name = self.get_previous_template_name(name)
        for i in range(self.template_list.count()):
            item = self.template_list.item(i)
            item_path = item.data(ROLE_ITEM_PATH)
            widget = self.template_list.itemWidget(item)
            if isinstance(widget, TemplateListItem) and item_path == name:
                start_pos = widget.pos()
                end_pos = QPoint(-widget.width(), start_pos.y())

                animation = QPropertyAnimation(widget, b"pos")
                animation.setDuration(200)
                animation.setStartValue(start_pos)
                animation.setEndValue(end_pos)
                animation.setEasingCurve(QEasingCurve.Type.InQuad)

                def on_finished(template_name=name, prev=prev_name):
                    self.template_delete_requested.emit(template_name)
                    library.delete_project_template(template_name)
                    if template_name == self._current_template:
                        self._current_template = None
                        self._has_unsaved_changes = False
                        self._original_content = ""
                        if prev:
                            self.template_selected.emit(prev)
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
    """Right top panel: title and custom inputs."""

    values_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("detailsPanel")
        self.setProperty("class", "panel")
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )

        self._custom_fields = {}
        self._custom_field_specs = []
        self._field_animations = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        header = QLabel("DETAILS")
        header.setProperty("class", "panelHeader")
        header.setToolTip("Project details for token substitution")
        layout.addWidget(header)

        title_label = QLabel("Title")
        layout.addWidget(title_label)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("My Project")
        self.title_input.textChanged.connect(self.values_changed.emit)
        layout.addWidget(self.title_input)

        self._custom_fields_container = QWidget()
        self._custom_fields_container.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )
        self._custom_fields_layout = QVBoxLayout(self._custom_fields_container)
        self._custom_fields_layout.setSpacing(6)
        self._custom_fields_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._custom_fields_container)

    def get_title(self) -> str:
        return self.title_input.text()

    def _normalize_custom_field_specs(self, fields) -> list[tuple[str, str, str, str, str, str]]:
        specs = []
        seen = set()
        if not fields:
            return specs
        for field in fields:
            token = self._read_field_value(field, "token")
            if not token:
                continue
            token_key = token.lower()
            if token_key in seen:
                continue
            seen.add(token_key)
            label = self._read_field_value(field, "label") or token
            placeholder = self._read_field_value(field, "placeholder") or ""
            field_type = (
                self._read_field_value(field, "field_type")
                or self._read_field_value(field, "type")
                or "text"
            ).lower()
            default_value = self._read_field_value(field, "default")
            specs.append((token_key, token, label, placeholder, field_type, default_value))
        return specs

    def _read_field_value(self, field, key: str) -> str:
        if isinstance(field, dict):
            value = field.get(key)
        else:
            value = getattr(field, key, None)
        if value is None:
            return ""
        return str(value).strip()

    def _clear_custom_field_widgets(self):
        while self._custom_fields_layout.count():
            item = self._custom_fields_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def set_custom_fields(self, fields, *, animate: bool = True):
        specs = self._normalize_custom_field_specs(fields)
        if specs == self._custom_field_specs:
            return
        previous_values = {
            key: field["widget"].text()
            for key, field in self._custom_fields.items()
        }
        if not animate:
            self._custom_field_specs = specs
            for field in list(self._custom_fields.values()):
                container = field.get("container")
                if container:
                    container.setParent(None)
                    container.deleteLater()
            self._custom_fields = {}
            new_order = [spec[0] for spec in specs]
            for token_key, token, label, placeholder, field_type, default_value in specs:
                container, label_widget, input_widget = self._create_field_widgets(
                    label,
                    placeholder,
                )
                input_widget.textChanged.connect(self.values_changed.emit)
                if token_key in previous_values:
                    input_widget.blockSignals(True)
                    input_widget.setText(previous_values[token_key])
                    input_widget.blockSignals(False)
                container.setVisible(True)
                container.setMaximumHeight(16777215)
                self._custom_fields[token_key] = {
                    "token": token,
                    "label": label_widget,
                    "widget": input_widget,
                    "container": container,
                    "field_type": field_type,
                    "default": default_value,
                }
            self._rebuild_custom_fields_layout(new_order)
            self._apply_tab_order()
            return
        new_order = [spec[0] for spec in specs]
        new_keys = set(new_order)
        removed_keys = [key for key in self._custom_fields if key not in new_keys]
        self._custom_field_specs = specs

        for token_key in removed_keys:
            field = self._custom_fields.get(token_key)
            if field and not field.get("removing"):
                field["removing"] = True
                self._animate_field_removal(field["container"], token_key)

        for token_key, token, label, placeholder, field_type, default_value in specs:
            if token_key in self._custom_fields:
                field = self._custom_fields[token_key]
                if field.get("removing"):
                    field["removing"] = False
                    self._animate_field_appearance(field["container"])
                field["label"].setText(label)
                field["widget"].setPlaceholderText(placeholder)
                field["default"] = default_value
                field["field_type"] = field_type
            else:
                container, label_widget, input_widget = self._create_field_widgets(
                    label,
                    placeholder,
                )
                input_widget.textChanged.connect(self.values_changed.emit)
                if token_key in previous_values:
                    input_widget.blockSignals(True)
                    input_widget.setText(previous_values[token_key])
                    input_widget.blockSignals(False)
                self._custom_fields[token_key] = {
                    "token": token,
                    "label": label_widget,
                    "widget": input_widget,
                    "container": container,
                    "field_type": field_type,
                    "default": default_value,
                }
                self._animate_field_appearance(container)

        self._rebuild_custom_fields_layout(new_order + removed_keys)
        self._apply_tab_order()

    def get_custom_field_values(self, apply_defaults: bool = False) -> dict[str, str]:
        values = {}
        for field in self._custom_fields.values():
            if field.get("removing"):
                continue
            text = field["widget"].text()
            if apply_defaults and not text.strip() and field.get("default"):
                values[field["token"]] = field["default"]
            else:
                values[field["token"]] = text
        return values

    def set_custom_field_values(self, values: dict[str, str]):
        if not values:
            return
        normalized = {str(key).lower(): "" if value is None else str(value)
                      for key, value in values.items()}
        for key, field in self._custom_fields.items():
            if field.get("removing"):
                continue
            if key in normalized:
                field["widget"].setText(normalized[key])

    def clear_custom_field_values(self):
        for field in self._custom_fields.values():
            if field.get("removing"):
                continue
            field["widget"].clear()

    def _ordered_field_widgets(self):
        widgets = []
        for token_key, *_ in self._custom_field_specs:
            field = self._custom_fields.get(token_key)
            if not field or field.get("removing"):
                continue
            widgets.append(field["widget"])
        return widgets

    def _next_focus_outside_details(self):
        widget = self.title_input
        seen = set()
        while widget and widget not in seen:
            seen.add(widget)
            widget = widget.nextInFocusChain()
            if widget and not self.isAncestorOf(widget) and widget is not self:
                return widget
        return None

    def _apply_tab_order(self):
        widgets = [self.title_input] + self._ordered_field_widgets()
        if not widgets:
            return
        for first, second in zip(widgets, widgets[1:]):
            QWidget.setTabOrder(first, second)
        next_widget = self._next_focus_outside_details()
        if next_widget and widgets[-1] is not next_widget:
            QWidget.setTabOrder(widgets[-1], next_widget)

    def _create_field_widgets(self, label: str, placeholder: str):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        label_widget = QLabel(label)
        input_widget = QLineEdit()
        input_widget.setPlaceholderText(placeholder)
        layout.addWidget(label_widget)
        layout.addWidget(input_widget)
        container.setVisible(False)
        return container, label_widget, input_widget

    def _rebuild_custom_fields_layout(self, order: list[str]):
        while self._custom_fields_layout.count():
            item = self._custom_fields_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
        for token_key in order:
            field = self._custom_fields.get(token_key)
            if field:
                self._custom_fields_layout.addWidget(field["container"])

    def _animate_field_appearance(self, container: QWidget):
        container.setVisible(True)
        container.setMaximumHeight(16777215)
        container.adjustSize()
        target_height = container.sizeHint().height() or container.minimumSizeHint().height()
        if target_height <= 0:
            target_height = 48
        container.setMaximumHeight(0)
        animation = QPropertyAnimation(container, b"maximumHeight")
        animation.setDuration(180)
        animation.setStartValue(0)
        animation.setEndValue(target_height)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(lambda: container.setMaximumHeight(16777215))
        self._track_field_animation(animation)

    def _animate_field_removal(self, container: QWidget, token_key: str):
        container.setMaximumHeight(container.sizeHint().height())
        animation = QPropertyAnimation(container, b"maximumHeight")
        animation.setDuration(160)
        animation.setStartValue(container.maximumHeight())
        animation.setEndValue(0)
        animation.setEasingCurve(QEasingCurve.Type.InCubic)

        def cleanup():
            container.setVisible(False)
            container.setParent(None)
            container.deleteLater()
            self._custom_fields.pop(token_key, None)

        animation.finished.connect(cleanup)
        self._track_field_animation(animation)

    def _track_field_animation(self, animation: QPropertyAnimation):
        if not hasattr(self, "_field_animations"):
            self._field_animations = []
        self._field_animations.append(animation)

        def drop_animation():
            if animation in self._field_animations:
                self._field_animations.remove(animation)

        animation.finished.connect(drop_animation)
        animation.start()


class PreviewPanel(QFrame):
    """Right middle panel: file tree preview and content viewer."""

    generate_item_requested = pyqtSignal(str)  # Emits path of item to generate

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
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
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

    def _set_status(self, message: str, status_class: str):
        self.status_label.setText(message)
        self.status_label.setProperty("class", status_class)
        self.status_label.style().polish(self.status_label)

    def update_tree(
        self,
        root_node,
        status_message: str = None,
        status_kind: str = "error",
    ):
        """Update the preview tree with file nodes."""
        if status_message and status_kind == "error":
            self._set_status(status_message, "error")
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
            if status_message:
                self._set_status(status_message, status_kind)
            else:
                self._set_status("No files", "muted")
            self.tree.clear()
            self._file_contents = {}
            self._clear_content_view()
            self.tree.setUpdatesEnabled(True)
            self.tree.blockSignals(False)
            return

        file_count = root_node.file_count()
        if status_message:
            self._set_status(status_message, status_kind)
        else:
            self._set_status(
                f"{file_count} file{'s' if file_count != 1 else ''}",
                "muted",
            )

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

            elif current and key == Qt.Key.Key_Left:
                # Collapse folder when pressing left arrow
                is_folder = current.data(0, Qt.ItemDataRole.UserRole + 1)
                if is_folder and current.isExpanded():
                    current.setExpanded(False)
                    return True

            elif current and key == Qt.Key.Key_Right:
                # Expand folder when pressing right arrow
                is_folder = current.data(0, Qt.ItemDataRole.UserRole + 1)
                if is_folder and not current.isExpanded():
                    current.setExpanded(True)
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

    def _show_context_menu(self, pos):
        """Show context menu for tree items."""
        item = self.tree.itemAt(pos)
        if item is None:
            return

        is_placeholder = item.data(0, Qt.ItemDataRole.UserRole + 2)
        if is_placeholder:
            return

        path = item.data(0, Qt.ItemDataRole.UserRole)
        is_folder = item.data(0, Qt.ItemDataRole.UserRole + 1)

        menu = QMenu(self)

        if is_folder:
            generate_action = menu.addAction("Generate this folder")
        else:
            generate_action = menu.addAction("Generate this file")

        action = menu.exec(self.tree.mapToGlobal(pos))

        if action == generate_action:
            self.generate_item_requested.emit(path)

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
    """Bottom center panel: file templates list and editor with folder support."""

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
        self._new_template_folder = None  # Folder to create new template in
        self._renaming_template = None
        self._renaming_folder = None
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
        
        # Folder expansion states
        self._folder_expanded = {}
        
        # Drag and drop state
        self._drag_start_pos = None
        self._drag_source_name = None
        self._drag_hover_item = None  # Currently highlighted drop target

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
        self.template_list.setSpacing(0)
        self.template_list.setViewportMargins(0, 0, 0, 0)
        self.template_list.itemClicked.connect(self._on_item_clicked)
        self.template_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.template_list.currentItemChanged.connect(self._on_current_item_changed)
        self.template_list.installEventFilter(self)
        self.template_list.viewport().installEventFilter(self)
        self.template_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.template_list.customContextMenuRequested.connect(self._show_context_menu)
        
        # Enable drag and drop (use DragDrop mode, not InternalMove, to prevent Qt's auto-reordering)
        self.template_list.setDragEnabled(True)
        self.template_list.setAcceptDrops(True)
        self.template_list.setDragDropMode(QListWidget.DragDropMode.DragDrop)
        self.template_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.template_list.viewport().setAcceptDrops(True)
        
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

    def _get_folder_display_name(self, folder: str) -> str:
        """Get display name for a folder (last component of path)."""
        return Path(folder).name

    def _get_template_display_name(self, name: str) -> str:
        """Get display name for a template (last component without folder)."""
        return Path(name).name

    def _get_template_folder(self, name: str) -> str | None:
        """Get the folder a template is in, or None if at root."""
        path = Path(name)
        if len(path.parts) > 1:
            return path.parts[0]
        return None

    def refresh_list(self):
        """Refresh the template list from disk with folder support."""
        if self._refreshing:
            self._refresh_pending = True
            return
        self._refreshing = True
        self.template_list.clear()
        
        template_names = library.list_file_template_names()
        folders = library.list_file_template_folders()
        unsaved_names = set(self._drafts.keys())
        if self._has_unsaved_changes and self._current_template:
            unsaved_names.add(self._current_template)

        # Track which templates are in folders
        templates_in_folders = set()
        for folder in folders:
            for t in template_names:
                if t.startswith(f"{folder}/"):
                    templates_in_folders.add(t)

        # Add folders first
        for folder in folders:
            if folder == self._renaming_folder:
                item = QListWidgetItem()
                widget = FolderListItem(
                    folder,
                    editable=True,
                    placeholder="Folder name...",
                    expanded=self._folder_expanded.get(folder, True),
                )
                widget.name_edited.connect(self._on_folder_rename_confirmed)
                widget.name_canceled.connect(self._on_folder_rename_canceled)
                widget.name_edit.setText(folder)
                item.setData(ROLE_ITEM_TYPE, "folder")
                item.setData(ROLE_ITEM_PATH, folder)
                item.setSizeHint(widget.sizeHint())
                self.template_list.addItem(item)
                self.template_list.setItemWidget(item, widget)
                QTimer.singleShot(50, widget.focus_edit)
            else:
                expanded = self._folder_expanded.get(folder, True)
                item = QListWidgetItem()
                widget = FolderListItem(
                    folder,
                    expanded=expanded,
                )
                widget.rename_requested.connect(self._start_rename_folder)
                widget.delete_clicked.connect(self._delete_folder)
                widget.toggled.connect(self._on_folder_toggled)
                item.setData(ROLE_ITEM_TYPE, "folder")
                item.setData(ROLE_ITEM_PATH, folder)
                item.setSizeHint(widget.sizeHint())
                self.template_list.addItem(item)
                self.template_list.setItemWidget(item, widget)

            # Add templates inside folder if expanded
            if self._folder_expanded.get(folder, True):
                folder_templates = [t for t in template_names if t.startswith(f"{folder}/")]
                for name in folder_templates:
                    self._add_template_item(name, unsaved_names, indent=True)
                
                # Add new template input inside this folder if creating here
                if self._editing_new and self._new_template_folder == folder:
                    item = QListWidgetItem()
                    widget = TemplateListItem(
                        "",
                        editable=True,
                        placeholder="filename.ext",
                    )
                    widget.name_edited.connect(self._on_new_name_confirmed)
                    widget.name_canceled.connect(self._on_new_name_canceled)
                    item.setData(ROLE_ITEM_TYPE, "template")
                    item.setData(ROLE_ITEM_PATH, "")
                    item.setSizeHint(widget.sizeHint())
                    # Add indentation for folder context
                    layout = widget.layout()
                    if layout:
                        margins = layout.contentsMargins()
                        layout.setContentsMargins(margins.left() + 20, margins.top(), margins.right(), margins.bottom())
                    self.template_list.addItem(item)
                    self.template_list.setItemWidget(item, widget)
                    self.template_list.setCurrentItem(item)
                    QTimer.singleShot(50, widget.focus_edit)

        # Add templates at root level (not in any folder)
        for name in template_names:
            if name not in templates_in_folders:
                self._add_template_item(name, unsaved_names, indent=False)

        # Handle editing new template (only at root level)
        if self._editing_new and not self._new_template_folder:
            item = QListWidgetItem()
            widget = TemplateListItem(
                "",
                editable=True,
                placeholder="filename.ext",
            )
            widget.name_edited.connect(self._on_new_name_confirmed)
            widget.name_canceled.connect(self._on_new_name_canceled)
            item.setData(ROLE_ITEM_TYPE, "template")
            item.setData(ROLE_ITEM_PATH, "")
            item.setSizeHint(widget.sizeHint())
            self.template_list.addItem(item)
            self.template_list.setItemWidget(item, widget)
            self.template_list.setCurrentItem(item)
            QTimer.singleShot(50, widget.focus_edit)

        add_item = QListWidgetItem()
        add_widget = AddTemplateButton()
        add_widget.clicked.connect(self._create_new_template)
        add_widget.folder_clicked.connect(self._create_new_folder)
        add_item.setData(ROLE_ITEM_TYPE, "add_button")
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

    def _create_new_folder(self):
        """Create a new folder and show rename input."""
        folder_name = self._generate_unique_folder_name("New Folder")
        library.create_file_template_folder(folder_name)
        self._folder_expanded[folder_name] = True
        self._renaming_folder = folder_name
        self.refresh_list()
        self._select_item_by_path(folder_name)
        self.template_list.setFocus()

    def _add_template_item(self, name: str, unsaved_names: set, indent: bool = False):
        """Add a template item to the list."""
        display_name = self._get_template_display_name(name)
        
        if name == self._renaming_template:
            item = QListWidgetItem()
            widget = TemplateListItem(
                display_name,
                editable=True,
                placeholder="filename.ext",
            )
            widget.name_edited.connect(
                lambda old, new, n=name: self._on_rename_confirmed(n, new)
            )
            widget.name_canceled.connect(lambda old: self._on_rename_canceled(name))
            widget.name_edit.setText(display_name)
            if indent:
                layout = widget.layout()
                if layout:
                    margins = layout.contentsMargins()
                    layout.setContentsMargins(20, margins.top(), margins.right(), margins.bottom())
            item.setData(ROLE_ITEM_TYPE, "template")
            item.setData(ROLE_ITEM_PATH, name)
            item.setSizeHint(widget.sizeHint())
            self.template_list.addItem(item)
            self.template_list.setItemWidget(item, widget)
            self.template_list.setCurrentItem(item)
            QTimer.singleShot(50, widget.focus_edit)
        else:
            item = QListWidgetItem()
            widget = TemplateListItem(
                display_name,
            )
            widget.rename_requested.connect(lambda n=name: self._start_rename_template(n))
            widget.delete_clicked.connect(lambda n=name: self._delete_template(n))
            if name in unsaved_names:
                widget.set_unsaved(True)
            if indent:
                layout = widget.layout()
                if layout:
                    margins = layout.contentsMargins()
                    layout.setContentsMargins(20, margins.top(), margins.right(), margins.bottom())
            item.setData(ROLE_ITEM_TYPE, "template")
            item.setData(ROLE_ITEM_PATH, name)
            item.setSizeHint(widget.sizeHint())
            self.template_list.addItem(item)
            self.template_list.setItemWidget(item, widget)

            if name == self._current_template:
                self.template_list.setCurrentItem(item)

    def _on_folder_toggled(self, folder: str, expanded: bool):
        """Handle folder expand/collapse."""
        self._folder_expanded[folder] = expanded
        self.refresh_list()
        self._select_item_by_path(folder)

    def _select_item_by_path(self, path: str):
        """Select an item in the list by its path."""
        for i in range(self.template_list.count()):
            item = self.template_list.item(i)
            if item and item.data(ROLE_ITEM_PATH) == path:
                self.template_list.setCurrentItem(item)
                return

    def _start_rename_folder(self, folder: str):
        """Start renaming a folder."""
        self._renaming_folder = folder
        self.refresh_list()

    def _on_folder_rename_confirmed(self, old_name: str, new_name: str):
        """Handle folder rename confirmation."""
        self._renaming_folder = None
        if old_name != new_name and new_name:
            if library.rename_file_template_folder(old_name, new_name):
                # Update expansion state
                if old_name in self._folder_expanded:
                    self._folder_expanded[new_name] = self._folder_expanded.pop(old_name)
                # Update current template path if it was in this folder
                if self._current_template and self._current_template.startswith(f"{old_name}/"):
                    new_template = new_name + self._current_template[len(old_name):]
                    self._current_template = new_template
                    self.reference_label.setText(f"Reference: template: {self._current_template}")
        self.refresh_list()

    def _on_folder_rename_canceled(self, old_name: str):
        """Handle folder rename cancellation."""
        self._renaming_folder = None
        self.refresh_list()

    def _delete_folder(self, folder: str):
        """Delete a folder and all its contents."""
        templates_in_folder = library.get_file_templates_in_folder(folder)
        dialog = DeleteFolderConfirmationDialog(
            folder, len(templates_in_folder), parent=self
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        
        library.delete_file_template_folder(folder)
        self._folder_expanded.pop(folder, None)
        
        # Clear current template if it was in the deleted folder
        if self._current_template and self._current_template.startswith(f"{folder}/"):
            self._current_template = None
            self._has_unsaved_changes = False
            self._original_content = ""
            self.editor.clear()
            self.reference_label.setText("Reference: template: <name>")
        
        self.refresh_list()
        self.templates_changed.emit()

    def _generate_unique_folder_name(self, base_name: str) -> str:
        """Generate a unique folder name."""
        existing = set(library.list_file_template_folders())
        if base_name not in existing:
            return base_name
        index = 1
        while True:
            candidate = f"{base_name} ({index})"
            if candidate not in existing:
                return candidate
            index += 1

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
        from PyQt6.QtCore import QEvent, QMimeData
        from PyQt6.QtGui import QDrag
        
        if obj in (self.template_list, self.template_list.viewport()):
            if event.type() == QEvent.Type.MouseButtonPress:
                self._mouse_click_in_progress = True
                if event.button() == Qt.MouseButton.LeftButton:
                    self._drag_start_pos = event.position().toPoint()
                    item = self.template_list.itemAt(self._drag_start_pos)
                    if item:
                        item_type = item.data(ROLE_ITEM_TYPE)
                        if item_type == "template":
                            self._drag_source_name = item.data(ROLE_ITEM_PATH)
                        else:
                            self._drag_source_name = None
                    else:
                        self._drag_source_name = None
                        
            elif event.type() == QEvent.Type.MouseMove:
                if (self._drag_start_pos is not None 
                    and self._drag_source_name is not None
                    and event.buttons() & Qt.MouseButton.LeftButton):
                    distance = (event.position().toPoint() - self._drag_start_pos).manhattanLength()
                    if distance >= 10:  # Drag threshold
                        self._start_drag()
                        return True
                        
            elif event.type() == QEvent.Type.MouseButtonRelease:
                self._drag_start_pos = None
                self._drag_source_name = None
                self._mouse_clear_timer.start(0)
                
            elif event.type() == QEvent.Type.DragEnter:
                if event.mimeData().hasFormat("application/x-makeproject-filetemplate"):
                    event.acceptProposedAction()
                    return True
                    
            elif event.type() == QEvent.Type.DragMove:
                if event.mimeData().hasFormat("application/x-makeproject-filetemplate"):
                    drop_pos = event.position().toPoint()
                    target_item = self.template_list.itemAt(drop_pos)
                    self._update_drag_hover(target_item)
                    event.acceptProposedAction()
                    return True
                    
            elif event.type() == QEvent.Type.Drop:
                if event.mimeData().hasFormat("application/x-makeproject-filetemplate"):
                    self._clear_drag_hover()
                    self._handle_drop(event)
                    return True
                    
            elif event.type() == QEvent.Type.DragLeave:
                self._clear_drag_hover()
                    
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
                elif key == Qt.Key.Key_Left:
                    # Collapse folder when pressing left arrow
                    current = self.template_list.currentItem()
                    if current:
                        item_type = current.data(ROLE_ITEM_TYPE)
                        if item_type == "folder":
                            folder = current.data(ROLE_ITEM_PATH)
                            if folder and self._folder_expanded.get(folder, True):
                                self._folder_expanded[folder] = False
                                self.refresh_list()
                                self._select_item_by_path(folder)
                                return True
                elif key == Qt.Key.Key_Right:
                    # Expand folder when pressing right arrow
                    current = self.template_list.currentItem()
                    if current:
                        item_type = current.data(ROLE_ITEM_TYPE)
                        if item_type == "folder":
                            folder = current.data(ROLE_ITEM_PATH)
                            if folder and not self._folder_expanded.get(folder, True):
                                self._folder_expanded[folder] = True
                                self.refresh_list()
                                self._select_item_by_path(folder)
                                return True
                elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    current = self.template_list.currentItem()
                    if current:
                        item_type = current.data(ROLE_ITEM_TYPE)
                        widget = self.template_list.itemWidget(current)
                        if item_type == "template" and isinstance(widget, TemplateListItem) and not widget._editable:
                            path = current.data(ROLE_ITEM_PATH)
                            if path:
                                self._renaming_template = path
                                self.refresh_list()
                                return True
                        elif item_type == "folder" and isinstance(widget, FolderListItem) and not widget._editable:
                            folder = current.data(ROLE_ITEM_PATH)
                            if folder:
                                self._start_rename_folder(folder)
                                return True
        return super().eventFilter(obj, event)

    def _start_drag(self):
        """Initiate a drag operation for a file template."""
        from PyQt6.QtCore import QMimeData
        from PyQt6.QtGui import QDrag, QPixmap, QPainter
        
        if not self._drag_source_name:
            return
            
        drag = QDrag(self.template_list)
        mime_data = QMimeData()
        mime_data.setData("application/x-makeproject-filetemplate", self._drag_source_name.encode())
        drag.setMimeData(mime_data)
        
        # Create visual drag feedback
        display_name = self._get_template_display_name(self._drag_source_name)
        font = self.template_list.font()
        metrics = self.template_list.fontMetrics()
        text_width = metrics.horizontalAdvance(display_name) + 24
        text_height = metrics.height() + 12
        
        pixmap = QPixmap(text_width, text_height)
        pixmap.fill(QColor(26, 188, 157, 200))  # Teal with transparency
        
        painter = QPainter(pixmap)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, display_name)
        painter.end()
        
        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(text_width // 2, text_height // 2))
        
        # Execute drag
        drag.exec(Qt.DropAction.MoveAction)
        
        self._drag_start_pos = None
        self._drag_source_name = None

    def _handle_drop(self, event):
        """Handle a drop event for folder creation or moving."""
        source_name = event.mimeData().data("application/x-makeproject-filetemplate").data().decode()
        drop_pos = event.position().toPoint()
        target_item = self.template_list.itemAt(drop_pos)
        
        if target_item is None:
            # Refresh to reset any Qt-internal reordering
            self.refresh_list()
            return
            
        target_type = target_item.data(ROLE_ITEM_TYPE)
        target_path = target_item.data(ROLE_ITEM_PATH)
        
        # Ignore drops on add_button - it should have no effect
        if target_type == "add_button":
            self.refresh_list()
            return
        
        if target_type == "folder":
            # Drop onto folder - move template into folder
            source_folder = self._get_template_folder(source_name)
            if source_folder == target_path:
                # Already in this folder
                self.refresh_list()
                return
            new_name = library.move_file_template_to_folder(source_name, target_path)
            if new_name:
                if self._current_template == source_name:
                    self._current_template = new_name
                    self.reference_label.setText(f"Reference: template: {self._current_template}")
                self.templates_changed.emit()
            self.refresh_list()
                
        elif target_type == "template":
            # Drop onto template - create new folder containing both OR move out of folder
            if source_name == target_path:
                self.refresh_list()
                return
            source_folder = self._get_template_folder(source_name)
            target_folder = self._get_template_folder(target_path)
            
            # If both templates are in the same folder (or both at root), create a new subfolder
            if source_folder == target_folder:
                # First, create folder with temporary name and move templates
                temp_folder = self._generate_unique_folder_name("New Folder")
                library.create_file_template_folder(temp_folder)
                self._folder_expanded[temp_folder] = True
                
                # Move both templates into the folder
                for template_name in [source_name, target_path]:
                    new_path = library.move_file_template_to_folder(template_name, temp_folder)
                    if new_path and self._current_template == template_name:
                        self._current_template = new_path
                        self.reference_label.setText(f"Reference: template: {self._current_template}")
                
                # Now show rename input for the folder
                self._renaming_folder = temp_folder
                self.refresh_list()
                self._select_item_by_path(temp_folder)
                self.template_list.setFocus()
                self.templates_changed.emit()
            else:
                # Move source to target's folder (or root if target has no folder)
                if target_folder:
                    new_name = library.move_file_template_to_folder(source_name, target_folder)
                else:
                    new_name = library.move_file_template_out_of_folder(source_name)
                if new_name:
                    if self._current_template == source_name:
                        self._current_template = new_name
                        self.reference_label.setText(f"Reference: template: {self._current_template}")
                    self.templates_changed.emit()
                self.refresh_list()

    def _update_drag_hover(self, target_item):
        """Update the visual highlight for the current drag hover target."""
        if target_item == self._drag_hover_item:
            return
        
        # Clear previous highlights
        self._clear_drag_hover()
        
        if target_item is None:
            return
            
        # Don't highlight the source item being dragged
        target_path = target_item.data(ROLE_ITEM_PATH)
        if target_path == self._drag_source_name:
            return
        
        target_type = target_item.data(ROLE_ITEM_TYPE)
        
        # Don't highlight the add button
        if target_type == "add_button":
            return
        
        # Check if source is in a folder
        source_folder = self._get_template_folder(self._drag_source_name) if self._drag_source_name else None
        target_folder = None
        if target_type == "template":
            target_folder = self._get_template_folder(target_path)
        elif target_type == "folder":
            # Hovering over a folder means we'd move INTO it, not to root
            target_folder = target_path
        
        # If dragging from a folder to ROOT level, highlight all ROOT-LEVEL items
        # (templates not in any folder, plus folder headers - but not items inside other folders)
        if source_folder and target_folder is None:
            self._drag_hover_items = []
            for i in range(self.template_list.count()):
                item = self.template_list.item(i)
                item_type = item.data(ROLE_ITEM_TYPE)
                item_path = item.data(ROLE_ITEM_PATH)
                
                # Skip the source item and add button
                if item_path == self._drag_source_name or item_type == "add_button":
                    continue
                
                # Only highlight root-level items
                if item_type == "folder":
                    # Folder headers are at root level (but skip source's folder)
                    if item_path != source_folder:
                        widget = self.template_list.itemWidget(item)
                        if widget:
                            widget.setStyleSheet("background-color: rgba(26, 188, 157, 0.3); border-radius: 4px;")
                            self._drag_hover_items.append(item)
                elif item_type == "template":
                    # Only templates at root (not in any folder)
                    item_folder = self._get_template_folder(item_path)
                    if item_folder is None:
                        widget = self.template_list.itemWidget(item)
                        if widget:
                            widget.setStyleSheet("background-color: rgba(26, 188, 157, 0.3); border-radius: 4px;")
                            self._drag_hover_items.append(item)
        else:
            # Normal single-item highlight
            self._drag_hover_item = target_item
            widget = self.template_list.itemWidget(target_item)
            if widget:
                widget.setStyleSheet("background-color: rgba(26, 188, 157, 0.3); border-radius: 4px;")

    def _clear_drag_hover(self):
        """Clear the visual highlight from all drag hover targets."""
        # Clear single hover item
        if self._drag_hover_item is not None:
            widget = self.template_list.itemWidget(self._drag_hover_item)
            if widget:
                widget.setStyleSheet("")
            self._drag_hover_item = None
        
        # Clear multiple hover items (for "remove from folder" hint)
        if hasattr(self, '_drag_hover_items') and self._drag_hover_items:
            for item in self._drag_hover_items:
                widget = self.template_list.itemWidget(item)
                if widget:
                    widget.setStyleSheet("")
            self._drag_hover_items = []

    def _on_current_item_changed(self, current, previous):
        if self._refreshing or current is None:
            return
        if self._mouse_click_in_progress or self._pending_click_name or self._click_timer.isActive():
            return
        
        item_type = current.data(ROLE_ITEM_TYPE)
        if item_type != "template":
            return
            
        path = current.data(ROLE_ITEM_PATH)
        widget = self.template_list.itemWidget(current)
        if isinstance(widget, TemplateListItem):
            if path and not widget._editable and path != self._current_template:
                self._load_template(path)

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
        
        item_type = item.data(ROLE_ITEM_TYPE)
        item_path = item.data(ROLE_ITEM_PATH)
        widget = self.template_list.itemWidget(item)
        
        if item_type == "folder":
            if not isinstance(widget, FolderListItem) or widget._editable:
                return
            self.template_list.setCurrentItem(item)
            menu = QMenu(self)
            new_template_action = menu.addAction("New Template")
            menu.addSeparator()
            rename_action = menu.addAction("Rename")
            show_action = menu.addAction("Show in Finder")
            menu.addSeparator()
            delete_action = menu.addAction("Delete")
            action = menu.exec(self.template_list.viewport().mapToGlobal(pos))
            if action == new_template_action:
                self._create_new_template(folder=item_path)
            elif action == rename_action:
                self._start_rename_folder(item_path)
            elif action == show_action:
                folder_path = library.get_file_templates_dir() / item_path
                if folder_path.exists():
                    if sys.platform == "darwin":
                        subprocess.run(["open", "-R", str(folder_path)])
                    else:
                        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder_path)))
            elif action == delete_action:
                self._delete_folder(item_path)
            return
            
        if item_type != "template":
            return
        if not isinstance(widget, TemplateListItem) or widget._editable:
            return
        if not item_path:
            return
        content = library.get_file_template(item_path)
        if content is None:
            return
        self.template_list.setCurrentItem(item)
        menu = QMenu(self)
        rename_action = menu.addAction("Rename")
        duplicate_action = menu.addAction("Duplicate")
        
        # Add move options
        folder = self._get_template_folder(item_path)
        folders = library.list_file_template_folders()
        if folder or folders:
            move_menu = menu.addMenu("Move to")
            if folder:
                move_root_action = move_menu.addAction("Root")
            else:
                move_root_action = None
            for f in folders:
                if f != folder:
                    move_menu.addAction(f)
        else:
            move_menu = None
            move_root_action = None
        
        show_action = menu.addAction("Show in Finder")
        menu.addSeparator()
        delete_action = menu.addAction("Delete")
        action = menu.exec(self.template_list.viewport().mapToGlobal(pos))
        if action == rename_action:
            self._start_rename_template(item_path)
        elif action == duplicate_action:
            self._duplicate_template(item_path)
        elif action == show_action:
            self._show_in_finder(item_path)
        elif action == delete_action:
            self._delete_template(item_path)
        elif move_menu and action:
            if action == move_root_action:
                new_name = library.move_file_template_out_of_folder(item_path)
                if new_name:
                    if self._current_template == item_path:
                        self._current_template = new_name
                        self.reference_label.setText(f"Reference: template: {self._current_template}")
                    self.refresh_list()
                    self.templates_changed.emit()
            elif action.text() in folders:
                new_name = library.move_file_template_to_folder(item_path, action.text())
                if new_name:
                    if self._current_template == item_path:
                        self._current_template = new_name
                        self.reference_label.setText(f"Reference: template: {self._current_template}")
                    self.refresh_list()
                    self.templates_changed.emit()

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
        item_type = item.data(ROLE_ITEM_TYPE)
        item_path = item.data(ROLE_ITEM_PATH)
        widget = self.template_list.itemWidget(item)
        
        if item_type == "template" and isinstance(widget, TemplateListItem):
            if item_path and not widget._editable:
                if item_path == self._current_template:
                    return
                self._pending_click_name = item_path
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

        item_type = item.data(ROLE_ITEM_TYPE)
        item_path = item.data(ROLE_ITEM_PATH)
        widget = self.template_list.itemWidget(item)
        
        if item_type == "folder" and isinstance(widget, FolderListItem) and not widget._editable:
            if item_path:
                self._start_rename_folder(item_path)
        elif item_type == "template" and isinstance(widget, TemplateListItem) and not widget._editable:
            if item_path:
                self._renaming_template = item_path
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

    def _create_new_template(self, folder: str = None):
        self._stash_current_template()
        self._current_template = None
        self._has_unsaved_changes = False
        self._original_content = ""
        self._editing_new = True
        self._new_template_folder = folder
        self._renaming_template = None
        # Expand the folder if creating inside one
        if folder:
            self._folder_expanded[folder] = True
        self.editor.clear()
        self._reset_editor_scroll()
        self.reference_label.setText("Reference: template: <name>")
        self.refresh_list()

    def _on_new_name_confirmed(self, old_name: str, new_name: str):
        name = new_name.strip()
        
        # Prepend folder path if creating in a folder
        if self._new_template_folder:
            name = f"{self._new_template_folder}/{name}"
        
        if name in library.list_file_template_names():
            decision = self._prompt_template_name_conflict(name)
            if decision == "cancel":
                self._editing_new = False
                self._new_template_folder = None
                self.refresh_list()
                self.template_list.setFocus()
                return
            if decision == "keep":
                name = self._next_available_template_name(name)
        self._editing_new = False
        self._new_template_folder = None
        self._current_template = name
        self._save_template()
        self.template_list.setFocus()

    def _on_new_name_canceled(self, old_name: str):
        self._editing_new = False
        self._new_template_folder = None
        self.refresh_list()

    def _on_rename_confirmed(self, old_name: str, new_name: str):
        self._renaming_template = None
        new_basename = new_name.strip()
        if not new_basename:
            self.refresh_list()
            self.template_list.setFocus()
            return
        
        # Preserve folder path when renaming
        old_folder = self._get_template_folder(old_name)
        if old_folder:
            full_new_name = f"{old_folder}/{new_basename}"
        else:
            full_new_name = new_basename
        
        old_display = self._get_template_display_name(old_name)
        if old_display == new_basename:
            self.refresh_list()
            self.template_list.setFocus()
            return
            
        content = library.get_file_template(old_name)
        if content is not None:
            library.delete_file_template(old_name)
            library.save_file_template(full_new_name, content)
            if self._current_template == old_name:
                self._current_template = full_new_name
            self.reference_label.setText(f"Reference: template: {full_new_name}")
            if old_name in self._drafts:
                self._drafts[full_new_name] = self._drafts.pop(old_name)
            if self._current_template == full_new_name:
                self._original_content = content or ""
                self._has_unsaved_changes = self.editor.toPlainText() != self._original_content
        self.refresh_list()
        self.template_list.setFocus()
        self.templates_changed.emit()

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
        """Delete a file template with confirmation dialog and slide animation."""
        # Show confirmation dialog
        display_name = self._get_template_display_name(name)
        dialog = DeleteConfirmationDialog(display_name, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        if dialog.choice != DeleteConfirmationDialog.Choice.DELETE:
            return

        for i in range(self.template_list.count()):
            item = self.template_list.item(i)
            item_path = item.data(ROLE_ITEM_PATH)
            widget = self.template_list.itemWidget(item)
            if isinstance(widget, TemplateListItem) and item_path == name:
                start_pos = widget.pos()
                end_pos = QPoint(-widget.width(), start_pos.y())

                animation = QPropertyAnimation(widget, b"pos")
                animation.setDuration(200)
                animation.setStartValue(start_pos)
                animation.setEndValue(end_pos)
                animation.setEasingCurve(QEasingCurve.Type.InQuad)

                def on_finished(template_name=name):
                    self.template_delete_requested.emit(template_name)
                    library.delete_file_template(template_name)
                    self._drafts.pop(template_name, None)
                    if template_name == self._current_template:
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

    def apply_font_size(self, size: int):
        """Apply the font size to the code editor."""
        from ..styles import get_code_font
        self.editor.setFont(get_code_font(size))

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
            )
            widget.name_edited.connect(self._on_new_name_confirmed)
            widget.name_canceled.connect(self._on_new_name_canceled)
            item.setSizeHint(widget.sizeHint())
            self.token_list.addItem(item)
            self.token_list.setItemWidget(item, widget)
            self.token_list.setCurrentItem(item)
            QTimer.singleShot(50, widget.focus_edit)

        add_item = QListWidgetItem()
        add_widget = AddTemplateButton(show_folder_button=False)
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
