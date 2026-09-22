"""
control_panel.py — ControlPanel: the toggleable panel below the camera
view, opened/closed by LeftPanel's Control button.

Trimmed down from the main app's ui/tabs_control.py (CommandPalette):
that widget is a tab bar (Pressure / Demo / Joystick tabs); this demo
folds its two relevant tabs' contents — the Translation and Rotation
joysticks, and the 6 balloon-pressure gauges — into one always-visible
row instead, since a full tab bar isn't needed to show what this demo is
teaching. Hidden by default, exactly like CommandPalette is in
ProcedurePage, until toggled.

Two separate analog Joystick widgets, same as the real
CommandPalette._create_joystick_tab: one drives translation, the other
drives orientation ("Rotation" is the label the real app uses too, even
though the mode string passed to JoystickBinding is "orientation" — see
main_procedure.py).
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton

from ui.balloon_slider import BalloonSlider
from ui.joystick import Joystick
from ui.motion_controller import NUM_CHANNELS


class ControlPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("control-panel")
        self.setFixedHeight(220)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(16)

        joysticks_col = QVBoxLayout()
        joysticks_row = QHBoxLayout()

        translation_col = QVBoxLayout()
        translation_col.addWidget(self._label("Translation"))
        self.joystick_translation = Joystick()
        translation_col.addWidget(
            self.joystick_translation, 1, alignment=Qt.AlignmentFlag.AlignHCenter)
        joysticks_row.addLayout(translation_col)

        rotation_col = QVBoxLayout()
        rotation_col.addWidget(self._label("Rotation"))
        self.joystick_rotation = Joystick()
        rotation_col.addWidget(
            self.joystick_rotation, 1, alignment=Qt.AlignmentFlag.AlignHCenter)
        joysticks_row.addLayout(rotation_col)

        joysticks_col.addLayout(joysticks_row, 1)
        self.btn_reset = QPushButton("Reset to center")
        joysticks_col.addWidget(self.btn_reset)
        layout.addLayout(joysticks_col)

        balloons_col = QVBoxLayout()
        balloons_col.addWidget(self._label("Balloon pressures (live)"))
        balloons_row = QHBoxLayout()
        self.balloon_sliders = [BalloonSlider(i) for i in range(NUM_CHANNELS)]
        for slider in self.balloon_sliders:
            balloons_row.addWidget(slider)
        balloons_col.addLayout(balloons_row, 1)
        layout.addLayout(balloons_col, 1)

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        return label
