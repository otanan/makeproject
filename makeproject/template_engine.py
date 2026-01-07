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
    def __init__(self, message: str, line: int = None):
        self.line = line
        self.message = message
        if line:
            super().__init__(f"{message} (line {line})")
        else:
            super().__init__(message)


def preprocess_yaml(text: str) -> str:
    """Preprocess YAML text: convert tabs to 2 spaces."""
    return text.replace('\t', '  ')


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


def substitute_tokens(text: str, context: Dict[str, str]) -> str:
    """
    Substitute tokens in text.
    - {mp:TokenName} uses the token context (case-insensitive)
      (if the token is marked as python, it will be evaluated)
    - {mp.py: <expr>} evaluates a Python expression
    - {mp.py|<code>} executes Python code (multi-line supported)
    """
    def run_python(code: str, is_expression: bool):
        globals_dict = {"__builtins__": __builtins__}
        locals_dict = {"context": context}

        if is_expression:
            result = eval(code, globals_dict, locals_dict)
            return "" if result is None else str(result)

        output = io.StringIO()
        with redirect_stdout(output):
            exec(code, globals_dict, locals_dict)
        stdout_value = output.getvalue()
        if "result" in locals_dict:
            return locals_dict.get("result")
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
    
    # Remove leading/trailing whitespace and dots
    name = name.strip().strip('.')
    
    # Ensure non-empty
    if not name:
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


def _collect_nodes(items: List[Any], context: Dict[str, str], include_stack: List[str]) -> List[FileNode]:
    """Process a list of YAML items into file nodes."""
    nodes: List[FileNode] = []
    for item in items:
        if isinstance(item, str):
            filename = substitute_tokens(item, context)
            filename = sanitize_filename(filename)
            nodes.append(FileNode(name=filename, content="", is_folder=False))
            continue
        if isinstance(item, dict) and "python" in item:
            code = _normalize_token_value(item["python"])
            items_from_code = _run_python_items(code, context, "python")
            nodes.extend(_collect_nodes(items_from_code, context, include_stack))
            continue
        nodes.extend(_process_file_item(item, context, include_stack))
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
    globals_dict = {"__builtins__": __builtins__}
    locals_dict = {"context": context}
    output = io.StringIO()
    try:
        with redirect_stdout(output):
            exec(code, globals_dict, locals_dict)
    except Exception as exc:
        raise YAMLParseError(f'Python item error in "{template_name}": {exc}') from exc

    if "result" in locals_dict:
        result = locals_dict.get("result")
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


def _process_file_item(item: Any, context: Dict[str, str], include_stack: List[str]) -> List[FileNode]:
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
            raise YAMLParseError(f'Invalid YAML in project template "{template_name}": {error}')
        file_items = _extract_file_items(data)
        if file_items is None:
            raise YAMLParseError(f'Project template "{template_name}" has no file list.')
        return _collect_nodes(file_items, context, include_stack + [template_name])
    
    if 'file' in item:
        # It's a file
        filename = substitute_tokens(_normalize_token_value(item['file']), context)
        filename = sanitize_filename(filename)
        
        # Get content
        content = ""
        if 'content' in item:
            content = substitute_tokens(str(item['content']), context)
        elif 'template' in item:
            template_name = item['template']
            template_content = get_file_template_content(template_name)
            content = substitute_tokens(template_content, context)
        
        return [FileNode(name=filename, content=content, is_folder=False)]
    
    elif 'folder' in item:
        # It's a folder
        foldername = substitute_tokens(_normalize_token_value(item['folder']), context)
        foldername = sanitize_filename(foldername)
        
        folder = FileNode(name=foldername, is_folder=True)
        
        # Process contents
        contents = item.get('contents', [])
        if isinstance(contents, list):
            folder.children.extend(_collect_nodes(contents, context, include_stack))

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
            folder = FileNode(name=foldername, is_folder=True)
            folder.children.extend(_collect_nodes(value, context, include_stack))
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
