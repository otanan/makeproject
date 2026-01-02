"""
Style management for MakeProject.
Loads QSS theme files and manages font fallbacks.
"""

import sys
from pathlib import Path
from functools import lru_cache
from PyQt6.QtGui import QFont, QFontDatabase


# Code font fallback list
CODE_FONT_FALLBACKS = [
    "Fira Code",
    "JetBrains Mono", 
    "SF Mono",
    "Menlo",
    "Consolas",
    "Courier New",
    "monospace"
]

# UI font fallback list
UI_FONT_FALLBACKS = [
    "Fira Sans",
    "SF Pro Display",
    "Helvetica Neue",
    "Segoe UI",
    "Arial"
]


def get_resource_path(relative_path: str) -> Path:
    """Get the absolute path to a resource, works for dev and PyInstaller."""
    module_path = Path(__file__).parent / relative_path
    if module_path.exists():
        return module_path

    if hasattr(sys, "_MEIPASS"):
        bundled_path = Path(sys._MEIPASS) / relative_path
        if bundled_path.exists():
            return bundled_path

    return module_path


@lru_cache(maxsize=2)
def load_qss(theme: str = "dark") -> str:
    """Load the QSS stylesheet for the given theme."""
    filename = f"styles_{theme}.qss"
    qss_path = get_resource_path(filename)
    
    if qss_path.exists():
        return qss_path.read_text(encoding="utf-8")
    
    # Fallback to empty stylesheet
    return ""


@lru_cache(maxsize=1)
def _get_font_families() -> tuple:
    return tuple(QFontDatabase.families())


def get_available_font(fallbacks: list) -> str:
    """Get the first available font from the fallback list."""
    available_families = _get_font_families()

    for font_name in fallbacks:
        if font_name in available_families:
            return font_name

    return fallbacks[-1] if fallbacks else "monospace"


def get_code_font() -> QFont:
    """Get the best available code font."""
    font_name = get_available_font(CODE_FONT_FALLBACKS)
    font = QFont(font_name)
    font.setPointSize(12)
    font.setStyleHint(QFont.StyleHint.Monospace)
    return font


def get_ui_font(size: int = 13) -> QFont:
    """Get the best available UI font."""
    font_name = get_available_font(UI_FONT_FALLBACKS)
    font = QFont(font_name)
    font.setPointSize(size)
    return font

