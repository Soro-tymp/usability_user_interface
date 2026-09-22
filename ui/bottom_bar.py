"""
bottom_bar.py — BottomBar: horizontal strip across the bottom of the
window showing which procedure step is current.

A much simpler stand-in for the main app's ui/bottom_bar.py (same name),
which paints a dotted stage track with a custom QPainter. This just bolds
and colors the current step's label among plain text labels — same idea
(show progress across a fixed bar at the bottom), simpler implementation.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel

from ui.styles import COLOR_PRIMARY, COLOR_TEXT_SECONDARY


class BottomBar(QWidget):
    def __init__(self, steps: list[str], parent=None):
        super().__init__(parent)
        self.setObjectName("bottom-bar")
        self.setFixedHeight(44)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(12)
        layout.addStretch()

        self._labels: list[QLabel] = []
        for i, step in enumerate(steps):
            if i > 0:
                sep = QLabel("—")
                sep.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY};")
                layout.addWidget(sep)
            label = QLabel(step)
            self._labels.append(label)
            layout.addWidget(label)

        layout.addStretch()
        self.set_current_index(0)

    def set_current_index(self, index: int) -> None:
        for i, label in enumerate(self._labels):
            if i == index:
                label.setStyleSheet(f"color: {COLOR_PRIMARY}; font-weight: 700;")
            else:
                label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY};")
