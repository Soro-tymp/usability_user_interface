"""
button_joystick.py — Directional button-pad joystick.

A 3x3 grid of 8 directional buttons (compass layout, center empty) that
emits the same positionChanged(x, y) signal as Joystick (joystick.py) —
full magnitude in the pressed button's direction, (0, 0) on release — so
it wires into motion the same way, via JoystickBinding. Adapted from the
main app's ui/widget/button_joystick.py (minus the .hide() call and
step-visibility wiring, which belong to the full procedure wizard) — the
one deliberate difference is BUTTON_SIZE/margins/spacing below, shrunk to
fit this demo's narrower side panel (see panel_left.py's SIDE_PANEL_WIDTH)
without spilling past its edges.
"""

import math

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QGridLayout, QPushButton

from ui.styles import COLOR_BACKGROUND_INPUT, COLOR_PRIMARY, COLOR_PRIMARY_HOVER, COLOR_PRIMARY_PRESSED

BUTTON_SIZE = 40
_DIAG = 1.0 / math.sqrt(2)  # matches the analog Joystick's max diagonal reach

# (glyph, dx, dy, row, col) — dy grows downward, matching
# Joystick._update_handle_pos's convention.
_BUTTONS = [
    ("↖", -_DIAG, -_DIAG, 0, 0),
    ("▲", 0.0, -1.0, 0, 1),
    ("↗", _DIAG, -_DIAG, 0, 2),
    ("◀", -1.0, 0.0, 1, 0),
    ("▶", 1.0, 0.0, 1, 2),
    ("↙", -_DIAG, _DIAG, 2, 0),
    ("▼", 0.0, 1.0, 2, 1),
    ("↘", _DIAG, _DIAG, 2, 2),
]


class ButtonJoystick(QWidget):
    """3x3 compass of directional buttons (8 directions, center left empty)."""

    positionChanged = pyqtSignal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("button-joystick")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            #button-joystick {{
                background-color: {COLOR_PRIMARY_PRESSED};
                border: 3px solid {COLOR_PRIMARY};
                border-radius: 20px;
            }}
            #button-joystick QPushButton {{
                background-color: {COLOR_BACKGROUND_INPUT};
                border: 2px solid {COLOR_PRIMARY};
                border-radius: 5px;
                font-size: 10pt;
                font-weight: 700;
                color: white;
            }}
            #button-joystick QPushButton:hover {{
                background-color: {COLOR_PRIMARY_HOVER};
            }}
            #button-joystick QPushButton:pressed {{
                background-color: {COLOR_PRIMARY};
            }}
        """)

        layout = QGridLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        for glyph, dx, dy, row, col in _BUTTONS:
            btn = QPushButton(glyph)
            btn.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.pressed.connect(lambda x=dx, y=dy: self.positionChanged.emit(x, y))
            btn.released.connect(lambda: self.positionChanged.emit(0.0, 0.0))
            layout.addWidget(btn, row, col)
