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
PROJECT_TEMPLATES_DIR = APP_SUPPORT_DIR / "project_templates"
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


def ensure_directories():
    """Create required directories if they don't exist."""
    APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    PROJECT_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)


def seed_defaults():
    """Seed default file templates on first run."""
    if not FILE_TEMPLATES_PATH.exists():
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


# --- Project Templates ---

def list_project_templates() -> List[str]:
    """List all saved project template names (without extension).
    Returns templates sorted by creation/modification time (oldest first, newest at bottom).
    """
    ensure_directories()
    templates = []
    for f in PROJECT_TEMPLATES_DIR.glob("*.yaml"):
        templates.append((f.stem, f.stat().st_mtime))
    # Sort by modification time (oldest first, so new ones appear at bottom)
    templates.sort(key=lambda x: x[1])
    return [name for name, _ in templates]


def load_project_template(name: str) -> Optional[str]:
    """Load a project template's YAML content by name."""
    path = PROJECT_TEMPLATES_DIR / f"{name}.yaml"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def save_project_template(name: str, content: str):
    """Save a project template with the given name."""
    ensure_directories()
    path = PROJECT_TEMPLATES_DIR / f"{name}.yaml"
    path.write_text(content, encoding="utf-8")


def delete_project_template(name: str) -> bool:
    """Delete a project template by name. Returns True if deleted."""
    path = PROJECT_TEMPLATES_DIR / f"{name}.yaml"
    if path.exists():
        path.unlink()
        return True
    return False


def rename_project_template(old_name: str, new_name: str) -> bool:
    """Rename a project template. Returns True if renamed."""
    old_path = PROJECT_TEMPLATES_DIR / f"{old_name}.yaml"
    new_path = PROJECT_TEMPLATES_DIR / f"{new_name}.yaml"
    
    if not old_path.exists():
        return False
    
    # Check if it's just a case change (same file on case-insensitive filesystem)
    if old_path.exists() and new_path.exists():
        try:
            if old_path.samefile(new_path):
                # Case-only change: rename via temp file
                import uuid
                temp_path = PROJECT_TEMPLATES_DIR / f"_temp_{uuid.uuid4().hex}.yaml"
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

def load_file_templates() -> Dict[str, str]:
    """Load all file templates from disk, preserving order."""
    ensure_directories()
    if FILE_TEMPLATES_PATH.exists():
        try:
            with open(FILE_TEMPLATES_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                # Support both old dict format and new list format
                if isinstance(data, list):
                    # New format: list of {name, content} dicts
                    result = {}
                    for item in data:
                        if isinstance(item, dict) and 'name' in item:
                            result[item['name']] = item.get('content', '')
                    return result
                elif isinstance(data, dict):
                    # Old format: dict of name -> content (order may not be preserved)
                    return data
                return {}
        except Exception:
            return {}
    return {}


def save_file_templates(templates: Dict[str, str]):
    """Save file templates from a name->content mapping."""
    templates_list = [{'name': name, 'content': content} for name, content in templates.items()]
    save_file_templates_list(templates_list)


def list_file_template_names() -> List[str]:
    """List file template names in order."""
    ensure_directories()
    if FILE_TEMPLATES_PATH.exists():
        try:
            with open(FILE_TEMPLATES_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if isinstance(data, list):
                    return [item['name'] for item in data if isinstance(item, dict) and 'name' in item]
                elif isinstance(data, dict):
                    return list(data.keys())
                return []
        except Exception:
            return []
    return []


def save_file_templates_list(templates: List[Dict]):
    """Save file templates as ordered list."""
    ensure_directories()
    with open(FILE_TEMPLATES_PATH, "w", encoding="utf-8") as f:
        yaml.dump(templates, f, default_flow_style=False, allow_unicode=True)


def get_file_template(name: str) -> Optional[str]:
    """Get a single file template by name."""
    templates = load_file_templates()
    return templates.get(name)


def save_file_template(name: str, content: str):
    """Save or update a single file template. New templates are added at the end."""
    ensure_directories()
    templates_list = []
    found = False
    
    if FILE_TEMPLATES_PATH.exists():
        try:
            with open(FILE_TEMPLATES_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if isinstance(data, list):
                    templates_list = data
                elif isinstance(data, dict):
                    # Convert old format to new
                    templates_list = [{'name': k, 'content': v} for k, v in data.items()]
        except Exception:
            pass
    
    # Update existing or mark as not found
    for item in templates_list:
        if isinstance(item, dict) and item.get('name') == name:
            item['content'] = content
            found = True
            break
    
    # Append new template at the end
    if not found:
        templates_list.append({'name': name, 'content': content})
    
    save_file_templates_list(templates_list)


def delete_file_template(name: str) -> bool:
    """Delete a file template by name. Returns True if deleted."""
    ensure_directories()
    if not FILE_TEMPLATES_PATH.exists():
        return False
    
    try:
        with open(FILE_TEMPLATES_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        templates_list = []
        if isinstance(data, list):
            templates_list = data
        elif isinstance(data, dict):
            templates_list = [{'name': k, 'content': v} for k, v in data.items()]
        
        original_len = len(templates_list)
        templates_list = [item for item in templates_list if not (isinstance(item, dict) and item.get('name') == name)]
        
        if len(templates_list) < original_len:
            save_file_templates_list(templates_list)
            return True
        return False
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
    ensure_directories()
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
    ensure_directories()
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
