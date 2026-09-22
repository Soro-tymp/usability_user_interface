"""
camera_view.py — CameraView: a placeholder for the endoscope camera feed.

Styled the same way the main app's video display looks when there's no
live stream (see ui/endoscope_view.py's EndoscopeView there): a dark
background with a centered image, scaled to fit while keeping its aspect
ratio. This demo has no camera attached, so instead of a live video feed
it always shows a static placeholder photo
(ui/images/camera_placeholder.png — a synthetic illustration generated for
this demo, not a real patient image).
"""

import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPixmap, QColor
from PyQt6.QtWidgets import QWidget, QSizePolicy

from ui.styles import COLOR_BACKGROUND_INPUT

_IMAGE_PATH = os.path.join(os.path.dirname(__file__), "images", "camera_placeholder.png")


class CameraView(QWidget):
    """Always shows the placeholder photo — there's no live camera here."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(160, 120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._pixmap = QPixmap(_IMAGE_PATH) if os.path.exists(_IMAGE_PATH) else QPixmap()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(COLOR_BACKGROUND_INPUT))

        if not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            x = (self.width() - scaled.width()) / 2
            y = (self.height() - scaled.height()) / 2
            painter.drawPixmap(int(x), int(y), scaled)
        else:
            painter.setPen(QColor("#AAAAAA"))
            font = painter.font()
            font.setPointSize(14)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No camera image")
