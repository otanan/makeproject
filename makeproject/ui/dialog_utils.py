"""
Shared helpers for dialog buttons.
"""

from PyQt6.QtWidgets import QPushButton

RETURN_KEY_SYMBOL = "↩"


def with_return_hint(label: str) -> str:
    return f"{label} {RETURN_KEY_SYMBOL}"


def style_default_dialog_button(button: QPushButton):
    button.setProperty("class", "defaultDialogButton")
    text = button.text()
    if RETURN_KEY_SYMBOL not in text:
        button.setText(with_return_hint(text))
    button.setDefault(True)
    button.setAutoDefault(True)
