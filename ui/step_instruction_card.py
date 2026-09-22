"""
step_instruction_card.py — StepInstructionCard: shows the current
procedure step's title and instructions. Display-only — the real app
(ui/widget/step_instruction_card.py, same name) keeps this separate from
the Back/Confirm buttons too, since those live in the side panels on
either side of it (see panel_left.py / panel_right.py), not on the card
itself.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

from ui.styles import COLOR_PRIMARY, COLOR_PRIMARY_PRESSED, COLOR_TEXT_PRIMARY


class StepInstructionCard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("step-instruction-card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            #step-instruction-card {{
                background-color: {COLOR_PRIMARY_PRESSED};
                border: 3px solid {COLOR_PRIMARY};
                border-radius: 16px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        self._title_label = QLabel()
        self._title_label.setWordWrap(True)
        self._title_label.setMinimumHeight(45)
        self._title_label.setStyleSheet(
            f"font-size: 12pt; font-weight: 700; color: {COLOR_TEXT_PRIMARY}; border: none;")
        layout.addWidget(self._title_label)

        self._body_label = QLabel()
        self._body_label.setWordWrap(True)
        # A fixed floor instead of relying purely on wordWrap's
        # heightForWidth, which needs the layout to already know this
        # widget's final width to compute a wrapped height — a chicken-
        # and-egg the layout doesn't always resolve before the first
        # paint, silently clipping the text otherwise.
        self._body_label.setMinimumHeight(135)
        self._body_label.setStyleSheet(
            f"font-size: 10pt; color: {COLOR_TEXT_PRIMARY}; border: none;")
        layout.addWidget(self._body_label)

    def set_content(self, title: str, body: str) -> None:
        self._title_label.setText(title)
        self._body_label.setText(body)
