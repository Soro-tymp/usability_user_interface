"""
balloon_slider.py — BalloonSlider: a vertical slider used as a live pressure
gauge for one actuator channel. Trimmed from the main app's
ui/balloon_slider.py (dropped the touch-drag-anywhere and settable-range
behavior — here it's driven read-only by BalloonPressuresBinding).
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSlider, QSizePolicy
from PyQt6.QtCore import Qt

PRESSURE_SLIDER_TICKS = 100


def convert_pressure_to_slider_int(pressure: float) -> int:
    return round(pressure * PRESSURE_SLIDER_TICKS)


def convert_pressure_slider_int_to_pressure(slider_value: int) -> float:
    return slider_value / PRESSURE_SLIDER_TICKS


class BalloonSlider(QWidget):
    """Vertical slider styled as a live pressure gauge for one channel."""

    def __init__(self, index: int, min_pressure: float = 0.0, max_pressure: float = 1.0, parent=None):
        super().__init__(parent)
        self._index = index

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        title = QLabel(f"P{index + 1}")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.slider = QSlider(Qt.Orientation.Vertical)
        self.slider.setMinimumWidth(20)
        self.slider.setMinimumHeight(120)
        self.slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.slider.setRange(
            convert_pressure_to_slider_int(min_pressure),
            convert_pressure_to_slider_int(max_pressure),
        )
        self.slider.setStyleSheet("""
            QSlider::groove:vertical {
                border: 1px solid #999999;
                width: 12px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #B1B1B1, stop:1 #c4c4c4);
                margin: 2px 0;
            }
            QSlider::handle:vertical {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #20B2AA, stop:1 #008B8B);
                border: 1px solid #006666;
                height: 18px;
                width: 18px;
                margin: 0 -3px;
                border-radius: 9px;
            }
        """)

        self.value_label = QLabel()
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.slider.valueChanged.connect(self._on_value_changed)
        self.set_pressure((min_pressure + max_pressure) / 2.0)

        layout.addWidget(title)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.value_label)

    def _on_value_changed(self, value: int):
        self.value_label.setText(f"{convert_pressure_slider_int_to_pressure(value):.2f}")

    def set_pressure(self, pressure: float):
        self.slider.setValue(convert_pressure_to_slider_int(pressure))

    def get_pressure(self) -> float:
        return convert_pressure_slider_int_to_pressure(self.slider.value())
