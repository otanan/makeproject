"""
YAML syntax highlighter for the Project YAML editor.
Supports highlighting for:
- YAML keys, file/folder keys, file/folder names
- Strings, numbers, booleans, comments, document markers
- MakeProject tokens {mp:TokenName}
"""

import re
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont


class YAMLHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for YAML with special MakeProject token support."""
    PYTHON_BLOCK_STATE = 1

    def __init__(self, parent=None, dark_mode=True):
        super().__init__(parent)
        self.dark_mode = dark_mode
        self._setup_formats()
        self._setup_rules()
    
    def _setup_formats(self):
        """Set up text formats for different syntax elements."""
        # Color palettes for dark and light modes
        if self.dark_mode:
            colors = {
                'key': '#82AAFF',           # Light blue
                'file_folder_key': '#C792EA',  # Purple
                'file_folder_name': '#FFCB6B', # Yellow/gold
                'string': '#C3E88D',         # Green
                'number': '#F78C6C',         # Orange
                'boolean': '#FF5370',        # Red/pink
                'comment': '#6C7086',        # Muted gray (theme color)
                'document': '#89DDFF',       # Cyan
                'token': '#1ABC9D',          # Teal green (accent)
                'template_key': '#BB80B3',   # Magenta
            }
            python_colors = {
                "keyword": "#C792EA",
                "builtin": "#82AAFF",
                "string": "#C3E88D",
                "number": "#F78C6C",
                "comment": "#6C7086",
            }
        else:
            colors = {
                'key': '#0550AE',           # Dark blue
                'file_folder_key': '#8250DF', # Purple
                'file_folder_name': '#953800', # Brown/orange
                'string': '#0A3069',         # Dark blue-gray
                'number': '#CF222E',         # Red
                'boolean': '#CF222E',        # Red
                'comment': '#9CA3AF',        # Gray (theme color)
                'document': '#0550AE',       # Blue
                'token': '#0D9488',          # Darker teal for light mode
                'template_key': '#8250DF',   # Purple
            }
            python_colors = {
                "keyword": "#8250DF",
                "builtin": "#0550AE",
                "string": "#0A3069",
                "number": "#CF222E",
                "comment": "#9CA3AF",
            }
        
        self.formats = {}
        
        # Regular YAML keys
        self.formats['key'] = self._create_format(colors['key'])
        
        # file/folder/contents keys (special)
        self.formats['file_folder_key'] = self._create_format(colors['file_folder_key'], bold=True)
        
        # File/folder names (values after file: or folder:)
        self.formats['file_folder_name'] = self._create_format(colors['file_folder_name'])
        
        # Strings
        self.formats['string'] = self._create_format(colors['string'])
        
        # Booleans
        self.formats['boolean'] = self._create_format(colors['boolean'], bold=True)
        
        # Comments
        self.formats['comment'] = self._create_format(colors['comment'], italic=True)
        
        # Document markers (---, ...)
        self.formats['document'] = self._create_format(colors['document'])
        
        # Tokens {mp:...}
        self.formats['token'] = self._create_format(colors['token'], bold=True)
        
        # template key
        self.formats['template_key'] = self._create_format(colors['template_key'], bold=True)

        self.python_formats = {
            "keyword": self._create_format(python_colors["keyword"], bold=True),
            "builtin": self._create_format(python_colors["builtin"]),
            "string": self._create_format(python_colors["string"]),
            "number": self._create_format(python_colors["number"]),
            "comment": self._create_format(python_colors["comment"], italic=True),
        }
    
    def _create_format(self, color, bold=False, italic=False):
        """Create a QTextCharFormat with the given properties."""
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        if italic:
            fmt.setFontItalic(True)
        return fmt
    
    def _setup_rules(self):
        """Set up regex patterns for syntax highlighting."""
        self.rules = []
        
        # Document markers: --- or ...
        self.rules.append((re.compile(r'^(---|\.\.\.)\s*$'), 'document'))
        
        # file/folder/contents/template keys (special highlighting)
        self.rules.append((
            re.compile(
                r'^\s*-?\s*(file|folder|contents|content|template|file_template|folder_template|project_template|title|description)\s*:'
            ),
            'file_folder_key'
        ))
        
        # Regular YAML keys
        self.rules.append((re.compile(r'^\s*-?\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:'), 'key'))
        
        # Booleans
        self.rules.append((re.compile(r'\b(true|false|yes|no|on|off|null|~)\b', re.IGNORECASE), 'boolean'))
        
        # Double-quoted strings
        self.rules.append((re.compile(r'"[^"\\]*(\\.[^"\\]*)*"'), 'string'))
        
        # Single-quoted strings
        self.rules.append((re.compile(r"'[^']*'"), 'string'))
        
        # MakeProject tokens {mp:...} and {mp.py:...}
        self.rules.append((re.compile(r'\{mp(?:\.py)?\s*:[^}]+\}', re.IGNORECASE), 'token'))
        self.rules.append((re.compile(r'\{\/mp\.py\s*\}', re.IGNORECASE), 'token'))

        self.python_block_start_re = re.compile(r'\{mp\.py\s*\}', re.IGNORECASE)
        self.python_block_end_re = re.compile(r'\{\/mp\.py\s*\}', re.IGNORECASE)
        self.python_expr_start_re = re.compile(r'\{mp\.py\s*:\s*', re.IGNORECASE)
        keywords = [
            "and", "as", "assert", "async", "await", "break", "class", "continue",
            "def", "del", "elif", "else", "except", "False", "finally", "for",
            "from", "global", "if", "import", "in", "is", "lambda", "None",
            "nonlocal", "not", "or", "pass", "raise", "return", "True", "try",
            "while", "with", "yield",
        ]
        builtins = [
            "print", "len", "range", "dict", "list", "set", "tuple", "str",
            "int", "float", "bool", "min", "max", "sum", "zip", "map", "filter",
            "sorted", "enumerate", "any", "all",
        ]
        self.python_rules = [
            (re.compile(r'"""[^"\\]*(\\.[^"\\]*)*"""'), "string"),
            (re.compile(r"'''[^'\\]*(\\.[^'\\]*)*'''"), "string"),
            (re.compile(r"\"[^\"\\]*(\\.[^\"\\]*)*\""), "string"),
            (re.compile(r"'[^'\\]*(\\.[^'\\]*)*'"), "string"),
            (re.compile(r"\b\d+(\.\d+)?\b"), "number"),
            (re.compile(r"\b(" + "|".join(keywords) + r")\b"), "keyword"),
            (re.compile(r"\b(" + "|".join(builtins) + r")\b"), "builtin"),
            (re.compile(r"#.*$"), "comment"),
        ]

    def _comment_start(self, text):
        """Return the index of a comment start outside quotes, if any."""
        in_single = False
        in_double = False
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == '\\' and in_double:
                i += 2
                continue
            if ch == '"' and not in_single:
                in_double = not in_double
            elif ch == "'" and not in_double:
                in_single = not in_single
            elif ch == '#' and not in_single and not in_double:
                return i
            i += 1
        return None
    
    def set_dark_mode(self, dark_mode):
        """Update the color scheme for dark/light mode."""
        self.dark_mode = dark_mode
        self._setup_formats()
        self.rehighlight()

    def _collect_python_block_ranges(self, text):
        ranges = []
        token_ranges = []
        idx = 0
        if self.previousBlockState() == self.PYTHON_BLOCK_STATE:
            end_match = self.python_block_end_re.search(text)
            if not end_match:
                ranges.append((0, len(text)))
                self.setCurrentBlockState(self.PYTHON_BLOCK_STATE)
                return ranges, token_ranges
            if end_match.start() > 0:
                ranges.append((0, end_match.start()))
            token_ranges.append((end_match.start(), end_match.end() - end_match.start()))
            idx = end_match.end()
        while True:
            block_match = self.python_block_start_re.search(text, idx)
            expr_match = self.python_expr_start_re.search(text, idx)
            if not block_match and not expr_match:
                break
            if block_match and expr_match:
                if block_match.start() <= expr_match.start():
                    match = block_match
                    is_block = True
                else:
                    match = expr_match
                    is_block = False
            elif block_match:
                match = block_match
                is_block = True
            else:
                match = expr_match
                is_block = False
            token_ranges.append((match.start(), match.end() - match.start()))
            code_start = match.end()
            if is_block:
                end_match = self.python_block_end_re.search(text, code_start)
                if not end_match:
                    if code_start < len(text):
                        ranges.append((code_start, len(text) - code_start))
                    self.setCurrentBlockState(self.PYTHON_BLOCK_STATE)
                    return ranges, token_ranges
                if end_match.start() > code_start:
                    ranges.append((code_start, end_match.start() - code_start))
                token_ranges.append((end_match.start(), end_match.end() - end_match.start()))
                idx = end_match.end()
                continue
            end_idx = text.find("}", code_start)
            if end_idx == -1:
                if code_start < len(text):
                    ranges.append((code_start, len(text) - code_start))
                self.setCurrentBlockState(0)
                return ranges, token_ranges
            if end_idx > code_start:
                ranges.append((code_start, end_idx - code_start))
            token_ranges.append((end_idx, 1))
            idx = end_idx + 1
        self.setCurrentBlockState(0)
        return ranges, token_ranges

    def _apply_python_highlighting(self, text, ranges):
        for start, length in ranges:
            if length <= 0:
                continue
            segment = text[start:start + length]
            for pattern, format_name in self.python_rules:
                for match in pattern.finditer(segment):
                    self.setFormat(
                        start + match.start(),
                        match.end() - match.start(),
                        self.python_formats[format_name],
                    )

    def _apply_python_block_formats(self, text, python_ranges, token_ranges):
        self._apply_python_highlighting(text, python_ranges)
        for start, length in token_ranges:
            if length <= 0:
                continue
            self.setFormat(start, length, self.formats['token'])
    
    def highlightBlock(self, text):
        """Apply syntax highlighting to a block of text."""
        python_ranges, python_token_ranges = self._collect_python_block_ranges(text)
        comment_start = self._comment_start(text)
        handled_special_case = False
        # Special handling for file: and folder: values (file/folder names)
        file_folder_match = re.match(r'^(\s*-?\s*)(file|folder|file_template|folder_template)(\s*:\s*)(.+)$', text)
        if file_folder_match:
            prefix_len = len(file_folder_match.group(1))
            key_start = prefix_len
            key_len = len(file_folder_match.group(2))
            colon_len = len(file_folder_match.group(3))
            value_start = prefix_len + key_len + colon_len
            value = file_folder_match.group(4)
            
            # Highlight the key (file/folder)
            self.setFormat(key_start, key_len, self.formats['file_folder_key'])
            
            # Highlight the value (filename/foldername) - but check for tokens first
            # Strip quotes if present
            value_text = value.strip()
            if value_text.startswith('"') and value_text.endswith('"'):
                value_text = value_text[1:-1]
            elif value_text.startswith("'") and value_text.endswith("'"):
                value_text = value_text[1:-1]
            
            # Apply file/folder name format
            self.setFormat(value_start, len(value), self.formats['file_folder_name'])
            
            # Override with token format for any {mp:...} patterns
            for match in re.finditer(r'\{mp:[^}]+\}', value, re.IGNORECASE):
                self.setFormat(value_start + match.start(), match.end() - match.start(), self.formats['token'])
            handled_special_case = True

        # Implicit folder syntax: - name:
        if not handled_special_case:
            implicit_folder_match = re.match(
                r'^(\s*-\s*)("([^"\\]|\\.)*"|\'([^\'\\]|\\.)*\'|[^:#]+)\s*:\s*(#.*)?$',
                text
            )
            if implicit_folder_match:
                prefix_len = len(implicit_folder_match.group(1))
                key_text = implicit_folder_match.group(2)
                key_len = len(key_text)
                key_value = key_text.strip()
                if (key_value.startswith('"') and key_value.endswith('"')) or (
                    key_value.startswith("'") and key_value.endswith("'")
                ):
                    key_value = key_value[1:-1]
                if key_value.lower() not in (
                    'file', 'folder', 'contents', 'content', 'template', 'file_template',
                    'folder_template', 'project_template', 'title', 'description'
                ):
                    self.setFormat(prefix_len, key_len, self.formats['file_folder_name'])
                    for match in re.finditer(r'\{mp:[^}]+\}', key_text, re.IGNORECASE):
                        self.setFormat(prefix_len + match.start(),
                                      match.end() - match.start(),
                                      self.formats['token'])
                    handled_special_case = True

        # Implicit file syntax: - filename
        if not handled_special_case:
            if re.match(r'^\s*-\s+', text):
                pre_comment = text.split('#', 1)[0]
                if ':' not in pre_comment:
                    implicit_file_match = re.match(
                        r'^(\s*-\s*)("([^"\\]|\\.)*"|\'([^\'\\]|\\.)*\'|[^#]+?)\s*(#.*)?$',
                        text
                    )
                    if implicit_file_match:
                        prefix_len = len(implicit_file_match.group(1))
                        value_text = implicit_file_match.group(2)
                        value_len = len(value_text)
                        self.setFormat(prefix_len, value_len, self.formats['key'])
                        for match in re.finditer(r'\{mp:[^}]+\}', value_text, re.IGNORECASE):
                            self.setFormat(prefix_len + match.start(),
                                          match.end() - match.start(),
                                          self.formats['token'])
                        handled_special_case = True
        
        # Apply standard rules
        if not handled_special_case:
            for pattern, format_name in self.rules:
                if format_name == 'key':
                    # For keys, only highlight the key part, not the colon
                    for match in pattern.finditer(text):
                        # Check if this is not a file/folder/contents key (already handled)
                        key = match.group(1) if match.lastindex else match.group(0)
                        if key.lower() not in (
                            'file', 'folder', 'contents', 'content', 'template', 'file_template',
                            'folder_template', 'project_template', 'title', 'description'
                        ):
                            key_start = match.start(1) if match.lastindex else match.start()
                            key_len = len(key)
                            self.setFormat(key_start, key_len, self.formats[format_name])
                elif format_name == 'file_folder_key':
                    # Highlight just the keyword
                    for match in pattern.finditer(text):
                        # Find the keyword position
                        keyword_match = re.search(
                            r'(file|folder|contents|content|template|file_template|folder_template|project_template|title|description)',
                            match.group(),
                            re.IGNORECASE
                        )
                        if keyword_match:
                            self.setFormat(match.start() + keyword_match.start(),
                                         len(keyword_match.group()),
                                         self.formats[format_name])
                else:
                    for match in pattern.finditer(text):
                        self.setFormat(match.start(), match.end() - match.start(), self.formats[format_name])
        self._apply_python_block_formats(text, python_ranges, python_token_ranges)
        if comment_start is not None:
            self.setFormat(comment_start, len(text) - comment_start, self.formats['comment'])


class PythonHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for Python code blocks."""

    TRIPLE_DOUBLE_STATE = 1
    TRIPLE_SINGLE_STATE = 2

    def __init__(self, parent=None, dark_mode=True):
        super().__init__(parent)
        self.dark_mode = dark_mode
        self._setup_formats()
        self._setup_rules()

    def _setup_formats(self):
        if self.dark_mode:
            colors = {
                "keyword": "#C792EA",
                "builtin": "#82AAFF",
                "string": "#C3E88D",
                "number": "#F78C6C",
                "comment": "#6C7086",
            }
        else:
            colors = {
                "keyword": "#8250DF",
                "builtin": "#0550AE",
                "string": "#0A3069",
                "number": "#CF222E",
                "comment": "#9CA3AF",
            }

        self.formats = {
            "keyword": self._create_format(colors["keyword"], bold=True),
            "builtin": self._create_format(colors["builtin"]),
            "string": self._create_format(colors["string"]),
            "number": self._create_format(colors["number"]),
            "comment": self._create_format(colors["comment"], italic=True),
        }

    def _create_format(self, color, bold=False, italic=False):
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        if italic:
            fmt.setFontItalic(True)
        return fmt

    def _setup_rules(self):
        keywords = [
            "and", "as", "assert", "async", "await", "break", "class", "continue",
            "def", "del", "elif", "else", "except", "False", "finally", "for",
            "from", "global", "if", "import", "in", "is", "lambda", "None",
            "nonlocal", "not", "or", "pass", "raise", "return", "True", "try",
            "while", "with", "yield",
        ]
        builtins = [
            "print", "len", "range", "dict", "list", "set", "tuple", "str",
            "int", "float", "bool", "min", "max", "sum", "zip", "map", "filter",
            "sorted", "enumerate", "any", "all",
        ]

        self.rules = [
            (re.compile(r'"""[^"\\]*(\\.[^"\\]*)*"""'), "string"),
            (re.compile(r"'''[^'\\]*(\\.[^'\\]*)*'''"), "string"),
            (re.compile(r"\"[^\"\\]*(\\.[^\"\\]*)*\""), "string"),
            (re.compile(r"'[^'\\]*(\\.[^'\\]*)*'"), "string"),
            (re.compile(r"\b\d+(\.\d+)?\b"), "number"),
            (re.compile(r"\b(" + "|".join(keywords) + r")\b"), "keyword"),
            (re.compile(r"\b(" + "|".join(builtins) + r")\b"), "builtin"),
            (re.compile(r"#.*$"), "comment"),
        ]

    def set_dark_mode(self, dark_mode):
        self.dark_mode = dark_mode
        self._setup_formats()
        self.rehighlight()

    def _collect_triple_quote_ranges(self, text):
        ranges = []
        idx = 0
        state = self.previousBlockState()
        if state in (self.TRIPLE_DOUBLE_STATE, self.TRIPLE_SINGLE_STATE):
            quote = '"""' if state == self.TRIPLE_DOUBLE_STATE else "'''"
            end_idx = text.find(quote)
            if end_idx == -1:
                ranges.append((0, len(text)))
                self.setCurrentBlockState(state)
                return ranges
            ranges.append((0, end_idx + 3))
            idx = end_idx + 3
        while True:
            next_double = text.find('"""', idx)
            next_single = text.find("'''", idx)
            if next_double == -1 and next_single == -1:
                break
            if next_double != -1 and (next_single == -1 or next_double < next_single):
                quote = '"""'
                state = self.TRIPLE_DOUBLE_STATE
                start_idx = next_double
            else:
                quote = "'''"
                state = self.TRIPLE_SINGLE_STATE
                start_idx = next_single
            end_idx = text.find(quote, start_idx + 3)
            if end_idx == -1:
                ranges.append((start_idx, len(text) - start_idx))
                self.setCurrentBlockState(state)
                return ranges
            ranges.append((start_idx, end_idx + 3 - start_idx))
            idx = end_idx + 3
        self.setCurrentBlockState(0)
        return ranges

    def highlightBlock(self, text):
        triple_ranges = self._collect_triple_quote_ranges(text)
        for pattern, format_name in self.rules:
            for match in pattern.finditer(text):
                self.setFormat(
                    match.start(),
                    match.end() - match.start(),
                    self.formats[format_name],
                )
        for start, length in triple_ranges:
            if length > 0:
                self.setFormat(start, length, self.formats["string"])
