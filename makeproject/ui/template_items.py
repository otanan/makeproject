"""
Reusable list item widgets for template panels.
"""

from PyQt6.QtCore import Qt, QSize, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFontMetrics, QIcon, QPainter, QPixmap, QPainterPath, QColor
from ..constants import Dimensions
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QFrame,
)


class InlineEdit(QLineEdit):
    """Inline edit with a trailing return-key hint."""

    _return_symbol = "↩"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._base_margins = self.textMargins()
        self._icon_padding = 8
        self._hint_action = None
        self._hint_width = 0
        self._install_return_hint()
        self.textChanged.connect(self._update_return_hint_visibility)

    def _install_return_hint(self):
        icon = self._build_return_icon()
        self._hint_action = self.addAction(
            icon, QLineEdit.ActionPosition.TrailingPosition
        )
        self._hint_action.setEnabled(False)
        self._hint_action.setVisible(True)
        self._update_return_hint_visibility()

    def _build_return_icon(self) -> QIcon:
        metrics = QFontMetrics(self.font())
        text_width = metrics.horizontalAdvance(self._return_symbol)
        text_height = metrics.height()
        self._hint_width = text_width

        pixmap = QPixmap(text_width + 2, text_height + 2)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(self.palette().color(self.palette().ColorRole.PlaceholderText))
        painter.drawText(
            pixmap.rect(),
            Qt.AlignmentFlag.AlignCenter,
            self._return_symbol,
        )
        painter.end()

        return QIcon(pixmap)

    def _update_return_hint_visibility(self):
        if not self._hint_action:
            return
        left = self._base_margins.left()
        top = self._base_margins.top()
        right = self._base_margins.right()
        bottom = self._base_margins.bottom()
        available = self.width() - left - right - self._icon_padding - self._hint_width
        text_width = QFontMetrics(self.font()).horizontalAdvance(self.text())
        visible = text_width < available
        self._hint_action.setVisible(visible)
        if visible:
            margin_right = max(right, self._hint_width + self._icon_padding)
            self.setTextMargins(left, top, margin_right, bottom)
        else:
            self.setTextMargins(left, top, right, bottom)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_return_hint_visibility()

    def changeEvent(self, event):
        from PyQt6.QtCore import QEvent
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange:
            if self._hint_action:
                self._hint_action.setIcon(self._build_return_icon())
                self._update_return_hint_visibility()


class TemplateListItem(QWidget):
    """Template list row with optional inline edit and unsaved indicator."""

    delete_clicked = pyqtSignal(str)  # template name
    rename_requested = pyqtSignal(str)  # template name
    name_edited = pyqtSignal(str, str)  # old_name, new_name
    name_canceled = pyqtSignal(str)  # old_name

    def __init__(
        self,
        name: str,
        *,
        editable: bool = False,
        placeholder: str = "Template name...",
        badge_text: str = "",
        badge_tooltip: str = "",
        auto_confirm_on_focus_out: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self._name = name
        self._has_unsaved = False
        self._editable = editable
        self._edit_finished = False
        self._auto_confirm_on_focus_out = auto_confirm_on_focus_out
        self._tooltip_loaded = False  # Lazy tooltip loading flag

        layout = QHBoxLayout(self)
        # Controls the indentation of all items
        layout.setContentsMargins(Dimensions.LIST_ITEM_BASE_INDENT, 0, 0, 0)
        layout.setSpacing(4)

        # Unsaved indicator dot
        self.dot_label = QLabel("●")
        self.dot_label.setFixedWidth(12)
        self.dot_label.setStyleSheet("color: #1ABC9D; font-size: 10px;")
        self.dot_label.setVisible(False)
        layout.addWidget(self.dot_label)

        # Name label or inline edit
        if editable:
            self.name_edit = InlineEdit()
            self.name_edit.setPlaceholderText(placeholder)
            self.name_edit.setProperty("class", "inlineEdit")
            self.name_edit.installEventFilter(self)
            self.name_edit.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Preferred
            )
            layout.addWidget(self.name_edit)
            self.name_label = None
        else:
            self.name_label = QLabel(name)
            self.name_label.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Preferred
            )
            layout.addWidget(self.name_label)
            self.name_edit = None

        self.badge_label = QLabel(badge_text or "")
        self.badge_label.setProperty("class", "tokenBadge")
        if badge_tooltip:
            self.badge_label.setToolTip(badge_tooltip)
        self.badge_label.setVisible(bool(badge_text) and not editable)
        layout.addWidget(self.badge_label)

        # Maintain consistent row height (previously set by delete button)
        self.setFixedHeight(28)

    def sizeHint(self):
        return QSize(super().sizeHint().width(), 28)

    def enterEvent(self, event):
        """Load tooltip lazily on first hover to avoid loading all templates during list refresh."""
        if not self._tooltip_loaded and self._name:
            self._tooltip_loaded = True
            # Import here to avoid circular dependency
            from .. import library
            from ..template_engine import parse_template_metadata

            content = library.load_project_template(self._name)
            if content:
                # Try to get description from metadata first
                metadata = parse_template_metadata(content)
                if metadata and metadata.description:
                    self.setToolTip(metadata.description)
                else:
                    # Fall back to first comment line
                    lines = content.splitlines()
                    if lines:
                        first_line = lines[0].strip()
                        if first_line.startswith("#") and not first_line.lstrip().startswith("# ---"):
                            tooltip = first_line.lstrip("#").strip()
                            if tooltip:
                                self.setToolTip(tooltip)
        super().enterEvent(event)

    def mouseDoubleClickEvent(self, event):
        if not self._editable:
            self.rename_requested.emit(self._name)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj == self.name_edit:
            if event.type() == QEvent.Type.KeyPress:
                if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    self._confirm_or_cancel()
                    return True
                if event.key() == Qt.Key.Key_Escape:
                    self._cancel_edit()
                    return True
            elif event.type() == QEvent.Type.FocusOut:
                if self._auto_confirm_on_focus_out:
                    self._confirm_or_cancel()
        return super().eventFilter(obj, event)

    def _confirm_or_cancel(self):
        if self._edit_finished or not self.name_edit:
            return
        new_name = self.name_edit.text().strip()
        self._edit_finished = True
        if new_name:
            self.name_edited.emit(self._name, new_name)
        else:
            self.name_canceled.emit(self._name)

    def _cancel_edit(self):
        if self._edit_finished:
            return
        self._edit_finished = True
        if self.name_edit:
            self.name_canceled.emit(self._name)

    def set_unsaved(self, unsaved: bool):
        """Show or hide the unsaved indicator dot."""
        self._has_unsaved = unsaved
        self.dot_label.setVisible(unsaved)

    def get_name(self) -> str:
        if self._editable and self.name_edit:
            return self.name_edit.text().strip()
        return self._name

    def focus_edit(self):
        if self.name_edit:
            self.name_edit.setFocus()
            self.name_edit.selectAll()


class AddTemplateButton(QWidget):
    """Row widget for the + button and folder button below template lists."""

    clicked = pyqtSignal()
    folder_clicked = pyqtSignal()

    def __init__(self, show_folder_button: bool = True, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(Dimensions.LIST_ITEM_BASE_INDENT, 0, 0, 0)
        layout.setSpacing(4)

        self.add_btn = QPushButton("+")
        self.add_btn.setFixedSize(28, 28)
        self.add_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.add_btn.setProperty("class", "addButton")
        self.add_btn.setToolTip("Create new template")
        self.add_btn.clicked.connect(self.clicked.emit)
        layout.addWidget(self.add_btn)

        self.folder_btn = QPushButton("📁")
        self.folder_btn.setFixedSize(28, 28)
        self.folder_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.folder_btn.setProperty("class", "addButton")
        self.folder_btn.setToolTip("Create new folder")
        # Make the folder icon ~10% smaller than the + icon
        self.folder_btn.setStyleSheet("font-size: 12px;")
        self.folder_btn.clicked.connect(self.folder_clicked.emit)
        self.folder_btn.setVisible(show_folder_button)
        layout.addWidget(self.folder_btn)

        layout.addStretch(1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(self.add_btn.height())
        self.setMinimumWidth(0)

    def sizeHint(self):
        return QSize(0, self.add_btn.height())

    def minimumSizeHint(self):
        return QSize(0, self.add_btn.height())


class FolderListItem(QWidget):
    """Collapsible folder row for template lists."""

    delete_clicked = pyqtSignal(str)  # folder name
    rename_requested = pyqtSignal(str)  # folder name
    name_edited = pyqtSignal(str, str)  # old_name, new_name
    name_canceled = pyqtSignal(str)  # old_name
    toggled = pyqtSignal(str, bool)  # folder name, expanded

    def __init__(
        self,
        name: str,
        *,
        editable: bool = False,
        placeholder: str = "Folder name...",
        expanded: bool = True,
        auto_confirm_on_focus_out: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self._name = name
        self._editable = editable
        self._expanded = expanded
        self._edit_finished = False
        self._auto_confirm_on_focus_out = auto_confirm_on_focus_out
        self._dark_mode = True

        layout = QHBoxLayout(self)
        # Same indentation as TemplateListItem
        layout.setContentsMargins(Dimensions.LIST_ITEM_BASE_INDENT, 0, 0, 0)
        layout.setSpacing(4)

        # Disclosure triangle
        self.disclosure_btn = QPushButton()
        self.disclosure_btn.setFixedSize(16, 16)
        self.disclosure_btn.setProperty("class", "disclosureButton")
        self.disclosure_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.disclosure_btn.clicked.connect(self._toggle_expanded)
        self._update_disclosure_icon()
        layout.addWidget(self.disclosure_btn)

        # Folder icon
        self.folder_icon = QLabel("📁")
        self.folder_icon.setFixedWidth(18)
        layout.addWidget(self.folder_icon)

        # Name label or inline edit
        if editable:
            self.name_edit = InlineEdit()
            self.name_edit.setPlaceholderText(placeholder)
            self.name_edit.setProperty("class", "inlineEdit")
            self.name_edit.installEventFilter(self)
            self.name_edit.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Preferred
            )
            layout.addWidget(self.name_edit)
            self.name_label = None
        else:
            self.name_label = QLabel(name)
            self.name_label.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Preferred
            )
            layout.addWidget(self.name_label)
            self.name_edit = None

        # Maintain consistent row height (previously set by delete button)
        self.setFixedHeight(28)

    def sizeHint(self):
        return QSize(super().sizeHint().width(), 28)

    def _update_disclosure_icon(self):
        """Update the disclosure triangle based on expanded state."""
        # Use simple unicode triangles
        if self._expanded:
            self.disclosure_btn.setText("▼")
        else:
            self.disclosure_btn.setText("▶")
        # Update styling based on dark mode
        # Must override padding and min-width from base QPushButton style
        color = "#6C7086" if self._dark_mode else "#9CA3AF"
        self.disclosure_btn.setStyleSheet(
            f"QPushButton {{ color: {color}; background: transparent; border: none; "
            f"font-size: 10px; padding: 0px; min-width: 0px; }}"
        )

    def set_dark_mode(self, dark_mode: bool):
        """Update colors for dark/light mode."""
        self._dark_mode = dark_mode
        self._update_disclosure_icon()

    def _toggle_expanded(self):
        self._expanded = not self._expanded
        self._update_disclosure_icon()
        self.toggled.emit(self._name, self._expanded)

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool):
        if self._expanded != expanded:
            self._expanded = expanded
            self._update_disclosure_icon()

    def mouseDoubleClickEvent(self, event):
        if not self._editable:
            self.rename_requested.emit(self._name)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj == self.name_edit:
            if event.type() == QEvent.Type.KeyPress:
                if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    self._confirm_or_cancel()
                    return True
                if event.key() == Qt.Key.Key_Escape:
                    self._cancel_edit()
                    return True
            elif event.type() == QEvent.Type.FocusOut:
                if self._auto_confirm_on_focus_out:
                    self._confirm_or_cancel()
        return super().eventFilter(obj, event)

    def _confirm_or_cancel(self):
        if self._edit_finished or not self.name_edit:
            return
        new_name = self.name_edit.text().strip()
        self._edit_finished = True
        if new_name:
            self.name_edited.emit(self._name, new_name)
        else:
            self.name_canceled.emit(self._name)

    def _cancel_edit(self):
        if self._edit_finished:
            return
        self._edit_finished = True
        if self.name_edit:
            self.name_canceled.emit(self._name)

    def get_name(self) -> str:
        if self._editable and self.name_edit:
            return self.name_edit.text().strip()
        return self._name

    def focus_edit(self):
        if self.name_edit:
            self.name_edit.setFocus()
            self.name_edit.selectAll()


class DropIndicator(QFrame):
    """Visual indicator shown when dragging items."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(2)
        self.setStyleSheet("background-color: #1ABC9D;")
        self.hide()


class FolderDropTarget(QFrame):
    """Visual overlay shown when dragging over a folder."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "background-color: rgba(26, 188, 157, 0.2); "
            "border: 2px dashed #1ABC9D; "
            "border-radius: 4px;"
        )
        self.hide()
