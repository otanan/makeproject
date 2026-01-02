"""
Editor widgets with shared configuration for the app.
"""

from typing import Optional, Type

from ..styles import get_code_font
from ..widgets import IndentTextEdit


class CodeEditor(IndentTextEdit):
    """
    Indented text editor configured with a code font and optional highlighter.
    """

    def __init__(
        self,
        *,
        indent_size: int,
        placeholder: str,
        highlighter_cls: Optional[Type] = None,
        dark_mode: bool = True,
        parent=None,
    ):
        super().__init__(parent, indent_size=indent_size)
        self.setFont(get_code_font())
        self.setPlaceholderText(placeholder)
        self._highlighter = None
        if highlighter_cls:
            self._highlighter = highlighter_cls(self.document(), dark_mode=dark_mode)

    def set_dark_mode(self, dark_mode):
        super().set_dark_mode(dark_mode)
        if self._highlighter:
            self._highlighter.set_dark_mode(dark_mode)
