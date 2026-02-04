"""
Central location for all constants used throughout MakeProject.
Provides easy customization and better maintainability.
"""

# ============================================================================
# Colors
# ============================================================================

class Colors:
    """Color constants used throughout the application."""

    # Primary colors
    PRIMARY_GREEN = "#4CAF50"
    ACCENT_TEAL = "#1ABC9D"

    # Status colors
    ERROR_RED = "#E74C3C"
    WARNING_ORANGE = "#F39C12"
    SUCCESS_GREEN = PRIMARY_GREEN

    # UI element colors (dark theme)
    DARK_COMMENT = "#6C7086"
    DARK_BACKGROUND = "#1E1E1E"
    DARK_FOREGROUND = "#D4D4D4"

    # UI element colors (light theme)
    LIGHT_COMMENT = "#9CA3AF"
    LIGHT_BACKGROUND = "#FFFFFF"
    LIGHT_FOREGROUND = "#1F2937"

    # Toggle switch colors
    TOGGLE_ON = PRIMARY_GREEN
    TOGGLE_OFF = "#9E9E9E"
    TOGGLE_THUMB = "#FFFFFF"

    # Code highlighting colors (dark theme)
    DARK_KEYWORD = "#C586C0"
    DARK_STRING = "#CE9178"
    DARK_NUMBER = "#B5CEA8"
    DARK_BUILTIN = "#4EC9B0"

    # Gutter colors
    GUTTER_DARK_BG = "#1E1E1E"
    GUTTER_DARK_FG = "#858585"
    GUTTER_LIGHT_BG = "#F5F5F5"
    GUTTER_LIGHT_FG = "#858585"

    # Current line highlight
    CURRENT_LINE_DARK = "#2A2A2A"
    CURRENT_LINE_LIGHT = "#E8F2FF"


# ============================================================================
# Font Settings
# ============================================================================

class FontSizes:
    """Font size constants and validation ranges."""

    # Default sizes
    DEFAULT_UI = 12
    DEFAULT_EDITOR = 12

    # Valid range
    MIN = 8
    MAX = 36

    # Relative size adjustments
    HEADER_OFFSET = 2      # Headers are +2pt
    BUTTON_OFFSET = 3      # Buttons are +3pt
    BADGE_OFFSET = -2      # Badges are -2pt


class FontFamilies:
    """Font family fallback chains."""

    # Code/monospace fonts
    CODE_FONTS = [
        "Fira Code",
        "JetBrains Mono",
        "SF Mono",
        "Menlo",
        "Consolas",
        "Courier New",
        "monospace"
    ]

    # UI fonts
    UI_FONTS = [
        "Fira Sans",
        "SF Pro Display",
        "Helvetica Neue",
        "Segoe UI",
        "Arial",
        "sans-serif"
    ]


# ============================================================================
# UI Widget Dimensions
# ============================================================================

class Dimensions:
    """Size constants for UI widgets."""

    # Toggle switch
    TOGGLE_WIDTH = 44
    TOGGLE_HEIGHT = 24
    TOGGLE_THUMB_RADIUS = 8
    TOGGLE_THUMB_MARGIN = 4

    # List items
    LIST_ITEM_HEIGHT = 28
    LIST_ITEM_BASE_INDENT = 10      # Base left margin for all items
    LIST_ITEM_INDENT = 25           # Left margin for nested items (templates in folders)

    # Margins and spacing
    PANEL_MARGIN = 12
    PANEL_SPACING = 8
    WIDGET_SPACING = 4

    # Splitter sizes
    DEFAULT_LEFT_PANEL = 180
    DEFAULT_RIGHT_PANEL = 400


# ============================================================================
# Timing
# ============================================================================

class Timing:
    """Timing constants for animations and debouncing."""

    # Animations
    TOGGLE_ANIMATION_MS = 150
    FADE_ANIMATION_MS = 200
    FOLDER_EXPAND_ANIMATION_MS = 150

    # Debouncing
    REFRESH_DEBOUNCE_MS = 100
    PREVIEW_DEBOUNCE_MS = 250
    CLICK_DEBOUNCE_MS = 250
    FOLDER_CLICK_DEBOUNCE_MS = 50  # Near-instant response for folder clicks
    HISTORY_COMMIT_MS = 400

    # Delays
    UPDATE_CHECK_DELAY_MS = 2000
    FOCUS_DELAY_MS = 50
    RESTORE_DELAY_MS = 0


# ============================================================================
# Cache Limits
# ============================================================================

class CacheLimits:
    """Maximum sizes for various caches."""

    PREFERENCES_CACHE = 1           # Single preferences dict
    TEMPLATE_LIST_CACHE = 1         # Single list
    TEMPLATE_CONTENT_CACHE = 50     # LRU cache for template content
    YAML_PARSE_CACHE = 10           # Recent YAML parse results
    WIDGET_POOL_SIZE = 20           # Maximum pooled widgets per type


# ============================================================================
# File System
# ============================================================================

class FileSystem:
    """File system related constants."""

    # Ignored directories
    IGNORED_VCS_DIRS = {".git", ".hg", ".svn"}

    # Ignored files
    IGNORED_OS_FILES = {
        ".DS_Store",
        ".localized",
        "Thumbs.db",
        "desktop.ini"
    }

    # File extensions
    YAML_EXTENSION = ".yaml"
    PYTHON_EXTENSION = ".py"


# ============================================================================
# Validation
# ============================================================================

class Validation:
    """Validation constants and patterns."""

    # Font size validation
    FONT_SIZE_RANGE = (FontSizes.MIN, FontSizes.MAX)

    # Template name restrictions
    MAX_TEMPLATE_NAME_LENGTH = 255

    # Reserved template names (if needed in future)
    RESERVED_NAMES = set()


# ============================================================================
# Default Content
# ============================================================================

class Defaults:
    """Default content for various features."""

    # Default custom token
    DEFAULT_CUSTOM_TOKEN_NAME = "email"
    DEFAULT_CUSTOM_TOKEN_VALUE = "myemail@gmail.com"

    # Default template content
    UNTITLED_PROJECT_NAME = "untitled project"

    # Placeholder texts
    TEMPLATE_NAME_PLACEHOLDER = "Template name..."
    FOLDER_NAME_PLACEHOLDER = "Folder name..."
    NEW_FOLDER_PREFIX = "New Folder"


# ============================================================================
# Application Info
# ============================================================================

class App:
    """Application-level constants."""

    NAME = "MakeProject"
    COAUTHOR = "Claude Sonnet 4.5 <noreply@anthropic.com>"
