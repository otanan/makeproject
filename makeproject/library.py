"""
Persistence layer for MakeProject.
Handles storage in ~/Library/Application Support/MakeProject/
"""

import os
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


def seed_defaults():
    """Seed default file templates on first run."""
    ensure_directories()
    _migrate_file_templates()
    if not _has_file_templates():
        save_file_templates(DEFAULT_FILE_TEMPLATES)


def seed_custom_tokens():
    """Seed default custom tokens on first run, ensure required defaults exist."""
    ensure_directories()
    if not CUSTOM_TOKENS_PATH.exists():
        save_custom_tokens(DEFAULT_CUSTOM_TOKENS)
        return
    tokens = load_custom_tokens()
    if "email" not in tokens:
        tokens["email"] = DEFAULT_CUSTOM_TOKENS["email"]
        save_custom_tokens(tokens)


def initialize():
    """Initialize the library on app startup."""
    ensure_directories()
    seed_defaults()
    seed_custom_tokens()


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


def set_template_paths(project_templates_dir: Path, file_templates_dir: Path):
    """Persist template storage locations."""
    prefs = load_preferences()
    prefs["project_templates_dir"] = str(project_templates_dir)
    prefs["file_templates_dir"] = str(file_templates_dir)
    save_preferences(prefs)


# --- Project Templates ---

def list_project_templates() -> List[str]:
    """List all saved project template names (without extension).
    Returns templates sorted by creation/modification time (oldest first, newest at bottom).
    """
    ensure_directories()
    templates = []
    for f in get_project_templates_dir().glob("*.yaml"):
        templates.append((f.stem, f.stat().st_mtime))
    # Sort by modification time (oldest first, so new ones appear at bottom)
    templates.sort(key=lambda x: x[1])
    return [name for name, _ in templates]


def load_project_template(name: str) -> Optional[str]:
    """Load a project template's YAML content by name."""
    path = get_project_templates_dir() / f"{name}.yaml"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def get_project_template_path(name: str) -> Path:
    """Get a project template path by name."""
    return get_project_templates_dir() / f"{name}.yaml"


def save_project_template(name: str, content: str):
    """Save a project template with the given name."""
    ensure_directories()
    path = get_project_templates_dir() / f"{name}.yaml"
    path.write_text(content, encoding="utf-8")


def delete_project_template(name: str) -> bool:
    """Delete a project template by name. Returns True if deleted."""
    path = get_project_templates_dir() / f"{name}.yaml"
    if path.exists():
        path.unlink()
        return True
    return False


def rename_project_template(old_name: str, new_name: str) -> bool:
    """Rename a project template. Returns True if renamed."""
    base_dir = get_project_templates_dir()
    old_path = base_dir / f"{old_name}.yaml"
    new_path = base_dir / f"{new_name}.yaml"
    
    if not old_path.exists():
        return False
    
    # Check if it's just a case change (same file on case-insensitive filesystem)
    if old_path.exists() and new_path.exists():
        try:
            if old_path.samefile(new_path):
                # Case-only change: rename via temp file
                import uuid
                temp_path = base_dir / f"_temp_{uuid.uuid4().hex}.yaml"
                old_path.rename(temp_path)
                temp_path.rename(new_path)
                return True
        except OSError:
            pass
    
    # Standard rename (different file)
    if not new_path.exists():
        old_path.rename(new_path)
        return True
    
    return False


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
            if any(part.startswith(".") for part in rel.parts):
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


# --- Custom Tokens ---

def load_custom_tokens() -> Dict[str, str]:
    """Load custom tokens from disk."""
    ensure_directories()
    if CUSTOM_TOKENS_PATH.exists():
        try:
            with open(CUSTOM_TOKENS_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def save_custom_tokens(tokens: Dict[str, str]):
    """Save custom tokens to disk."""
    ensure_directories()
    with open(CUSTOM_TOKENS_PATH, "w", encoding="utf-8") as f:
        yaml.dump(tokens, f, default_flow_style=False, allow_unicode=True)


def update_custom_token(name: str, value: str):
    """Add or update a custom token."""
    tokens = load_custom_tokens()
    tokens[name] = value
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
