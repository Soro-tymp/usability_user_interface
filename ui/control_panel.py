from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton

from ui.balloon_slider import BalloonSlider
from ui.joystick import Joystick
from ui.motion_controller import NUM_CHANNELS
from ui.robot_view import RobotView, ring_color


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

        # cartoon of the robot, balloons linked to the same pressures as the sliders
        # (hidden by default, main_procedure.py shows it in the game)
        self.robot_view = RobotView()
        self.robot_view.setVisible(False)
        layout.addWidget(self.robot_view, 3)

        balloons_col = QVBoxLayout()
        balloons_col.addWidget(self._label("Balloon pressures (live)"))
        balloons_row = QHBoxLayout()
        self.balloon_sliders = [BalloonSlider(i) for i in range(NUM_CHANNELS)]
        for slider in self.balloon_sliders:
            balloons_row.addWidget(slider)
        balloons_col.addLayout(balloons_row, 1)
        layout.addLayout(balloons_col, 2)

    def show_robot(self) -> None:
        # Game: robot cartoon + slider handles in the colours of its balloon rings
        self.robot_view.setVisible(True)
        for i, slider in enumerate(self.balloon_sliders):
            color = ring_color(i)
            slider.set_handle_color(color.lighter(125).name(), color.name(), color.darker(150).name())

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        return label
