"""
panel_right.py — RightPanel: fixed-width right sidebar.

Trimmed down from the main app's ui/panel_right.py (RightSidePanel): keeps
its core arrangement — a StepInstructionCard, the directional ButtonJoystick
pad below it (visible only during the "Align" step, exactly like the real
RightSidePanel gates its own button_joystick — see
StepInstructionCard._update_button_joystick_visibility there), and a
Confirm button pinned to the bottom — and drops the procedure-stage
buttons (Init/Deploy/Align/Lock/Remove), since those exist to drive real
hardware state.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton

from ui.button_joystick import ButtonJoystick
from ui.panel_left import SIDE_PANEL_WIDTH
from ui.step_instruction_card import StepInstructionCard


class RightPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("right-panel")
        self.setFixedWidth(SIDE_PANEL_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(8)

        # step_card grows from the top, taking whatever height its text
        # needs; the stretch is below the button pad instead of above the
        # card (unlike the real RightSidePanel, which has other content
        # above the card to push down) so Confirm still pins to the
        # bottom without squeezing the card's text.
        self.step_card = StepInstructionCard()
        layout.addWidget(self.step_card)

        self.button_joystick = ButtonJoystick()
        layout.addWidget(self.button_joystick, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.button_joystick.setVisible(False)

        layout.addStretch()

        self.btn_confirm = QPushButton("Confirm")
        layout.addWidget(self.btn_confirm)
