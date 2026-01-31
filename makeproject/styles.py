"""
Style management for MakeProject.
Loads QSS theme files and manages font fallbacks.
"""

import sys
from pathlib import Path
from functools import lru_cache
from PyQt6.QtGui import QFont, QFontDatabase

from . import library


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

# Default base font sizes (match library defaults)
DEFAULT_UI_FONT_SIZE = 12
DEFAULT_EDITOR_FONT_SIZE = 12


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


# UI Font size offsets from base (12px default)
# These maintain relative sizing when base UI font changes
UI_FONT_SIZE_OFFSETS = {
    "font_size_base": 0,        # 12px - base size
    "font_size_header": 2,      # 14px - panel headers
    "font_size_primary": 3,     # 15px - primary button
    "font_size_title": 4,       # 16px - title label
    "font_size_icon": 4,        # 16px - icon buttons
    "font_size_add_button": 6,  # 18px - add/delete buttons
    "font_size_badge": -2,      # 10px - token badges
    "font_size_reference": -1,  # 11px - reference labels
    "font_size_list_item": 1,   # 13px - list items
    "font_size_input": 1,       # 13px - input fields
}


def _load_qss_raw(theme: str = "dark") -> str:
    """Load raw QSS content from files."""
    base_path = get_resource_path("styles_base.qss")
    theme_path = get_resource_path(f"styles_{theme}.qss")

    parts = []
    if base_path.exists():
        parts.append(base_path.read_text(encoding="utf-8"))
    if theme_path.exists():
        parts.append(theme_path.read_text(encoding="utf-8"))

    if parts:
        return "\n\n".join(parts)

    return ""


def load_qss(theme: str = "dark", ui_font_size: int | None = None) -> str:
    """Load the QSS stylesheet for the given theme with scaled font sizes.
    
    Args:
        theme: "dark" or "light"
        ui_font_size: UI font size in points. If None, uses stored preference.
    """
    if ui_font_size is None:
        ui_font_size = library.get_ui_font_size()
    
    qss = _load_qss_raw(theme)
    
    # Substitute font size placeholders
    for placeholder, offset in UI_FONT_SIZE_OFFSETS.items():
        scaled_size = ui_font_size + offset
        qss = qss.replace("{{" + placeholder + "}}", str(scaled_size))
    
    return qss


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


def get_code_font(size: int | None = None) -> QFont:
    """Get the best available code font for editors.
    
    Args:
        size: Optional font size in points. If None, uses the stored editor preference.
    """
    font_name = get_available_font(CODE_FONT_FALLBACKS)
    font = QFont(font_name)
    if size is None:
        size = library.get_editor_font_size()
    font.setPointSize(size)
    font.setStyleHint(QFont.StyleHint.Monospace)
    return font


def get_scaled_ui_font_size(base_offset: int, ui_font_size: int | None = None) -> int:
    """Get a UI font size scaled relative to the base UI font size.
    
    Args:
        base_offset: The offset from the default base (12pt).
        ui_font_size: Optional base UI font size. If None, uses the stored preference.
    
    Returns:
        The scaled font size maintaining the relative offset.
    """
    if ui_font_size is None:
        ui_font_size = library.get_ui_font_size()
    return ui_font_size + base_offset


def get_ui_font(size: int = 13) -> QFont:
    """Get the best available UI font."""
    font_name = get_available_font(UI_FONT_FALLBACKS)
    font = QFont(font_name)
    font.setPointSize(size)
    return font
