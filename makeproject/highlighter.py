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
        
        # Comments: # ...
        self.rules.append((re.compile(r'#.*$'), 'comment'))
        
        # file/folder/contents/template keys (special highlighting)
        self.rules.append((re.compile(r'^\s*-?\s*(file|folder|contents|content|template|project_template)\s*:'), 'file_folder_key'))
        
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
    
    def set_dark_mode(self, dark_mode):
        """Update the color scheme for dark/light mode."""
        self.dark_mode = dark_mode
        self._setup_formats()
        self.rehighlight()
    
    def highlightBlock(self, text):
        """Apply syntax highlighting to a block of text."""
        # Special handling for file: and folder: values (file/folder names)
        file_folder_match = re.match(r'^(\s*-?\s*)(file|folder)(\s*:\s*)(.+)$', text)
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
            
            # Still apply comment highlighting if there's a comment
            comment_match = re.search(r'#.*$', text)
            if comment_match:
                self.setFormat(comment_match.start(), len(comment_match.group()), self.formats['comment'])
            return

        # Implicit folder syntax: - name:
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
                'file', 'folder', 'contents', 'content', 'template', 'project_template'
            ):
                self.setFormat(prefix_len, key_len, self.formats['file_folder_name'])
                for match in re.finditer(r'\{mp:[^}]+\}', key_text, re.IGNORECASE):
                    self.setFormat(prefix_len + match.start(),
                                  match.end() - match.start(),
                                  self.formats['token'])
                comment_match = re.search(r'#.*$', text)
                if comment_match:
                    self.setFormat(comment_match.start(), len(comment_match.group()), self.formats['comment'])
                return

        # Implicit file syntax: - filename
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
                    self.setFormat(prefix_len, value_len, self.formats['file_folder_name'])
                    for match in re.finditer(r'\{mp:[^}]+\}', value_text, re.IGNORECASE):
                        self.setFormat(prefix_len + match.start(),
                                      match.end() - match.start(),
                                      self.formats['token'])
                    comment_match = re.search(r'#.*$', text)
                    if comment_match:
                        self.setFormat(comment_match.start(), len(comment_match.group()), self.formats['comment'])
                    return
        
        # Apply standard rules
        for pattern, format_name in self.rules:
            if format_name == 'key':
                # For keys, only highlight the key part, not the colon
                for match in pattern.finditer(text):
                    # Check if this is not a file/folder/contents key (already handled)
                    key = match.group(1) if match.lastindex else match.group(0)
                    if key.lower() not in ('file', 'folder', 'contents', 'content', 'template', 'project_template'):
                        key_start = match.start(1) if match.lastindex else match.start()
                        key_len = len(key)
                        self.setFormat(key_start, key_len, self.formats[format_name])
            elif format_name == 'file_folder_key':
                # Highlight just the keyword
                for match in pattern.finditer(text):
                    # Find the keyword position
                    keyword_match = re.search(
                        r'(file|folder|contents|content|template|project_template)',
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
