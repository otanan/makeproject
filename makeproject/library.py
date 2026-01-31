"""
Persistence layer for MakeProject.
Handles storage in ~/Library/Application Support/MakeProject/
"""

import os
import sys
import yaml
from pathlib import Path
from typing import Dict, List, Optional

# Application Support paths
APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "MakeProject"
DEFAULT_PROJECT_TEMPLATES_DIR = APP_SUPPORT_DIR / "project_templates"
DEFAULT_FILE_TEMPLATES_DIR = APP_SUPPORT_DIR / "file_templates"
FILE_TEMPLATES_PATH = APP_SUPPORT_DIR / "file_templates.yaml"
CUSTOM_TOKENS_PATH = APP_SUPPORT_DIR / "custom_tokens.yaml"
PREFERENCES_PATH = APP_SUPPORT_DIR / "preferences.yaml"
UPDATES_DIR = APP_SUPPORT_DIR / "updates"
APP_OPENED_PREF_KEY = "app_opened"
CUSTOM_TOKENS_PREF_KEY = "custom_tokens_path"
PROJECT_GENERATION_DIR_PREF_KEY = "project_generation_dir"
PYTHON_INTERPRETER_PREF_KEY = "python_interpreter_path"
PYTHON_PREAMBLE_PREF_KEY = "python_preamble"
UI_FONT_SIZE_PREF_KEY = "ui_font_size"
EDITOR_FONT_SIZE_PREF_KEY = "editor_font_size"
DEFAULT_PYTHON_INTERPRETER = Path(sys.executable)
DEFAULT_PROJECT_GENERATION_DIR = Path.home()
DEFAULT_UI_FONT_SIZE = 12  # Base UI font size in points
DEFAULT_EDITOR_FONT_SIZE = 12  # Base editor font size in points
IGNORED_TEMPLATE_DIRS = {".git", ".hg", ".svn"}
IGNORED_TEMPLATE_FILES = {".DS_Store", ".localized", "Thumbs.db", "desktop.ini"}

# Default file templates seeded on first run (use actual file extensions)
DEFAULT_FILE_TEMPLATES = {
    "main.py": '''#!/usr/bin/env python3
"""
{mp:title} - {mp:description}
"""

def main():
    print("Hello from {mp:title}!")

if __name__ == "__main__":
    main()
''',
    "preamble.sty": r'''\NeedsTeXFormat{LaTeX2e}
\ProvidesPackage{preamble}[{mp:title} Package]

% Common packages
\RequirePackage{amsmath}
\RequirePackage{amssymb}
\RequirePackage{graphicx}

% Custom commands
\newcommand{\project}{{mp:title}}

\endinput
'''
}

# Default custom tokens seeded on first run
DEFAULT_CUSTOM_TOKENS = {
    "email": "myemail@gmail.com"
}


def _ensure_app_support_dir():
    """Create base app support directories."""
    APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)


def ensure_directories():
    """Create required directories if they don't exist."""
    _ensure_app_support_dir()
    get_project_templates_dir().mkdir(parents=True, exist_ok=True)
    get_file_templates_dir().mkdir(parents=True, exist_ok=True)


def _has_app_opened() -> bool:
    """Return True if the app appears to have been opened before."""
    if PREFERENCES_PATH.exists():
        return True
    if CUSTOM_TOKENS_PATH.exists():
        return True
    if FILE_TEMPLATES_PATH.exists():
        return True
    project_dir = get_project_templates_dir()
    if project_dir.exists() and any(project_dir.glob("*.yaml")):
        return True
    return False


def _mark_app_opened():
    """Persist the app-opened flag for future launches."""
    prefs = load_preferences()
    if prefs.get(APP_OPENED_PREF_KEY) is True:
        return
    prefs[APP_OPENED_PREF_KEY] = True
    save_preferences(prefs)


def seed_defaults():
    """Seed default file templates on first app launch."""
    ensure_directories()
    _migrate_file_templates()
    if not _has_file_templates() and not _has_app_opened():
        save_file_templates(DEFAULT_FILE_TEMPLATES)


def seed_custom_tokens():
    """Seed default custom tokens on first run, ensure required defaults exist."""
    ensure_directories()
    tokens_path = get_custom_tokens_path()
    if not tokens_path.exists():
        save_custom_tokens(DEFAULT_CUSTOM_TOKENS)
        return


def initialize():
    """Initialize the library on app startup."""
    ensure_directories()
    seed_defaults()
    seed_custom_tokens()
    _mark_app_opened()


def get_project_templates_dir() -> Path:
    """Return the project templates directory, honoring user preferences."""
    prefs = load_preferences()
    path_value = prefs.get("project_templates_dir")
    if isinstance(path_value, str) and path_value.strip():
        return Path(path_value).expanduser()
    return DEFAULT_PROJECT_TEMPLATES_DIR


def get_file_templates_dir() -> Path:
    """Return the file templates directory, honoring user preferences."""
    prefs = load_preferences()
    path_value = prefs.get("file_templates_dir")
    if isinstance(path_value, str) and path_value.strip():
        return Path(path_value).expanduser()
    return DEFAULT_FILE_TEMPLATES_DIR


def get_custom_tokens_path() -> Path:
    """Return the custom tokens file path, honoring user preferences."""
    prefs = load_preferences()
    path_value = prefs.get(CUSTOM_TOKENS_PREF_KEY)
    if isinstance(path_value, str) and path_value.strip():
        return Path(path_value).expanduser()
    return CUSTOM_TOKENS_PATH


def set_custom_tokens_path(custom_tokens_path: Path):
    """Persist the custom tokens storage location."""
    prefs = load_preferences()
    prefs[CUSTOM_TOKENS_PREF_KEY] = str(custom_tokens_path)
    save_preferences(prefs)


def set_template_paths(project_templates_dir: Path, file_templates_dir: Path):
    """Persist template storage locations."""
    prefs = load_preferences()
    prefs["project_templates_dir"] = str(project_templates_dir)
    prefs["file_templates_dir"] = str(file_templates_dir)
    save_preferences(prefs)


def get_project_generation_dir() -> Path:
    """Return the default start directory for project generation."""
    prefs = load_preferences()
    path_value = prefs.get(PROJECT_GENERATION_DIR_PREF_KEY)
    if isinstance(path_value, str) and path_value.strip():
        path = Path(path_value).expanduser()
        if path.exists() and path.is_dir():
            return path
    return DEFAULT_PROJECT_GENERATION_DIR


def set_project_generation_dir(project_generation_dir: Optional[Path]):
    """Persist the default start directory for project generation."""
    prefs = load_preferences()
    if project_generation_dir is None:
        prefs.pop(PROJECT_GENERATION_DIR_PREF_KEY, None)
    else:
        path_value = str(project_generation_dir).strip()
        if path_value:
            prefs[PROJECT_GENERATION_DIR_PREF_KEY] = path_value
        else:
            prefs.pop(PROJECT_GENERATION_DIR_PREF_KEY, None)
    save_preferences(prefs)


def get_python_interpreter_path() -> Path:
    """Return the Python interpreter path, honoring user preferences."""
    prefs = load_preferences()
    path_value = prefs.get(PYTHON_INTERPRETER_PREF_KEY)
    if isinstance(path_value, str) and path_value.strip():
        return Path(path_value).expanduser()
    return DEFAULT_PYTHON_INTERPRETER


def set_python_interpreter_path(python_interpreter_path: Optional[Path]):
    """Persist the Python interpreter path preference."""
    prefs = load_preferences()
    if python_interpreter_path is None:
        prefs.pop(PYTHON_INTERPRETER_PREF_KEY, None)
    else:
        path_value = str(python_interpreter_path).strip()
        if path_value:
            prefs[PYTHON_INTERPRETER_PREF_KEY] = path_value
        else:
            prefs.pop(PYTHON_INTERPRETER_PREF_KEY, None)
    save_preferences(prefs)


def get_python_preamble() -> str:
    """Return the Python preamble code, honoring user preferences."""
    prefs = load_preferences()
    value = prefs.get(PYTHON_PREAMBLE_PREF_KEY)
    return value if isinstance(value, str) else ""


def set_python_preamble(preamble: str):
    """Persist the Python preamble code."""
    prefs = load_preferences()
    prefs[PYTHON_PREAMBLE_PREF_KEY] = preamble if isinstance(preamble, str) else ""
    save_preferences(prefs)


def get_ui_font_size() -> int:
    """Return the UI font size."""
    prefs = load_preferences()
    size = prefs.get(UI_FONT_SIZE_PREF_KEY, DEFAULT_UI_FONT_SIZE)
    if isinstance(size, int) and 8 <= size <= 36:
        return size
    return DEFAULT_UI_FONT_SIZE


def set_ui_font_size(size: int):
    """Persist the UI font size preference."""
    prefs = load_preferences()
    if isinstance(size, int) and 8 <= size <= 36:
        prefs[UI_FONT_SIZE_PREF_KEY] = size
    else:
        prefs[UI_FONT_SIZE_PREF_KEY] = DEFAULT_UI_FONT_SIZE
    save_preferences(prefs)


def get_editor_font_size() -> int:
    """Return the editor font size for code editors."""
    prefs = load_preferences()
    size = prefs.get(EDITOR_FONT_SIZE_PREF_KEY, DEFAULT_EDITOR_FONT_SIZE)
    if isinstance(size, int) and 8 <= size <= 36:
        return size
    return DEFAULT_EDITOR_FONT_SIZE


def set_editor_font_size(size: int):
    """Persist the editor font size preference."""
    prefs = load_preferences()
    if isinstance(size, int) and 8 <= size <= 36:
        prefs[EDITOR_FONT_SIZE_PREF_KEY] = size
    else:
        prefs[EDITOR_FONT_SIZE_PREF_KEY] = DEFAULT_EDITOR_FONT_SIZE
    save_preferences(prefs)


# --- Project Templates ---

def _sanitize_project_template_name(name: str) -> Optional[Path]:
    """Sanitize a project template name that may include folder paths."""
    try:
        # Remove .yaml extension if present
        if name.endswith(".yaml"):
            name = name[:-5]
        path = Path(name.strip().replace("\\", "/"))
    except Exception:
        return None
    if not path.name:
        return None
    if path.is_absolute():
        return None
    if ".." in path.parts:
        return None
    return path


def _project_template_path_from_name(name: str) -> Optional[Path]:
    """Get the full path for a project template name (which may include folders)."""
    path = _sanitize_project_template_name(name)
    if not path:
        return None
    return get_project_templates_dir() / f"{path}.yaml"


def _iter_project_template_files() -> List[Path]:
    """Iterate all project template files, including those in subdirectories."""
    base_dir = get_project_templates_dir()
    if not base_dir.exists():
        return []
    files = []
    for item in base_dir.rglob("*.yaml"):
        if item.is_file():
            rel = item.relative_to(base_dir)
            if any(part in IGNORED_TEMPLATE_DIRS for part in rel.parts[:-1]):
                continue
            if rel.name in IGNORED_TEMPLATE_FILES or rel.name.startswith("._"):
                continue
            files.append(item)
    return files


def list_project_templates() -> List[str]:
    """List all saved project template names (with folder paths, without extension).
    Returns templates sorted alphabetically (case-insensitive).
    """
    ensure_directories()
    base_dir = get_project_templates_dir()
    templates = []
    for f in _iter_project_template_files():
        rel = f.relative_to(base_dir)
        # Remove .yaml extension and convert to posix path
        name = rel.with_suffix("").as_posix()
        templates.append(name)
    # Sort alphabetically (case-insensitive)
    templates.sort(key=lambda x: x.lower())
    return templates


def list_project_template_folders() -> List[str]:
    """List all project template folder names (including empty folders)."""
    ensure_directories()
    base_dir = get_project_templates_dir()
    folders = set()
    # Include folders inferred from template file paths
    for f in _iter_project_template_files():
        rel = f.relative_to(base_dir)
        if len(rel.parts) > 1:
            # Add immediate parent folder
            folders.add(rel.parts[0])
    # Also include actual directories on disk (for empty folders)
    for item in base_dir.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            folders.add(item.name)
    return sorted(folders)


def get_project_templates_in_folder(folder: str) -> List[str]:
    """List templates inside a specific folder (sorted alphabetically)."""
    ensure_directories()
    base_dir = get_project_templates_dir()
    folder_path = base_dir / folder
    if not folder_path.exists() or not folder_path.is_dir():
        return []
    templates = []
    for f in folder_path.rglob("*.yaml"):
        if f.is_file():
            rel = f.relative_to(base_dir)
            if any(part in IGNORED_TEMPLATE_DIRS for part in rel.parts[:-1]):
                continue
            if rel.name in IGNORED_TEMPLATE_FILES or rel.name.startswith("._"):
                continue
            name = rel.with_suffix("").as_posix()
            templates.append(name)
    templates.sort(key=lambda x: x.lower())
    return templates


def load_project_template(name: str) -> Optional[str]:
    """Load a project template's YAML content by name (supports folder paths)."""
    path = _project_template_path_from_name(name)
    if path and path.exists():
        return path.read_text(encoding="utf-8")
    return None


def get_project_template_path(name: str) -> Path:
    """Get a project template path by name (supports folder paths)."""
    path = _project_template_path_from_name(name)
    if path:
        return path
    return get_project_templates_dir() / f"{name}.yaml"


def save_project_template(name: str, content: str):
    """Save a project template with the given name (supports folder paths)."""
    ensure_directories()
    path = _project_template_path_from_name(name)
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def delete_project_template(name: str) -> bool:
    """Delete a project template by name (supports folder paths). Returns True if deleted."""
    path = _project_template_path_from_name(name)
    if path and path.exists():
        path.unlink()
        # Clean up empty parent folders
        _cleanup_empty_project_folders(path.parent)
        return True
    return False


def _cleanup_empty_project_folders(folder: Path):
    """No longer automatically removes empty folders - folders persist until explicitly deleted."""
    pass


def rename_project_template(old_name: str, new_name: str) -> bool:
    """Rename a project template (supports folder paths). Returns True if renamed."""
    old_path = _project_template_path_from_name(old_name)
    new_path = _project_template_path_from_name(new_name)
    
    if not old_path or not new_path:
        return False
    if not old_path.exists():
        return False
    
    # Ensure parent folder exists for new path
    new_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Check if it's just a case change (same file on case-insensitive filesystem)
    if old_path.exists() and new_path.exists():
        try:
            if old_path.samefile(new_path):
                # Case-only change: rename via temp file
                import uuid
                temp_path = old_path.parent / f"_temp_{uuid.uuid4().hex}.yaml"
                old_path.rename(temp_path)
                temp_path.rename(new_path)
                _cleanup_empty_project_folders(old_path.parent)
                return True
        except OSError:
            pass
    
    # Standard rename (different file)
    if not new_path.exists():
        old_path.rename(new_path)
        _cleanup_empty_project_folders(old_path.parent)
        return True
    
    return False


def move_project_template_to_folder(name: str, folder: str) -> str | None:
    """Move a project template into a folder. Returns new name or None on failure."""
    old_path = _project_template_path_from_name(name)
    if not old_path or not old_path.exists():
        return None
    
    # Extract just the template name without any existing folder
    template_basename = Path(name).name
    new_name = f"{folder}/{template_basename}"
    new_path = _project_template_path_from_name(new_name)
    
    if not new_path:
        return None
    if new_path.exists():
        return None
    
    new_path.parent.mkdir(parents=True, exist_ok=True)
    old_path.rename(new_path)
    _cleanup_empty_project_folders(old_path.parent)
    return new_name


def move_project_template_out_of_folder(name: str) -> str | None:
    """Move a project template out of its folder to the root. Returns new name or None."""
    old_path = _project_template_path_from_name(name)
    if not old_path or not old_path.exists():
        return None
    
    # Extract just the template name
    template_basename = Path(name).name
    new_path = get_project_templates_dir() / f"{template_basename}.yaml"
    
    if new_path.exists():
        return None
    
    old_path.rename(new_path)
    _cleanup_empty_project_folders(old_path.parent)
    return template_basename


def create_project_template_folder(folder: str) -> bool:
    """Create an empty project template folder. Returns True if created."""
    ensure_directories()
    path = _sanitize_project_template_name(folder)
    if not path:
        return False
    folder_path = get_project_templates_dir() / path
    if folder_path.exists():
        return False
    folder_path.mkdir(parents=True, exist_ok=True)
    return True


def rename_project_template_folder(old_name: str, new_name: str) -> bool:
    """Rename a project template folder. Returns True if renamed."""
    base_dir = get_project_templates_dir()
    old_path = base_dir / old_name
    new_path = base_dir / new_name
    
    if not old_path.exists() or not old_path.is_dir():
        return False
    if new_path.exists():
        return False
    
    old_path.rename(new_path)
    return True


def delete_project_template_folder(folder: str) -> bool:
    """Delete a project template folder and all its contents. Returns True if deleted."""
    base_dir = get_project_templates_dir()
    folder_path = base_dir / folder
    if not folder_path.exists() or not folder_path.is_dir():
        return False
    import shutil
    shutil.rmtree(folder_path)
    return True


# --- File Templates ---

def _sanitize_template_name(name: str) -> Optional[Path]:
    try:
        path = Path(name.strip().replace("\\", "/"))
    except Exception:
        return None
    if not path.name:
        return None
    if path.is_absolute():
        return None
    if ".." in path.parts:
        return None
    return path


def _template_path_from_name(name: str) -> Optional[Path]:
    path = _sanitize_template_name(name)
    if not path:
        return None
    return get_file_templates_dir() / path


def _iter_template_files() -> List[Path]:
    base_dir = get_file_templates_dir()
    if not base_dir.exists():
        return []
    files = []
    for item in base_dir.rglob("*"):
        if item.is_file():
            rel = item.relative_to(base_dir)
            if any(part in IGNORED_TEMPLATE_DIRS for part in rel.parts[:-1]):
                continue
            if rel.name in IGNORED_TEMPLATE_FILES or rel.name.startswith("._"):
                continue
            files.append(item)
    return files


def _has_file_templates() -> bool:
    return any(True for _ in _iter_template_files())


def _migrate_file_templates():
    if not FILE_TEMPLATES_PATH.exists():
        return
    if _has_file_templates():
        return
    try:
        with open(FILE_TEMPLATES_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception:
        return
    templates: Dict[str, str] = {}
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "name" in item:
                templates[item["name"]] = item.get("content", "")
    elif isinstance(data, dict):
        templates = data
    if not templates:
        return
    save_file_templates(templates)
    try:
        backup_path = FILE_TEMPLATES_PATH.with_suffix(".yaml.bak")
        if backup_path.exists():
            backup_path.unlink()
        FILE_TEMPLATES_PATH.rename(backup_path)
    except OSError:
        pass

def load_file_templates() -> Dict[str, str]:
    """Load all file templates from disk, preserving order."""
    ensure_directories()
    templates = {}
    for path in _iter_template_files():
        try:
            rel = path.relative_to(get_file_templates_dir()).as_posix()
            templates[rel] = path.read_text(encoding="utf-8")
        except Exception:
            continue
    return templates


def save_file_templates(templates: Dict[str, str]):
    """Save file templates from a name->content mapping."""
    ensure_directories()
    for path in _iter_template_files():
        try:
            path.unlink()
        except Exception:
            pass
    for name, content in templates.items():
        save_file_template(name, content)


def list_file_template_names() -> List[str]:
    """List file template names in order."""
    ensure_directories()
    names = []
    for path in _iter_template_files():
        names.append(path.relative_to(get_file_templates_dir()).as_posix())
    return sorted(names)


def save_file_templates_list(templates: List[Dict]):
    """Save file templates as ordered list."""
    templates_dict = {}
    for item in templates:
        if isinstance(item, dict) and "name" in item:
            templates_dict[item["name"]] = item.get("content", "")
    save_file_templates(templates_dict)


def get_file_template(name: str) -> Optional[str]:
    """Get a single file template by name."""
    path = _template_path_from_name(name)
    if not path or not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None


def get_file_template_path(name: str) -> Optional[Path]:
    """Get a file template path by name."""
    path = _template_path_from_name(name)
    if not path or not path.exists():
        return None
    return path


def save_file_template(name: str, content: str):
    """Save or update a single file template. New templates are added at the end."""
    ensure_directories()
    path = _template_path_from_name(name)
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def delete_file_template(name: str) -> bool:
    """Delete a file template by name. Returns True if deleted."""
    ensure_directories()
    path = _template_path_from_name(name)
    if not path or not path.exists():
        return False
    try:
        path.unlink()
        parent = path.parent
        base_dir = get_file_templates_dir()
        while parent != base_dir and parent.exists():
            if any(parent.iterdir()):
                break
            parent.rmdir()
            parent = parent.parent
        return True
    except Exception:
        return False


def list_file_template_folders() -> List[str]:
    """List all file template folder names (including empty folders)."""
    ensure_directories()
    base_dir = get_file_templates_dir()
    folders = set()
    # Include folders inferred from template file paths
    for f in _iter_template_files():
        rel = f.relative_to(base_dir)
        if len(rel.parts) > 1:
            folders.add(rel.parts[0])
    # Also include actual directories on disk (for empty folders)
    for item in base_dir.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            folders.add(item.name)
    return sorted(folders)


def get_file_templates_in_folder(folder: str) -> List[str]:
    """List file templates inside a specific folder (sorted alphabetically)."""
    ensure_directories()
    base_dir = get_file_templates_dir()
    folder_path = base_dir / folder
    if not folder_path.exists() or not folder_path.is_dir():
        return []
    templates = []
    for f in folder_path.rglob("*"):
        if f.is_file():
            rel = f.relative_to(base_dir)
            if any(part in IGNORED_TEMPLATE_DIRS for part in rel.parts[:-1]):
                continue
            if rel.name in IGNORED_TEMPLATE_FILES or rel.name.startswith("._"):
                continue
            templates.append(rel.as_posix())
    templates.sort(key=lambda x: x.lower())
    return templates


def move_file_template_to_folder(name: str, folder: str) -> str | None:
    """Move a file template into a folder. Returns new name or None on failure."""
    path = _template_path_from_name(name)
    if not path or not path.exists():
        return None
    
    template_basename = Path(name).name
    new_name = f"{folder}/{template_basename}"
    new_path = _template_path_from_name(new_name)
    
    if not new_path:
        return None
    if new_path.exists():
        return None
    
    new_path.parent.mkdir(parents=True, exist_ok=True)
    path.rename(new_path)
    _cleanup_empty_file_folders(path.parent)
    return new_name


def move_file_template_out_of_folder(name: str) -> str | None:
    """Move a file template out of its folder to the root. Returns new name or None."""
    path = _template_path_from_name(name)
    if not path or not path.exists():
        return None
    
    template_basename = Path(name).name
    base_dir = get_file_templates_dir()
    new_path = base_dir / template_basename
    
    if new_path.exists():
        return None
    
    path.rename(new_path)
    _cleanup_empty_file_folders(path.parent)
    return template_basename


def _cleanup_empty_file_folders(folder: Path):
    """No longer automatically removes empty folders - folders persist until explicitly deleted."""
    pass


def create_file_template_folder(folder: str) -> bool:
    """Create an empty file template folder. Returns True if created."""
    ensure_directories()
    path = _sanitize_template_name(folder)
    if not path:
        return False
    folder_path = get_file_templates_dir() / path
    if folder_path.exists():
        return False
    folder_path.mkdir(parents=True, exist_ok=True)
    return True


def rename_file_template_folder(old_name: str, new_name: str) -> bool:
    """Rename a file template folder. Returns True if renamed."""
    base_dir = get_file_templates_dir()
    old_path = base_dir / old_name
    new_path = base_dir / new_name
    
    if not old_path.exists() or not old_path.is_dir():
        return False
    if new_path.exists():
        return False
    
    old_path.rename(new_path)
    return True


def delete_file_template_folder(folder: str) -> bool:
    """Delete a file template folder and all its contents. Returns True if deleted."""
    base_dir = get_file_templates_dir()
    folder_path = base_dir / folder
    if not folder_path.exists() or not folder_path.is_dir():
        return False
    import shutil
    shutil.rmtree(folder_path)
    return True


# --- Custom Tokens ---

def _normalize_custom_token(value) -> Dict[str, str]:
    if isinstance(value, dict):
        if "type" in value and "value" in value:
            token_type = value.get("type", "text")
            if isinstance(token_type, str):
                token_type = token_type.lower()
            else:
                token_type = "text"
            token_value = value.get("value", "")
            return {
                "type": "python" if token_type == "python" else "text",
                "value": "" if token_value is None else str(token_value),
            }
        if "python" in value:
            token_value = value.get("python", "")
            return {
                "type": "python",
                "value": "" if token_value is None else str(token_value),
            }
    return {"type": "text", "value": "" if value is None else str(value)}


def load_custom_tokens() -> Dict[str, Dict[str, str]]:
    """Load custom tokens from disk."""
    ensure_directories()
    path = get_custom_tokens_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if not isinstance(data, dict):
                    return {}
                tokens = {}
                for name, value in data.items():
                    tokens[str(name)] = _normalize_custom_token(value)
                return tokens
        except Exception:
            return {}
    return {}


def save_custom_tokens(tokens: Dict[str, Dict[str, str]]):
    """Save custom tokens to disk."""
    ensure_directories()
    path = get_custom_tokens_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        serialized = {}
        for name, token in tokens.items():
            if not isinstance(token, dict):
                serialized[name] = "" if token is None else str(token)
                continue
            token_type = token.get("type", "text")
            if isinstance(token_type, str):
                token_type = token_type.lower()
            else:
                token_type = "text"
            token_value = token.get("value", "")
            if token_type == "python":
                serialized[name] = {
                    "type": "python",
                    "value": "" if token_value is None else str(token_value),
                }
            else:
                serialized[name] = "" if token_value is None else str(token_value)
        yaml.dump(serialized, f, default_flow_style=False, allow_unicode=True)


def update_custom_token(name: str, value: str, token_type: str = "text"):
    """Add or update a custom token."""
    tokens = load_custom_tokens()
    token_type = token_type.lower() if isinstance(token_type, str) else "text"
    tokens[name] = {
        "type": "python" if token_type == "python" else "text",
        "value": value,
    }
    save_custom_tokens(tokens)


def delete_custom_token(name: str) -> bool:
    """Delete a custom token by name. Returns True if deleted."""
    tokens = load_custom_tokens()
    if name in tokens:
        del tokens[name]
        save_custom_tokens(tokens)
        return True
    return False


# --- Preferences ---

def load_preferences() -> Dict:
    """Load user preferences from disk."""
    _ensure_app_support_dir()
    if PREFERENCES_PATH.exists():
        try:
            with open(PREFERENCES_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def save_preferences(prefs: Dict):
    """Save user preferences to disk."""
    _ensure_app_support_dir()
    with open(PREFERENCES_PATH, "w", encoding="utf-8") as f:
        yaml.dump(prefs, f, default_flow_style=False, allow_unicode=True)


def get_preference(key: str, default=None):
    """Get a single preference value."""
    prefs = load_preferences()
    return prefs.get(key, default)


def set_preference(key: str, value):
    """Set a single preference value."""
    prefs = load_preferences()
    prefs[key] = value
    save_preferences(prefs)
