"""
styles.py — Minimal color palette for the joystick demo.

Trimmed down from the main app's ui/styles.py: just the colors the
Joystick and ButtonJoystick widgets need to draw themselves.
"""


def darken_color(hex_color: str, factor: float = 0.8) -> str:
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r = max(0, int(r * factor))
    g = max(0, int(g * factor))
    b = max(0, int(b * factor))
    return f"#{r:02x}{g:02x}{b:02x}"


def lighten_color(hex_color: str, factor: float = 1.2) -> str:
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r = min(255, int(r * factor))
    g = min(255, int(g * factor))
    b = min(255, int(b * factor))
    return f"#{r:02x}{g:02x}{b:02x}"


COLOR_PRIMARY = "#2B9DA1"
COLOR_PRIMARY_HOVER = lighten_color(COLOR_PRIMARY, 1.12)
COLOR_PRIMARY_PRESSED = darken_color(COLOR_PRIMARY, 0.70)

COLOR_BACKGROUND_MAIN = "#1E1E1E"
COLOR_BACKGROUND_WIDGET = "#2D2D2D"
COLOR_BACKGROUND_INPUT = "#3C3C3C"

COLOR_TEXT_PRIMARY = "#E0E0E0"
COLOR_TEXT_SECONDARY = "#808080"
