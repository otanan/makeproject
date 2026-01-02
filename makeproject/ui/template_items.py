"""
Reusable list item widgets for template panels.
"""

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy


class TemplateListItem(QWidget):
    """Template list row with optional inline edit, unsaved indicator, and delete button."""

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
        delete_tooltip: str = "Delete template",
        allow_delete: bool = True,
        delete_square: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._name = name
        self._has_unsaved = False
        self._editable = editable
        self._edit_finished = False
        self._allow_delete = allow_delete

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 0, 0)
        layout.setSpacing(4)

        # Unsaved indicator dot
        self.dot_label = QLabel("●")
        self.dot_label.setFixedWidth(12)
        self.dot_label.setStyleSheet("color: #1ABC9D; font-size: 10px;")
        self.dot_label.setVisible(False)
        layout.addWidget(self.dot_label)

        # Name label or inline edit
        if editable:
            self.name_edit = QLineEdit()
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

        self.delete_btn = QPushButton("−")
        if delete_square:
            self.delete_btn.setFixedSize(28, 28)
            self.delete_btn.setSizePolicy(
                QSizePolicy.Policy.Fixed,
                QSizePolicy.Policy.Fixed
            )
        else:
            self.delete_btn.setFixedWidth(28)
            self.delete_btn.setSizePolicy(
                QSizePolicy.Policy.Fixed,
                QSizePolicy.Policy.Expanding
            )
        self.delete_btn.setProperty("class", "deleteButton")
        self.delete_btn.setToolTip(delete_tooltip)
        self.delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self._name))
        self.delete_btn.setVisible(False)
        layout.addWidget(self.delete_btn)

        self.setMouseTracking(True)

    def mouseDoubleClickEvent(self, event):
        if not self._editable:
            if self.delete_btn.isVisible():
                btn_rect = self.delete_btn.geometry()
                if btn_rect.contains(event.position().toPoint()):
                    return super().mouseDoubleClickEvent(event)
            self.rename_requested.emit(self._name)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def enterEvent(self, event):
        if not self._editable and self._allow_delete:
            self.delete_btn.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.delete_btn.setVisible(False)
        super().leaveEvent(event)

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
    """Row widget for the + button below template lists."""

    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.add_btn = QPushButton("+")
        self.add_btn.setFixedSize(28, 28)
        self.add_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.add_btn.setProperty("class", "addButton")
        self.add_btn.setToolTip("Create new template")
        self.add_btn.clicked.connect(self.clicked.emit)
        layout.addWidget(self.add_btn)
        layout.setAlignment(
            self.add_btn,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addStretch(1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(self.add_btn.height())
        self.setMinimumWidth(0)

    def sizeHint(self):
        return QSize(0, self.add_btn.height())

    def minimumSizeHint(self):
        return QSize(0, self.add_btn.height())
