"""
Custom title bar widgets for the MakeProject window.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QMouseEvent
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from .. import __version__
from ..widgets import ToggleSwitch


class WindowButton(QPushButton):
    """macOS-style window control button with hover icon."""

    def __init__(self, button_type: str, parent=None):
        super().__init__(parent)
        self.button_type = button_type
        self._hovered = False
        self.setFixedSize(12, 12)

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._hovered:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            pen = QPen(QColor("#3D3D3D"))
            pen.setWidthF(1.5)
            painter.setPen(pen)

            cx = self.width() / 2.0
            cy = self.height() / 2.0

            if self.button_type == "close":
                painter.drawLine(int(cx - 3), int(cy - 3), int(cx + 3), int(cy + 3))
                painter.drawLine(int(cx + 3), int(cy - 3), int(cx - 3), int(cy + 3))
            elif self.button_type == "maximize":
                painter.drawLine(int(cx - 3), int(cy), int(cx + 3), int(cy))
                painter.drawLine(int(cx), int(cy - 3), int(cx), int(cy + 3))
            elif self.button_type == "minimize":
                painter.drawLine(int(cx - 3), int(cy), int(cx + 3), int(cy))


class TitleBar(QFrame):
    """Frameless title bar with window controls and theme toggle."""

    close_clicked = pyqtSignal()
    maximize_clicked = pyqtSignal()
    minimize_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("titleBar")
        self.setFixedHeight(40)
        self._drag_pos = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(0)

        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)

        self.close_btn = WindowButton("close")
        self.close_btn.setObjectName("closeButton")
        self.close_btn.clicked.connect(self.close_clicked.emit)
        self.close_btn.setToolTip("Close")

        self.minimize_btn = WindowButton("minimize")
        self.minimize_btn.setObjectName("minimizeButton")
        self.minimize_btn.clicked.connect(self.minimize_clicked.emit)
        self.minimize_btn.setToolTip("Minimize")

        self.maximize_btn = WindowButton("maximize")
        self.maximize_btn.setObjectName("maximizeButton")
        self.maximize_btn.clicked.connect(self.maximize_clicked.emit)
        self.maximize_btn.setToolTip("Maximize")

        btn_layout.addWidget(self.close_btn)
        btn_layout.addWidget(self.minimize_btn)
        btn_layout.addWidget(self.maximize_btn)

        layout.addWidget(btn_container)

        layout.addStretch()
        self.title_label = QLabel("MakeProject")
        self.title_label.setObjectName("titleLabel")
        self.title_label.setToolTip(f"Version {__version__}")
        layout.addWidget(self.title_label)
        layout.addStretch()

        self.dark_mode_label = QLabel("Dark Mode")
        self.dark_mode_label.setObjectName("darkModeLabel")
        layout.addWidget(self.dark_mode_label)

        layout.addSpacing(6)

        self.dark_mode_toggle = ToggleSwitch(checked=True)
        self.dark_mode_toggle.setToolTip("Toggle dark/light mode")
        layout.addWidget(self.dark_mode_toggle)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint()
                - self.window().frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_pos:
            self.window().move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.maximize_clicked.emit()


class DialogTitleBar(QFrame):
    """Simplified frameless title bar for dialogs (no theme toggle, no maximize)."""

    close_clicked = pyqtSignal()

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("dialogTitleBar")
        self.setFixedHeight(40)
        self._drag_pos = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(0)

        # Window control button (just close for dialogs)
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)

        self.close_btn = WindowButton("close")
        self.close_btn.setObjectName("closeButton")
        self.close_btn.clicked.connect(self.close_clicked.emit)
        self.close_btn.setToolTip("Close")

        btn_layout.addWidget(self.close_btn)
        layout.addWidget(btn_container)

        # Title in center
        layout.addStretch()
        self.title_label = QLabel(title)
        self.title_label.setObjectName("dialogTitleLabel")
        layout.addWidget(self.title_label)
        layout.addStretch()

        # Empty space on right to balance layout
        spacer = QWidget()
        spacer.setFixedWidth(28)  # Same width as btn_container (12 + 8 spacing + 8)
        layout.addWidget(spacer)

    def set_title(self, title: str):
        """Update the dialog title."""
        self.title_label.setText(title)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint()
                - self.window().frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_pos:
            self.window().move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None
