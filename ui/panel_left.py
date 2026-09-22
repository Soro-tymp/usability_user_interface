"""
panel_left.py — LeftPanel: fixed-width left sidebar.

Trimmed down from the main app's ui/panel_left.py (LeftSidePanel): keeps
just the two buttons this demo needs — Control (toggles the ControlPanel
below the camera view) and Back (steps the procedure wizard backward) —
and drops everything else LeftSidePanel has (device toggles, the air
compressor bar, the system status LED), since none of that applies without
real hardware.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton

SIDE_PANEL_WIDTH = 190


class LeftPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("left-panel")
        self.setFixedWidth(SIDE_PANEL_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(8)

        layout.addStretch()

        self.btn_back = QPushButton("Back")
        layout.addWidget(self.btn_back)
