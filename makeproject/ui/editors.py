"""
Editor widgets with shared configuration for the app.
"""

import re
from typing import Optional, Type

from PyQt6.QtCore import Qt

from ..styles import get_code_font
from ..widgets import IndentTextEdit


_METADATA_MARKER = re.compile(r'^\s*#\s*---\s*$')


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
        preamble_newlines: bool = False,
        parent=None,
    ):
        super().__init__(parent, indent_size=indent_size)
        self._preamble_newlines = preamble_newlines
        self._dark_mode = dark_mode
        self.setFont(get_code_font())
        self.setPlaceholderText(placeholder)
        self._highlighter = None
        if highlighter_cls:
            self._highlighter = highlighter_cls(self.document(), dark_mode=dark_mode)
        self.set_dark_mode(dark_mode)

    def set_dark_mode(self, dark_mode):
        self._dark_mode = dark_mode
        super().set_dark_mode(dark_mode)
        if self._highlighter:
            self._highlighter.set_dark_mode(dark_mode)

    def set_highlighter(self, highlighter_cls: Optional[Type]):
        if self._highlighter:
            self._highlighter.setDocument(None)
            self._highlighter = None
        if highlighter_cls:
            self._highlighter = highlighter_cls(self.document(), dark_mode=self._dark_mode)

    def keyPressEvent(self, event):
        if self._preamble_newlines and event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):
            if self._handle_preamble_newline():
                return
        super().keyPressEvent(event)

    def _handle_preamble_newline(self) -> bool:
        cursor = self.textCursor()
        if not self._cursor_in_preamble(cursor):
            return False
        if cursor.hasSelection():
            cursor.removeSelectedText()
        line_text = cursor.block().text()
        leading_ws = line_text[:len(line_text) - len(line_text.lstrip(" \t"))]
        stripped = line_text.lstrip(" \t")
        if stripped.startswith("#"):
            after_hash = stripped[1:]
            inner_indent = ""
            for char in after_hash:
                if char in (" ", "\t"):
                    inner_indent += char
                else:
                    break
            if not inner_indent:
                inner_indent = " "
            prefix = f"{leading_ws}#{inner_indent}"
        else:
            prefix = f"{leading_ws}# "
        cursor.insertText("\n" + prefix)
        return True

    def _cursor_in_preamble(self, cursor) -> bool:
        lines = self.toPlainText().splitlines()
        if not lines:
            return False
        bounds = self._preamble_bounds(lines)
        if not bounds:
            return False
        start, end, has_end = bounds
        line = cursor.blockNumber()
        if has_end:
            return start <= line < end
        return line >= start

    def _preamble_bounds(self, lines):
        index = 0
        while index < len(lines) and not lines[index].strip():
            index += 1
        if index >= len(lines) or not _METADATA_MARKER.match(lines[index]):
            return None
        start_marker = index
        index += 1
        while index < len(lines):
            if _METADATA_MARKER.match(lines[index]):
                return start_marker, index, True
            index += 1
        return start_marker, len(lines), False
