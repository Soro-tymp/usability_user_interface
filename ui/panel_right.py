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
        self._layout = layout

    def expand_card(self) -> None:
        # Game: the explanation card takes all the free height (instead of an
        # empty gap above the START button)
        self._layout.setStretch(self._layout.indexOf(self.step_card), 1)
        self._layout.setStretch(2, 0)   # the spacer below the button pad
