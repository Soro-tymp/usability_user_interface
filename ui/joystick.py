"""
joystick.py — Custom analog joystick widget.

Draws a draggable handle inside a base circle and emits normalized
position signals for use in device control. Copied unmodified from the
main app's ui/joystick.py.
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import pyqtSignal, QPointF, QSize, Qt
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor
from ui.styles import COLOR_BACKGROUND_INPUT, COLOR_PRIMARY, COLOR_PRIMARY_PRESSED


class Joystick(QWidget):
    """
    Joystick is a custom QWidget for 2D analog input, emitting normalized position signals.
    """
    positionChanged = pyqtSignal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(100, 100)
        self._handle_pos = QPointF(0, 0)
        self._max_offset = 0
        self._base_radius = 0
        self._handle_radius = 0
        self._dragging = False
        self.setMouseTracking(True)

    def paintEvent(self, event):
        """Draw the joystick base and handle."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        current_width = self.width()
        current_height = self.height()
        short_dim = min(current_width, current_height)

        self._base_radius = short_dim / 2.0 - 5
        self._handle_radius = self._base_radius / 3.0
        self._max_offset = self._base_radius - self._handle_radius

        center = QPointF(current_width / 2.0, current_height / 2.0)

        painter.setBrush(QBrush(QColor(COLOR_BACKGROUND_INPUT)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, self._base_radius, self._base_radius)

        handle_center = center + self._handle_pos
        painter.setBrush(QBrush(QColor(COLOR_PRIMARY)))
        painter.setPen(QPen(QColor(COLOR_PRIMARY_PRESSED), 2))
        painter.drawEllipse(handle_center, self._handle_radius, self._handle_radius)

    def mousePressEvent(self, event):
        """Start dragging the joystick handle if inside the base circle."""
        if event.button() == Qt.MouseButton.LeftButton:
            center = QPointF(self.width() / 2, self.height() / 2)
            click_offset_from_center = QPointF(event.pos()) - center
            if (click_offset_from_center.x() ** 2 + click_offset_from_center.y() ** 2) ** 0.5 <= self._base_radius:
                self._dragging = True
                self._update_handle_pos(event.pos())
                self.update()

    def mouseMoveEvent(self, event):
        """Update handle position while dragging."""
        if self._dragging:
            self._update_handle_pos(event.pos())
            self.update()

    def mouseReleaseEvent(self, event):
        """Release the joystick handle and emit (0,0) position."""
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self._handle_pos = QPointF(0, 0)
            self.positionChanged.emit(0.0, 0.0)
            self.update()

    def _update_handle_pos(self, mouse_pos_in_widget):
        """Update the handle position and emit normalized coordinates."""
        center = QPointF(self.width() / 2, self.height() / 2)
        vec_to_mouse = QPointF(mouse_pos_in_widget) - center
        distance_to_mouse = (vec_to_mouse.x() ** 2 + vec_to_mouse.y() ** 2) ** 0.5

        if self._max_offset <= 1e-6:
            self._handle_pos = QPointF(0, 0)
            norm_x, norm_y = 0.0, 0.0
        elif distance_to_mouse == 0:
            self._handle_pos = QPointF(0, 0)
            norm_x, norm_y = 0.0, 0.0
        else:
            if distance_to_mouse > self._max_offset:
                self._handle_pos = (vec_to_mouse / distance_to_mouse) * self._max_offset
            else:
                self._handle_pos = vec_to_mouse

            norm_x = self._handle_pos.x() / self._max_offset
            norm_y = self._handle_pos.y() / self._max_offset

        self.positionChanged.emit(norm_x, norm_y)

    def sizeHint(self):
        """Suggest a default size for the joystick widget."""
        diameter = 100
        return QSize(diameter, diameter)

    def resizeEvent(self, event):
        """Update the widget on resize."""
        super().resizeEvent(event)
        self.update()
