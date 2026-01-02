"""
MakeProject application entrypoint.
"""

import sys

from PyQt6.QtWidgets import QApplication

from . import __version__
from .styles import get_ui_font
from .ui.window import MakeProjectWindow


def run():
    """Run the MakeProject application."""
    app = QApplication(sys.argv)
    app.setApplicationName("MakeProject")
    app.setApplicationVersion(__version__)
    app.setFont(get_ui_font())

    window = MakeProjectWindow()
    window.show()

    sys.exit(app.exec())
