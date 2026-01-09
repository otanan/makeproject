"""
Custom widgets for MakeProject.
- ToggleSwitch: Custom dark mode toggle
- IndentTextEdit: Text editor with line numbers, indent preservation, tab-to-spaces
- LineNumberArea: Line number gutter for the editor
"""

from PyQt6.QtCore import Qt, QRect, QSize, pyqtSignal, QPropertyAnimation, QEasingCurve, pyqtProperty, QTimer
from PyQt6.QtGui import QPainter, QColor, QTextCursor, QKeyEvent, QTextFormat
from PyQt6.QtWidgets import (
    QWidget, QPlainTextEdit, QTextEdit, QFrame, QLabel
)


class ToggleSwitch(QWidget):
    """Custom toggle switch widget for dark/light mode."""
    
    toggled = pyqtSignal(bool)
    
    def __init__(self, parent=None, checked=True):
        super().__init__(parent)
        self._checked = checked
        self._thumb_position = 1.0 if checked else 0.0
        
        self.setFixedSize(44, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Animation for smooth toggle
        self._animation = QPropertyAnimation(self, b"thumbPosition", self)
        self._animation.setDuration(150)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
    
    def get_thumb_position(self):
        return self._thumb_position
    
    def set_thumb_position(self, pos):
        self._thumb_position = pos
        self.update()
    
    thumbPosition = pyqtProperty(float, get_thumb_position, set_thumb_position)
    
    def isChecked(self):
        return self._checked
    
    def setChecked(self, checked):
        if self._checked != checked:
            self._checked = checked
            self._animate_toggle()
            self.toggled.emit(checked)
    
    def _animate_toggle(self):
        self._animation.stop()
        self._animation.setStartValue(self._thumb_position)
        self._animation.setEndValue(1.0 if self._checked else 0.0)
        self._animation.start()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Track
        track_rect = self.rect().adjusted(2, 4, -2, -4)
        track_radius = track_rect.height() / 2
        
        if self._checked:
            track_color = QColor("#4CAF50")  # Green when on (dark mode)
        else:
            track_color = QColor("#9E9E9E")  # Gray when off
        
        painter.setBrush(track_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(track_rect, track_radius, track_radius)
        
        # Thumb
        thumb_radius = 8
        thumb_margin = 4
        track_width = self.width() - thumb_margin * 2 - thumb_radius * 2
        thumb_x = thumb_margin + thumb_radius + (track_width * self._thumb_position)
        thumb_y = self.height() / 2
        
        # Thumb shadow
        shadow_color = QColor(0, 0, 0, 40)
        painter.setBrush(shadow_color)
        painter.drawEllipse(int(thumb_x - thumb_radius + 1), int(thumb_y - thumb_radius + 1), 
                          thumb_radius * 2, thumb_radius * 2)
        
        # Thumb
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(int(thumb_x - thumb_radius), int(thumb_y - thumb_radius), 
                          thumb_radius * 2, thumb_radius * 2)


class LineNumberArea(QWidget):
    """Line number gutter for the code editor."""
    
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
    
    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)
    
    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)


class IndentTextEdit(QPlainTextEdit):
    """
    Text editor with:
    - Line numbers in a slim gutter
    - Tab key inserts spaces
    - Newline preserves current line indentation
    - No line wrapping (for accurate line numbers)
    """
    
    def __init__(self, parent=None, indent_size: int = 2):
        super().__init__(parent)
        
        self.line_number_area = LineNumberArea(self)
        self._indent_size = max(1, indent_size)
        self._placeholder_text = ""
        self._placeholder_label = QLabel(self.viewport())
        self._placeholder_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._placeholder_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._placeholder_label.setWordWrap(True)
        self._placeholder_label.hide()
        
        # Theme colors (updated by set_dark_mode)
        self._dark_mode = True
        self._gutter_bg = QColor("#1E1E2E")
        self._gutter_fg = QColor("#6C7086")
        self._current_line_fg = QColor("#CDD6F4")
        self._error_badge_bg = QColor("#FF5C5C")
        self._error_line = None
        
        # Disable line wrapping for accurate line numbers
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.horizontalScrollBar().valueChanged.connect(self._clamp_empty_scroll)
        self.verticalScrollBar().valueChanged.connect(self._clamp_empty_scroll)
        
        # Connect signals
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.textChanged.connect(self._schedule_empty_scroll_reset)
        self.textChanged.connect(self._update_placeholder_visibility)
        
        self.update_line_number_area_width(0)
        self.highlight_current_line()
        self._update_placeholder_style()
    
    def set_dark_mode(self, dark_mode):
        """Update gutter colors and current line highlight for dark/light mode."""
        self._dark_mode = dark_mode
        if dark_mode:
            self._gutter_bg = QColor("#1E1E2E")
            self._gutter_fg = QColor("#6C7086")
            self._current_line_fg = QColor("#CDD6F4")
        else:
            self._gutter_bg = QColor("#F5F5F5")
            self._gutter_fg = QColor("#999999")
            self._current_line_fg = QColor("#333333")
        self._update_placeholder_style()
        self.update()
        self.line_number_area.update()
        # Re-apply current line highlight with new theme colors
        self.highlight_current_line()
    
    def line_number_area_width(self):
        """Calculate the width needed for line numbers."""
        digits = len(str(max(1, self.blockCount())))
        # Minimum 3 digits width, with padding
        digits = max(3, digits)
        space = 8 + self.fontMetrics().horizontalAdvance('9') * digits + 8
        return space
    
    def update_line_number_area_width(self, _):
        """Update the viewport margins to make room for line numbers."""
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
    
    def update_line_number_area(self, rect, dy):
        """Scroll the line number area when the editor scrolls."""
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), 
                                        self.line_number_area.width(), 
                                        rect.height())
        
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)
    
    def resizeEvent(self, event):
        """Handle resize to adjust line number area."""
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(),
                                                self.line_number_area_width(), 
                                                cr.height()))
        self._position_placeholder()

    def showEvent(self, event):
        """Ensure placeholder visibility updates when the editor becomes visible."""
        super().showEvent(event)
        self._update_placeholder_visibility()
    
    def line_number_area_paint_event(self, event):
        """Paint the line numbers in the gutter."""
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), self._gutter_bg)

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        current_block = self.textCursor().block().blockNumber()
        highlight_active = self.hasFocus() and not self.isReadOnly()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                is_error_line = self._error_line == block_number + 1

                if is_error_line:
                    badge_radius = 5
                    badge_x = 8
                    badge_y = top + (self.fontMetrics().height() // 2)
                    painter.setBrush(self._error_badge_bg)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(
                        badge_x - badge_radius,
                        badge_y - badge_radius,
                        badge_radius * 2,
                        badge_radius * 2,
                    )

                if highlight_active and block_number == current_block:
                    painter.setPen(self._current_line_fg)
                else:
                    painter.setPen(self._gutter_fg)
                
                painter.drawText(0, top,
                               self.line_number_area.width() - 8,
                               self.fontMetrics().height(),
                               Qt.AlignmentFlag.AlignRight,
                               number)
            
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1
    
    def highlight_current_line(self):
        """Highlight the current line with a subtle background."""
        extra_selections = []

        if not self.isReadOnly() and self.hasFocus():
            selection = QTextEdit.ExtraSelection()
            
            if self._dark_mode:
                line_color = QColor("#2A2A3E")
            else:
                line_color = QColor("#E8E8E8")
            
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        
        self.setExtraSelections(extra_selections)

        self.line_number_area.update()

    def set_error_line(self, line: int | None):
        if line is not None and line < 1:
            line = None
        if self._error_line == line:
            return
        self._error_line = line
        self.line_number_area.update()
    
    def keyPressEvent(self, event: QKeyEvent):
        """Handle special key presses: Tab, Enter, Cmd+Delete, Cmd+/, Cmd+[, Cmd+]."""
        modifiers = event.modifiers()
        is_cmd = modifiers & Qt.KeyboardModifier.ControlModifier  # Cmd on macOS maps to Control
        
        # Cmd+Backspace - delete to start of line (content to the left of cursor)
        if is_cmd and event.key() == Qt.Key.Key_Backspace:
            self._delete_to_line_start()
            return
        
        # Cmd+Delete - delete to end of line (content to the right of cursor)
        if is_cmd and event.key() == Qt.Key.Key_Delete:
            self._delete_to_line_end()
            return
        
        # Cmd+/ - toggle comment
        if is_cmd and event.key() == Qt.Key.Key_Slash:
            self._toggle_comment()
            return
        
        # Cmd+[ - unindent (remove spaces from start)
        if is_cmd and event.key() == Qt.Key.Key_BracketLeft:
            self._unindent_line()
            return
        
        # Cmd+] - indent (add spaces to start)
        if is_cmd and event.key() == Qt.Key.Key_BracketRight:
            self._indent_line()
            return
        
        # Tab - insert spaces (match previous indent on blank line)
        if event.key() == Qt.Key.Key_Tab:
            if self._handle_tab_indent():
                return
            self.insertPlainText(" " * self._indent_size)
            return
        
        # Shift+Tab - unindent
        if event.key() == Qt.Key.Key_Backtab:
            self._unindent_line()
            return

        # Left/Right - treat indentation spaces as tab stops
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            if self._handle_indent_navigation(event):
                return
        
        # Enter - preserve current line indentation
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            cursor = self.textCursor()
            current_line = cursor.block().text()
            
            # Extract leading whitespace
            indent = ""
            for char in current_line:
                if char in (' ', '\t'):
                    indent += char
                else:
                    break
            
            # Insert newline with same indentation
            cursor.insertText('\n' + indent)
            return
        
        super().keyPressEvent(event)

    def setPlaceholderText(self, text: str):
        self._placeholder_text = text or ""
        QPlainTextEdit.setPlaceholderText(self, "")
        self._update_placeholder_visibility()

    def setPlainText(self, text: str):
        super().setPlainText(text)
        self._update_placeholder_visibility()

    def _update_placeholder_style(self):
        color = "#6C7086" if self._dark_mode else "#9CA3AF"
        self._placeholder_label.setStyleSheet(f"color: {color};")
        self._placeholder_label.setFont(self.font())

    def _update_placeholder_visibility(self):
        show = bool(self._placeholder_text) and not self.toPlainText().strip()
        self._placeholder_label.setVisible(show)
        if show:
            QTimer.singleShot(0, self._position_placeholder)

    def _position_placeholder(self):
        if not self._placeholder_text:
            return
        margin = 8
        available = max(1, self.viewport().width() - (margin * 2))
        height = max(1, self.viewport().height() - (margin * 2))
        self._placeholder_label.setText(self._placeholder_text)
        self._placeholder_label.setGeometry(
            margin,
            margin,
            available,
            height
        )

    def showEvent(self, event):
        super().showEvent(event)
        self._reset_scroll_if_empty()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._reset_scroll_if_empty()
        self.highlight_current_line()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.highlight_current_line()

    def _reset_scroll_if_empty(self):
        if self.toPlainText():
            return
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.setTextCursor(cursor)
        self.horizontalScrollBar().setValue(0)
        self.verticalScrollBar().setValue(0)

    def _schedule_empty_scroll_reset(self):
        if self.toPlainText():
            return
        QTimer.singleShot(0, self._reset_scroll_if_empty)

    def _clamp_empty_scroll(self):
        if self.toPlainText():
            return
        h_scroll = self.horizontalScrollBar()
        v_scroll = self.verticalScrollBar()
        if h_scroll.value() != 0:
            h_scroll.blockSignals(True)
            h_scroll.setValue(0)
            h_scroll.blockSignals(False)
        if v_scroll.value() != 0:
            v_scroll.blockSignals(True)
            v_scroll.setValue(0)
            v_scroll.blockSignals(False)

    def _handle_indent_navigation(self, event: QKeyEvent) -> bool:
        key = event.key()
        modifiers = event.modifiers()
        if modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier):
            return False
        step = self._indent_size
        cursor = self.textCursor()
        line_text = cursor.block().text()
        pos = cursor.positionInBlock()
        leading_spaces = 0
        for char in line_text:
            if char == ' ':
                leading_spaces += 1
            else:
                break
        if pos > leading_spaces:
            return False
        if key == Qt.Key.Key_Left:
            if pos == 0:
                return False
            delta = step if pos % step == 0 else pos % step
            new_pos = pos - delta
            new_pos = max(0, new_pos)
        elif key == Qt.Key.Key_Right:
            if pos >= leading_spaces:
                return False
            delta = step if pos % step == 0 else (step - (pos % step))
            new_pos = pos + delta
            new_pos = min(leading_spaces, new_pos)
        else:
            return False
        if new_pos == pos:
            return False
        move_mode = QTextCursor.MoveMode.KeepAnchor if modifiers & Qt.KeyboardModifier.ShiftModifier else QTextCursor.MoveMode.MoveAnchor
        direction = QTextCursor.MoveOperation.Right if new_pos > pos else QTextCursor.MoveOperation.Left
        cursor.movePosition(direction, move_mode, abs(new_pos - pos))
        self.setTextCursor(cursor)
        return True

    def _handle_tab_indent(self) -> bool:
        cursor = self.textCursor()
        line_text = cursor.block().text()
        pos = cursor.positionInBlock()
        if line_text.strip():
            return False
        if pos > len(line_text):
            return False
        # Match indentation of previous line if this line is empty/whitespace.
        prev_block = cursor.block().previous()
        if not prev_block.isValid():
            return False
        prev_text = prev_block.text()
        prev_indent = ""
        for char in prev_text:
            if char == ' ':
                prev_indent += char
            else:
                break
        current_indent = 0
        for char in line_text:
            if char == ' ':
                current_indent += 1
            else:
                break
        if pos > current_indent or len(prev_indent) <= current_indent:
            return False
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(prev_indent)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.MoveAnchor, len(prev_indent))
        self.setTextCursor(cursor)
        return True
    
    def _delete_to_line_start(self):
        """Delete content from cursor to start of line (preserves newline)."""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        self.setTextCursor(cursor)
    
    def _delete_to_line_end(self):
        """Delete content from cursor to end of line (preserves newline)."""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        self.setTextCursor(cursor)
    
    def _toggle_comment(self):
        """Toggle YAML comment (# ) on selected lines or current line."""
        cursor = self.textCursor()
        
        # Check if there's a selection spanning multiple lines
        if cursor.hasSelection():
            start = cursor.selectionStart()
            end = cursor.selectionEnd()
            
            # Get the block (line) numbers
            cursor.setPosition(start)
            start_block = cursor.blockNumber()
            cursor.setPosition(end)
            end_block = cursor.blockNumber()
            
            # If selection ends at start of a line, don't include that line
            if cursor.positionInBlock() == 0 and end_block > start_block:
                end_block -= 1
            
            # Process multiple lines
            if end_block > start_block:
                self._toggle_comment_lines(start_block, end_block)
                return
        
        # Single line toggle
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
        line_text = cursor.selectedText()
        
        new_text = self._toggle_line_comment(line_text)
        cursor.insertText(new_text)
        self.setTextCursor(cursor)
    
    def _toggle_line_comment(self, line_text: str) -> str:
        """Toggle comment on a single line of text."""
        stripped = line_text.lstrip()
        leading_whitespace = line_text[:len(line_text) - len(stripped)]
        
        if stripped.startswith('# '):
            # Uncomment: remove '# '
            return leading_whitespace + stripped[2:]
        elif stripped.startswith('#'):
            # Uncomment: remove '#'
            return leading_whitespace + stripped[1:]
        else:
            # Comment: add '# '
            return leading_whitespace + '# ' + stripped
    
    def _toggle_comment_lines(self, start_block: int, end_block: int):
        """Toggle comments on multiple lines, preserving selection."""
        cursor = self.textCursor()
        
        # Begin edit block for undo
        cursor.beginEditBlock()
        
        # Collect all lines first to determine if we should comment or uncomment
        lines = []
        cursor.setPosition(0)
        for _ in range(start_block):
            cursor.movePosition(QTextCursor.MoveOperation.NextBlock)
        
        for i in range(start_block, end_block + 1):
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
            lines.append(cursor.selectedText())
            if i < end_block:
                cursor.movePosition(QTextCursor.MoveOperation.NextBlock)
        
        # Check if majority of non-empty lines are commented
        non_empty_lines = [l for l in lines if l.strip()]
        if non_empty_lines:
            commented_count = sum(1 for l in non_empty_lines if l.lstrip().startswith('#'))
            should_uncomment = commented_count > len(non_empty_lines) / 2
        else:
            should_uncomment = False
        
        # Go back to start and apply changes
        cursor.setPosition(0)
        for _ in range(start_block):
            cursor.movePosition(QTextCursor.MoveOperation.NextBlock)
        
        # Remember start position for reselection
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        selection_start = cursor.position()
        
        for i, line_text in enumerate(lines):
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
            
            if should_uncomment:
                new_text = self._uncomment_line(line_text)
            else:
                new_text = self._comment_line(line_text)
            
            cursor.insertText(new_text)
            
            if i < len(lines) - 1:
                cursor.movePosition(QTextCursor.MoveOperation.NextBlock)
        
        # Get end position for reselection
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
        selection_end = cursor.position()
        
        cursor.endEditBlock()
        
        # Restore selection
        cursor.setPosition(selection_start)
        cursor.setPosition(selection_end, QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(cursor)

    def _selected_block_range(self) -> tuple[int, int] | None:
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return None
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        temp = QTextCursor(self.document())
        temp.setPosition(start)
        start_block = temp.blockNumber()
        temp.setPosition(end)
        end_block = temp.blockNumber()
        if temp.positionInBlock() == 0 and end_block > start_block:
            end_block -= 1
        if end_block <= start_block:
            return None
        return start_block, end_block
    
    def _comment_line(self, line_text: str) -> str:
        """Add comment to a line."""
        stripped = line_text.lstrip()
        leading_whitespace = line_text[:len(line_text) - len(stripped)]
        if stripped.startswith('#'):
            return line_text  # Already commented
        return leading_whitespace + '# ' + stripped
    
    def _uncomment_line(self, line_text: str) -> str:
        """Remove comment from a line."""
        stripped = line_text.lstrip()
        leading_whitespace = line_text[:len(line_text) - len(stripped)]
        if stripped.startswith('# '):
            return leading_whitespace + stripped[2:]
        elif stripped.startswith('#'):
            return leading_whitespace + stripped[1:]
        return line_text  # Not commented
    
    def _indent_line(self):
        """Add indentation spaces to the beginning of the current line."""
        block_range = self._selected_block_range()
        if block_range:
            start_block, end_block = block_range
            cursor = self.textCursor()
            cursor.beginEditBlock()

            cursor.setPosition(0)
            for _ in range(start_block):
                cursor.movePosition(QTextCursor.MoveOperation.NextBlock)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            selection_start = cursor.position()

            for i in range(start_block, end_block + 1):
                cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                cursor.insertText(" " * self._indent_size)
                if i < end_block:
                    cursor.movePosition(QTextCursor.MoveOperation.NextBlock)

            cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
            selection_end = cursor.position()
            cursor.endEditBlock()

            cursor.setPosition(selection_start)
            cursor.setPosition(selection_end, QTextCursor.MoveMode.KeepAnchor)
            self.setTextCursor(cursor)
            return

        cursor = self.textCursor()
        line_text = cursor.block().text()
        if not line_text.strip():
            prev_block = cursor.block().previous()
            if prev_block.isValid():
                prev_text = prev_block.text()
                prev_indent = ""
                for char in prev_text:
                    if char == ' ':
                        prev_indent += char
                    else:
                        break
                current_indent = 0
                for char in line_text:
                    if char == ' ':
                        current_indent += 1
                    else:
                        break
                if len(prev_indent) > current_indent:
                    cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                    cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
                    cursor.removeSelectedText()
                    cursor.insertText(prev_indent)
                    cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                    cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.MoveAnchor, len(prev_indent))
                    self.setTextCursor(cursor)
                    return
        
        # Save cursor position within line
        pos_in_line = cursor.positionInBlock()
        
        # Move to start of line and insert spaces
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.insertText(" " * self._indent_size)
        
        # Restore cursor position (adjusted for added spaces)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(
            QTextCursor.MoveOperation.Right,
            QTextCursor.MoveMode.MoveAnchor,
            pos_in_line + self._indent_size
        )
        self.setTextCursor(cursor)
    
    def _unindent_line(self):
        """Remove up to one indentation level from the beginning of the current line."""
        block_range = self._selected_block_range()
        if block_range:
            start_block, end_block = block_range
            cursor = self.textCursor()
            cursor.beginEditBlock()

            cursor.setPosition(0)
            for _ in range(start_block):
                cursor.movePosition(QTextCursor.MoveOperation.NextBlock)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            selection_start = cursor.position()

            for i in range(start_block, end_block + 1):
                cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
                line_text = cursor.selectedText()
                remove_count = 0
                for char in line_text:
                    if char == ' ' and remove_count < self._indent_size:
                        remove_count += 1
                    else:
                        break
                if remove_count > 0:
                    cursor.insertText(line_text[remove_count:])
                else:
                    cursor.clearSelection()
                if i < end_block:
                    cursor.movePosition(QTextCursor.MoveOperation.NextBlock)

            cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
            selection_end = cursor.position()
            cursor.endEditBlock()

            cursor.setPosition(selection_start)
            cursor.setPosition(selection_end, QTextCursor.MoveMode.KeepAnchor)
            self.setTextCursor(cursor)
            return

        cursor = self.textCursor()
        
        # Save cursor position within line
        pos_in_line = cursor.positionInBlock()
        
        # Get line text
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
        line_text = cursor.selectedText()
        
        # Count leading spaces to remove (up to indent size)
        remove_count = 0
        for char in line_text:
            if char == ' ' and remove_count < self._indent_size:
                remove_count += 1
            else:
                break
        
        if remove_count > 0:
            # Remove the whitespace
            new_text = line_text[remove_count:]
            cursor.insertText(new_text)
            
            # Restore cursor position (adjusted for removed whitespace)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            new_pos = max(0, pos_in_line - remove_count)
            cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.MoveAnchor, new_pos)
            self.setTextCursor(cursor)


class ClickableFrame(QFrame):
    """A QFrame that emits clicked signal."""
    
    clicked = pyqtSignal()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
