"""
Template engine for MakeProject.
Handles YAML parsing, token substitution, and file tree generation.
"""

import re
import os
import shutil
import io
import textwrap
from contextlib import redirect_stdout
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
import yaml

from . import library


@dataclass
class FileNode:
    """Represents a file in the project tree."""
    name: str
    content: str = ""
    is_folder: bool = False
    children: List['FileNode'] = field(default_factory=list)
    source_template: str | None = None
    
    def file_count(self) -> int:
        """Count total files (not folders) in this subtree."""
        if not self.is_folder:
            return 1
        return sum(child.file_count() for child in self.children)


class TokenContext(dict):
    """Dictionary wrapper that carries python token definitions."""

    def __init__(self, *args, python_tokens=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.python_tokens = python_tokens or {}


class YAMLParseError(Exception):
    """Exception for YAML parsing errors with line numbers."""
    def __init__(
        self,
        message: str,
        line: int = None,
        template_name: str | None = None,
        template_line: int | None = None,
    ):
        self.line = line
        self.template_name = template_name
        self.template_line = template_line
        self.message = message
        if template_name and template_line:
            super().__init__(
                f'{message} (template "{template_name}", line {template_line})'
            )
        elif line:
            super().__init__(f"{message} (line {line})")
        else:
            super().__init__(message)


def _normalize_implicit_token_keys(text: str) -> str:
    """Quote implicit folder keys that are token placeholders (e.g., - {mp:title}:)."""
    lines = []
    token_line = re.compile(
        r'^(\s*-\s*)\{([mM][pP]\s*:[^}]+)\}(\s*:\s*)(.*)$'
    )
    for line in text.splitlines():
        match = token_line.match(line)
        if match:
            prefix, token, sep, rest = match.groups()
            lines.append(f'{prefix}"{{{token.strip()}}}"{sep}{rest}')
        else:
            lines.append(line)
    return "\n".join(lines)


def _normalize_implicit_token_items(text: str) -> str:
    """Quote implicit file items that start with a token placeholder."""
    lines = []
    token_item = re.compile(
        r'^(\s*-\s*)(\{[mM][pP]\s*:[^}]+\}[^#]*?)(\s*(?:#.*)?)$'
    )
    token_key = re.compile(
        r'^\s*-\s*\{[mM][pP]\s*:[^}]+\}\s*:\s*(#.*)?$'
    )
    for line in text.splitlines():
        if token_key.match(line):
            lines.append(line)
            continue
        match = token_item.match(line)
        if match:
            prefix, value, suffix = match.groups()
            stripped = value.strip()
            if stripped.startswith(('"', "'")):
                lines.append(line)
                continue
            escaped = stripped.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{prefix}"{escaped}"{suffix}')
        else:
            lines.append(line)
    return "\n".join(lines)


def preprocess_yaml(text: str) -> str:
    """Preprocess YAML text: convert tabs to 2 spaces."""
    text = text.replace('\t', '  ')
    text = _normalize_implicit_token_keys(text)
    return _normalize_implicit_token_items(text)


def parse_yaml(text: str) -> Tuple[Optional[Dict], Optional[str]]:
    """
    Parse YAML text with tab preprocessing.
    Returns (data, None) on success or (None, error_message) on failure.
    """
    try:
        processed = preprocess_yaml(text)
        data = yaml.safe_load(processed)
        return data, None
    except yaml.YAMLError as e:
        # Extract line number from YAML error
        line = None
        if hasattr(e, 'problem_mark') and e.problem_mark:
            line = e.problem_mark.line + 1
        
        if line:
            return None, f"Invalid YAML on line {line}"
    return None, f"Invalid YAML: {str(e)}"


def _extract_error_line(message: str) -> int | None:
    match = re.search(r'line\s+(\d+)', message, re.IGNORECASE)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def _find_token_line_in_text(text: str, token_name: str) -> int | None:
    if not token_name:
        return None
    token_re = re.compile(
        r'\{[mM][pP]\s*:\s*[^}]*\b' + re.escape(token_name) + r'\b',
        re.IGNORECASE,
    )
    alt_re = re.compile(
        r'\bmp\s*:\s*' + re.escape(token_name) + r'\b',
        re.IGNORECASE,
    )
    for index, line in enumerate(text.splitlines(), start=1):
        if token_re.search(line) or alt_re.search(line):
            return index
    return None


def _find_key_line_in_text(text: str, key: str) -> int | None:
    if not key:
        return None
    token_match = re.search(r'[mM][pP]\s*:\s*([^\}\s]+)', key)
    if token_match:
        token_line = _find_token_line_in_text(text, token_match.group(1))
        if token_line:
            return token_line
    for index, line in enumerate(text.splitlines(), start=1):
        if key in line:
            return index
    return None


def _decorate_template_error(
    exc: Exception,
    template_name: str,
    template_text: str,
    template_kind: str,
) -> YAMLParseError:
    if not isinstance(exc, YAMLParseError):
        return YAMLParseError(
            str(exc),
            template_name=template_name,
            template_line=None,
        )
    if exc.template_name:
        return exc

    message = exc.message
    template_line = None

    token_match = re.search(r'Unknown token "([^"]+)"', message)
    if token_match:
        token_name = token_match.group(1)
        template_line = _find_token_line_in_text(template_text, token_name)
        message = f'Unknown token "{token_name}" in {template_kind} "{template_name}".'
    else:
        shorthand_match = re.search(
            r'Invalid shorthand folder for "([^"]+)"',
            message,
        )
        if shorthand_match:
            key = shorthand_match.group(1)
            template_line = _find_key_line_in_text(template_text, key)
            message = f'Invalid shorthand folder for "{key}" in {template_kind} "{template_name}".'

    if template_line is None and exc.line:
        template_line = exc.line

    return YAMLParseError(
        message,
        template_name=template_name,
        template_line=template_line,
    )


def build_token_context(yaml_data: Optional[Any], title: str = "", description: str = "") -> TokenContext:
    """
    Build the token substitution context from YAML data and user input.
    Includes lowercase aliases for case-insensitive matching.
    """
    context = TokenContext()
    
    # Add user-provided values
    context['title'] = title
    context['description'] = description
    
    # Add custom tokens from library
    custom_tokens = library.load_custom_tokens()
    python_tokens = {}
    for name, token in custom_tokens.items():
        token_type = token.get("type", "text")
        token_value = token.get("value", "")
        context[name] = token_value
        if token_type == "python":
            python_tokens[name.lower()] = token_value
    context.python_tokens = python_tokens
    
    # Add lowercase aliases for case-insensitive matching
    lowercase_aliases = {}
    for key, value in context.items():
        lowercase_aliases[key.lower()] = value
    context.update(lowercase_aliases)
    
    return context


def _with_context_overrides(context: Dict[str, str], overrides: Dict[str, str]) -> TokenContext:
    python_tokens = getattr(context, "python_tokens", {})
    new_context = TokenContext(context, python_tokens=python_tokens.copy())
    for key, value in overrides.items():
        new_context[key] = value
        new_context[key.lower()] = value
    return new_context


def substitute_tokens(text: str, context: Dict[str, str]) -> str:
    """
    Substitute tokens in text.
    - {mp:TokenName} uses the token context (case-insensitive)
      (if the token is marked as python, it will be evaluated)
    - {mp.py: <expr>} evaluates a Python expression
    - {mp.py|<code>} executes Python code (multi-line supported)
    """
    python_preamble = library.get_python_preamble()
    has_preamble = isinstance(python_preamble, str) and python_preamble.strip()

    def run_python(code: str, is_expression: bool):
        exec_context = {"__builtins__": __builtins__, "context": context}

        if has_preamble:
            try:
                with redirect_stdout(io.StringIO()):
                    exec(python_preamble, exec_context, exec_context)
            except Exception as exc:
                raise RuntimeError(f"Python preamble error: {exc}") from exc

        if is_expression:
            output = io.StringIO()
            with redirect_stdout(output):
                result = eval(code, exec_context, exec_context)
            if result is None:
                stdout_value = output.getvalue()
                return stdout_value.rstrip("\n") if stdout_value else ""
            return str(result)

        output = io.StringIO()
        with redirect_stdout(output):
            exec(code, exec_context, exec_context)
        stdout_value = output.getvalue()
        if "result" in exec_context:
            return exec_context.get("result")
        if stdout_value:
            return stdout_value.rstrip("\n")
        return None

    def replace_python_block(match):
        code = textwrap.dedent(match.group(1)).strip("\n")
        try:
            value = run_python(code, is_expression=False)
            if value is None:
                return ""
            if isinstance(value, (list, dict)):
                return yaml.dump(value, default_flow_style=False, allow_unicode=True).rstrip("\n")
            return "" if value is None else str(value)
        except Exception as exc:
            raise YAMLParseError(f"Python token error: {exc}") from exc

    def replace_python_expr(match):
        code = match.group(1).strip()
        try:
            return run_python(code, is_expression=True)
        except Exception as exc:
            raise YAMLParseError(f"Python token error: {exc}") from exc

    def replace_custom_token(token_name: str, default_text: str):
        python_tokens = getattr(context, "python_tokens", {})
        lookup = token_name.lower()
        if lookup in python_tokens:
            code = python_tokens[lookup]
            try:
                if "\n" in code:
                    value = run_python(textwrap.dedent(code).strip("\n"), is_expression=False)
                    if value is None:
                        return ""
                    if isinstance(value, (list, dict)):
                        return yaml.dump(
                            value,
                            default_flow_style=False,
                            allow_unicode=True,
                        ).rstrip("\n")
                    return "" if value is None else str(value)
                stripped = code.strip()
                if not stripped:
                    return ""
                try:
                    return run_python(stripped, is_expression=True)
                except SyntaxError:
                    value = run_python(textwrap.dedent(code).strip("\n"), is_expression=False)
                    if value is None:
                        return ""
                    if isinstance(value, (list, dict)):
                        return yaml.dump(
                            value,
                            default_flow_style=False,
                            allow_unicode=True,
                        ).rstrip("\n")
                    return "" if value is None else str(value)
            except Exception as exc:
                raise YAMLParseError(f"Python token error: {exc}") from exc
        if lookup in context:
            return context.get(lookup, default_text)
        raise YAMLParseError(f'Unknown token "{token_name}".')

    def replace_token(match):
        token_name = match.group(1)
        # Case-insensitive lookup
        return replace_custom_token(token_name, match.group(0))

    # Process python block tokens first.
    text = re.sub(r'\{mp\.py\|([\s\S]*?)\}', replace_python_block, text, flags=re.IGNORECASE)
    # Process python expression tokens.
    text = re.sub(r'\{mp\.py\s*:\s*([^}]+)\}', replace_python_expr, text, flags=re.IGNORECASE)
    # Pattern matches {mp:TokenName} - case insensitive on mp
    return re.sub(r'\{[mM][pP]:([^}]+)\}', replace_token, text)


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename/folder name."""
    # Remove or replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '_')
    
    # Remove leading/trailing whitespace and trailing dots
    name = name.strip()
    name = name.rstrip('.')
    
    # Ensure non-empty
    if not name or name in (".", ".."):
        name = "Untitled"
    
    return name


def get_file_template_content(template_name: str) -> str:
    """Get the content of a named file template."""
    templates = library.load_file_templates()
    return templates.get(template_name, "")


def _extract_file_items(yaml_data: Optional[Any]) -> Optional[List[Any]]:
    """Extract the top-level file item list from YAML data."""
    if yaml_data is None:
        return None
    if isinstance(yaml_data, list):
        return yaml_data
    if isinstance(yaml_data, dict):
        files = yaml_data.get('files', [])
        return files if isinstance(files, list) else None
    return None


def _collect_nodes(
    items: List[Any],
    context: Dict[str, str],
    include_stack: List[str],
    source_template: str | None = None,
) -> List[FileNode]:
    """Process a list of YAML items into file nodes."""
    nodes: List[FileNode] = []
    for item in items:
        if isinstance(item, str):
            filename = substitute_tokens(item, context)
            filename = sanitize_filename(filename)
            nodes.append(FileNode(
                name=filename,
                content="",
                is_folder=False,
                source_template=source_template,
            ))
            continue
        if isinstance(item, dict) and "python" in item:
            code = _normalize_token_value(item["python"])
            items_from_code = _run_python_items(code, context, "python")
            nodes.extend(_collect_nodes(
                items_from_code,
                context,
                include_stack,
                source_template=source_template,
            ))
            continue
        nodes.extend(_process_file_item(item, context, include_stack, source_template))
    return nodes


def build_file_tree(
    yaml_data: Optional[Any],
    context: Dict[str, str],
    include_stack: Optional[List[str]] = None,
) -> Optional[FileNode]:
    """
    Build a file tree from parsed YAML data.
    Returns the root FileNode or None if no files section.
    """
    files = _extract_file_items(yaml_data)
    if files is None:
        return None
    if include_stack is None:
        include_stack = []
    
    # Determine project name
    project_name = context.get('title', 'Project') or "Project"
    
    project_name = sanitize_filename(project_name)
    
    # Build root node
    root = FileNode(name=project_name, is_folder=True)
    
    # Process files list
    root.children.extend(_collect_nodes(files, context, include_stack))
    
    return root


def _normalize_token_value(value: Any) -> str:
    """Normalize YAML values that might be token mappings into strings."""
    if isinstance(value, dict) and len(value) == 1:
        key, mapped_value = next(iter(value.items()))
        if mapped_value is None:
            return f"{{{key}}}"
    if value is None:
        return ""
    return str(value)


def _run_python_items(code: str, context: Dict[str, str], template_name: str) -> List[Any]:
    """Execute python block and return a list of YAML items."""
    code = textwrap.dedent(code).strip("\n")
    exec_context = {"__builtins__": __builtins__, "context": context}
    python_preamble = library.get_python_preamble()
    output = io.StringIO()
    if isinstance(python_preamble, str) and python_preamble.strip():
        try:
            with redirect_stdout(io.StringIO()):
                exec(python_preamble, exec_context, exec_context)
        except Exception as exc:
            raise YAMLParseError(
                f'Python preamble error in "{template_name}": {exc}'
            ) from exc
    try:
        with redirect_stdout(output):
            exec(code, exec_context, exec_context)
    except Exception as exc:
        raise YAMLParseError(f'Python item error in "{template_name}": {exc}') from exc

    if "result" in exec_context:
        result = exec_context.get("result")
        if result is None:
            return []
        if not isinstance(result, list):
            raise YAMLParseError(f'Python item "result" must be a list in "{template_name}".')
        return result

    stdout_value = output.getvalue().strip()
    if not stdout_value:
        return []

    data, error = parse_yaml(stdout_value)
    if error:
        raise YAMLParseError(f'Invalid YAML from python block in "{template_name}": {error}')
    items = _extract_file_items(data)
    if items is None:
        raise YAMLParseError(f'Python block output must be a list in "{template_name}".')
    return items


def _with_file_context(context: Dict[str, str], filename: str) -> TokenContext:
    file_path = Path(filename)
    overrides = {
        "filename": filename,
        "file_stem": file_path.stem,
        "file_ext": file_path.suffix,
    }
    return _with_context_overrides(context, overrides)


def _process_file_item(
    item: Any,
    context: Dict[str, str],
    include_stack: List[str],
    source_template: str | None = None,
) -> List[FileNode]:
    """Process a single file/folder item from the YAML."""
    if not isinstance(item, dict):
        return []

    if 'project_template' in item:
        template_name = substitute_tokens(
            _normalize_token_value(item['project_template']),
            context
        ).strip()
        if not template_name:
            return []
        if template_name in include_stack:
            chain = " -> ".join(include_stack + [template_name])
            raise YAMLParseError(f"Recursive project template include: {chain}")
        content = library.load_project_template(template_name)
        if content is None:
            raise YAMLParseError(f'Project template "{template_name}" not found.')
        data, error = parse_yaml(content)
        if error:
            template_line = _extract_error_line(error)
            raise YAMLParseError(
                f'Invalid YAML in project template "{template_name}": {error}',
                template_name=template_name,
                template_line=template_line,
            )
        file_items = _extract_file_items(data)
        if file_items is None:
            raise YAMLParseError(f'Project template "{template_name}" has no file list.')
        overrides = {}
        if "title" in item:
            overrides["title"] = substitute_tokens(
                _normalize_token_value(item["title"]),
                context,
            )
        if "description" in item:
            overrides["description"] = substitute_tokens(
                _normalize_token_value(item["description"]),
                context,
            )
        include_context = (
            _with_context_overrides(context, overrides) if overrides else context
        )
        try:
            return _collect_nodes(
                file_items,
                include_context,
                include_stack + [template_name],
                source_template=template_name,
            )
        except Exception as exc:
            raise _decorate_template_error(
                exc,
                template_name,
                content,
                "project template",
            ) from exc
    
    if 'file_template' in item:
        filename_value = _normalize_token_value(item['file_template'])
        filename = substitute_tokens(filename_value, context)
        filename = sanitize_filename(filename)
        file_context = _with_file_context(context, filename)
        template_name = substitute_tokens(filename_value, context).strip()
        if not template_name:
            return []
        template_content = get_file_template_content(template_name)
        try:
            content = substitute_tokens(template_content, file_context)
        except Exception as exc:
            raise _decorate_template_error(
                exc,
                template_name,
                template_content,
                "file template",
            ) from exc
        return [FileNode(
            name=filename,
            content=content,
            is_folder=False,
            source_template=source_template,
        )]

    if 'file' in item:
        # It's a file
        filename = substitute_tokens(_normalize_token_value(item['file']), context)
        filename = sanitize_filename(filename)
        file_context = _with_file_context(context, filename)
        
        # Get content
        content = ""
        if 'content' in item:
            content = substitute_tokens(str(item['content']), file_context)
        elif 'template' in item:
            template_name = item['template']
            template_content = get_file_template_content(template_name)
            try:
                content = substitute_tokens(template_content, file_context)
            except Exception as exc:
                raise _decorate_template_error(
                    exc,
                    template_name,
                    template_content,
                    "file template",
                ) from exc
        
        return [FileNode(
            name=filename,
            content=content,
            is_folder=False,
            source_template=source_template,
        )]
    
    elif 'folder' in item:
        # It's a folder
        foldername = substitute_tokens(_normalize_token_value(item['folder']), context)
        foldername = sanitize_filename(foldername)
        
        folder = FileNode(
            name=foldername,
            is_folder=True,
            source_template=source_template,
        )
        
        # Process contents
        contents = item.get('contents', [])
        if isinstance(contents, list):
            folder.children.extend(_collect_nodes(
                contents,
                context,
                include_stack,
                source_template=source_template,
            ))

        return [folder]

    if len(item) == 1:
        key, value = next(iter(item.items()))
        key_text = _normalize_token_value(key)
        token_probe = None
        if re.search(r'\{[mM][pP]\s*:', key_text):
            token_probe = key_text
        elif re.match(r'^[mM][pP]\s*:', key_text):
            token_probe = f"{{{key_text}}}"
        if token_probe:
            substitute_tokens(token_probe, context)
        folder_key = substitute_tokens(key_text, context)
        if isinstance(value, list):
            foldername = sanitize_filename(folder_key)
            folder = FileNode(
                name=foldername,
                is_folder=True,
                source_template=source_template,
            )
            folder.children.extend(_collect_nodes(
                value,
                context,
                include_stack,
                source_template=source_template,
            ))
            return [folder]
        raise YAMLParseError(f'Invalid shorthand folder for "{key}".')

    return []


def generate_project(
    root: FileNode,
    output_path: Path | str,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    conflict_callback: Optional[Callable[[Path, Path, bool], str]] = None,
) -> Tuple[bool, str]:
    """
    Generate the project files to disk.
    Generates children of root directly into output_path (no project folder wrapper).
    Returns (success, message).
    """
    output_path = Path(output_path)

    class GenerationCancelled(Exception):
        pass

    def _next_available_path(path: Path) -> Path:
        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        index = 1
        while True:
            candidate = parent / f"{stem} ({index}){suffix}"
            if not candidate.exists():
                return candidate
            index += 1

    try:
        total_files = root.file_count()
        files_created = [0]  # Use list to allow modification in nested function
        
        def create_node(node: FileNode, parent_path: Path):
            current_path = parent_path / node.name
            
            if node.is_folder:
                if current_path.exists() and conflict_callback:
                    decision = conflict_callback(current_path, output_path, True)
                    if decision == "cancel":
                        raise GenerationCancelled()
                    if decision == "skip":
                        return
                    if decision == "overwrite":
                        if current_path.is_dir():
                            shutil.rmtree(current_path)
                        else:
                            current_path.unlink()
                    elif decision == "merge" and current_path.is_file():
                        current_path.unlink()

                current_path.mkdir(parents=True, exist_ok=True)
                for child in node.children:
                    create_node(child, current_path)
            else:
                target_path = current_path
                if target_path.exists() and conflict_callback:
                    decision = conflict_callback(target_path, output_path, False)
                    if decision == "cancel":
                        raise GenerationCancelled()
                    if decision == "keep":
                        target_path = _next_available_path(target_path)
                    if decision == "skip":
                        return
                # Ensure parent exists
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(node.content, encoding='utf-8')
                files_created[0] += 1
                
                if progress_callback:
                    progress_callback(files_created[0], total_files)
        
        # Generate children directly into output_path (skip root wrapper)
        for child in root.children:
            create_node(child, output_path)
        
        return True, f"Project created in: {output_path}"
    
    except GenerationCancelled:
        return False, "Generation cancelled."
    except Exception as e:
        return False, f"Error creating project: {str(e)}"


# Default YAML template for new projects
DEFAULT_YAML = '''# Example project template.
# Each item is either a file or a folder in the project.
# Tokens use {mp:token} and are case-insensitive.
#
# Explicit syntax:
# - file: filename for a generated file
# - folder: folder name
#   contents: nested items inside a folder
# - content: inline file contents (supports {mp:token})
# - template: reference a File Template by name
# - file_template: shorthand for file + template using the same name
# - project_template: include another Project Template by name
# - python: run python code that returns or prints a YAML list
- file: README.md
  content: |
    # {mp:title}
    
    {mp:description}
    
    ## Contact
    
    {mp:email}
    
- folder: src
  contents:
    - file: main.py
      template: main.py
    - folder: tests

# Implicit syntax (folder name as the key, list of contents as the value):
# Note: for tokenized folder names, use quotes: "{mp:title}"
- "Teaching - {mp:title}":
  - Quizzes.md
  - file: lesson-plan.md
    content: |
      # Lesson Plan
      {mp:description}
  - folder: resources

# Programmatic items (python result must be a list of items):
- python: |
    result = [
      {"file": f"Quiz {i}.tex", "content": f"\\\\section*{{Quiz {i}}}\\n"}
      for i in range(3)
    ]
'''
