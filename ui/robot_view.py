"""
A cartoon of the robot in the ear canal, animated live from the same
data as the rest of the screen:
  - the 6 balloons follow the 6 pressures (same values as the P1..P6 sliders)
  - the robot shifts/tilts with the camera pose (the joysticks)
  - it slides in when the procedure starts, shows the needle once locked,
    and slides out at the end (set_insertion / set_needle, eased smoothly)

Two drawings side by side:
  - SIDE VIEW (left): ear canal cut lengthwise, entrance on the left, eardrum on
    the right. The balloon ring sits behind the tip, balloons at the back
    are drawn darker.
  - END VIEW (right): looking down the canal from outside. Balloon i sits at
    i*60° around the robot (same layout as MotionController.kinematics_from_drag:
    angle 0 = right, y pointing down like the joystick), numbered 1..6 like
    the sliders. Bigger + more saturated = higher pressure.

NB: it's a cartoon, the proportions are not the real device's.
"""

import math

from PyQt6.QtCore import Qt, QPointF, QRectF, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath, QLinearGradient
from PyQt6.QtWidgets import QWidget, QSizePolicy

from ui.motion_controller import NUM_CHANNELS
from ui.styles import COLOR_TEXT_SECONDARY

_TICK_MS = 30
_EASE = 0.12                        # fraction of the remaining distance covered per tick
_SKIN = QColor(205, 164, 142)
_SKIN_DARK = QColor(150, 105, 88)
_CANAL = QColor(70, 45, 40)
_DRUM = QColor(235, 200, 190)
_BODY = QColor("#D8DEE3")
_BODY_EDGE = QColor("#7C8790")
_BALLOON_EMPTY = QColor("#9FD9DB")
_BALLOON_FULL = QColor("#1E9EA3")
_TARGET_GREEN = QColor("#5EDA94")
_MAX_TILT_DEG = 12.0                # robot tilt drawn at full yaw/pitch


def _mix(a: QColor, b: QColor, f: float) -> QColor:
    f = max(0.0, min(1.0, f))
    return QColor(int(a.red() + (b.red() - a.red()) * f),
                  int(a.green() + (b.green() - a.green()) * f),
                  int(a.blue() + (b.blue() - a.blue()) * f))


class RobotView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(260, 150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._pressures = [0.0] * NUM_CHANNELS
        self._pose = (0.0, 0.0, 0.0, 0.0)
        self._on_target = False
        # current value / where it's going (eased every tick)
        self._insertion, self._insertion_target = 0.0, 0.0
        self._needle, self._needle_target = 0.0, 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self._on_tick)

    # inputs

    def set_pressures(self, pressures) -> None:
        self._pressures = list(pressures)
        self.update()

    def set_pose(self, tx: float, ty: float, yaw: float, pitch: float) -> None:
        self._pose = (tx, ty, yaw, pitch)
        self.update()

    def set_on_target(self, on_target: bool) -> None:
        self._on_target = on_target
        self.update()

    def set_insertion(self, value: float, animate: bool = True) -> None:
        # 0 = outside the ear, 1 = fully inserted
        self._insertion_target = value
        if not animate:
            self._insertion = value
        self._kick()

    def set_needle(self, value: float, animate: bool = True) -> None:
        # 0 = needle hidden, 1 = needle touching the eardrum
        self._needle_target = value
        if not animate:
            self._needle = value
        self._kick()

    def _kick(self) -> None:
        if not self._timer.isActive():
            self._timer.start()
        self.update()

    def _on_tick(self) -> None:
        done = True
        for name in ("_insertion", "_needle"):
            cur, target = getattr(self, name), getattr(self, name + "_target")
            if abs(target - cur) > 0.002:
                setattr(self, name, cur + (target - cur) * _EASE)
                done = False
            else:
                setattr(self, name, target)
        if done:
            self._timer.stop()
        self.update()

    # drawing

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        end_size = min(h - 18, w * 0.30)
        side_rect = QRectF(0, 16, w - end_size - 14, h - 18)
        end_rect = QRectF(w - end_size, 16 + (h - 18 - end_size) / 2, end_size, end_size)

        painter.setPen(QColor(COLOR_TEXT_SECONDARY))
        font = QFont(painter.font())
        font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(QRectF(side_rect.left(), 0, side_rect.width(), 14),
                         Qt.AlignmentFlag.AlignHCenter, "Robot in the ear canal")
        painter.drawText(QRectF(end_rect.left() - 10, 0, end_rect.width() + 20, 14),
                         Qt.AlignmentFlag.AlignHCenter, "Balloons (P1–P6)")

        self._paint_side(painter, side_rect)
        self._paint_end(painter, end_rect)

    def _paint_side(self, painter: QPainter, r: QRectF) -> None:
        tx, ty, yaw, pitch = self._pose
        canal_half = r.height() * 0.34
        cy = r.center().y()
        entrance_x = r.left() + r.width() * 0.22
        drum_x = r.right() - r.width() * 0.08

        # head/skin around the canal, the canal itself, then the eardrum
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_SKIN)
        painter.drawRoundedRect(QRectF(entrance_x, r.top(), r.right() - entrance_x, r.height()), 10, 10)
        grad = QLinearGradient(entrance_x, 0, drum_x, 0)
        grad.setColorAt(0.0, _SKIN_DARK)
        grad.setColorAt(1.0, _CANAL)
        painter.setBrush(QBrush(grad))
        painter.drawRect(QRectF(entrance_x, cy - canal_half, drum_x - entrance_x, 2 * canal_half))
        tilt = canal_half * math.tan(math.radians(15))   # eardrum is tilted, like in the 3D view
        drum = QPainterPath()
        drum.moveTo(drum_x - tilt, cy - canal_half)
        drum.lineTo(drum_x + tilt, cy + canal_half)
        painter.setPen(QPen(_DRUM, 4))
        painter.drawPath(drum)

        # robot: tip position from the insertion, offset by translation (ty),
        # tilted by pitch around the balloon ring
        body_r = canal_half * 0.32
        length = r.width() * 0.62
        # tip goes from just outside the entrance (0) to near the eardrum (1),
        # leaving room for the camera cone / needle
        tip_start, tip_end = entrance_x - body_r, drum_x - canal_half * 0.9
        tip_x = tip_start + (tip_end - tip_start) * self._insertion
        ring_x = tip_x - body_r * 2.2
        center_y = cy + ty * canal_half * 0.2
        painter.save()
        # nothing goes through the canal walls: balloons pressing on a wall get flattened
        clip = QPainterPath()
        clip.addRect(QRectF(entrance_x, cy - canal_half, r.right() - entrance_x, 2 * canal_half))
        clip.addRect(QRectF(r.left(), r.top(), entrance_x - r.left(), r.height()))
        painter.setClipPath(clip)
        painter.translate(ring_x, center_y)
        painter.rotate(pitch * _MAX_TILT_DEG)

        # field of view of the camera at the tip, green when on target
        fov = QPainterPath()
        tip_rel = tip_x - ring_x
        fov.moveTo(tip_rel, 0)
        fov.lineTo(tip_rel + canal_half * 1.6, -canal_half * 0.9)
        fov.lineTo(tip_rel + canal_half * 1.6, canal_half * 0.9)
        fov.closeSubpath()
        cone = _TARGET_GREEN if self._on_target else QColor(255, 255, 255)
        cone.setAlpha(55 if self._insertion > 0.9 else 0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(cone)
        painter.drawPath(fov)

        balloons = self._side_balloons(body_r, canal_half)
        for b in balloons:                     # back balloons first (behind the body)
            if b[0] < 0:
                self._draw_side_balloon(painter, b, dark=True)

        painter.setPen(QPen(_BODY_EDGE, 1.5))
        painter.setBrush(_BODY)
        painter.drawRoundedRect(QRectF(tip_rel - length, -body_r, length, 2 * body_r), body_r, body_r)
        painter.setBrush(QColor("#30343A"))      # camera lens
        painter.drawEllipse(QPointF(tip_rel - body_r * 0.35, 0), body_r * 0.35, body_r * 0.35)

        if self._needle > 0.01:
            # needle travels from the tip to the eardrum
            reach = (drum_x - tip_x) * self._needle
            painter.setPen(QPen(QColor("#C0C8D0"), 2))
            painter.drawLine(QPointF(tip_rel, body_r * 0.4), QPointF(tip_rel + reach, body_r * 0.4))
            if self._needle > 0.97:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#4FA3FF"))
                painter.drawEllipse(QPointF(tip_rel + reach, body_r * 0.4), 4, 4)

        for b in balloons:                     # front balloons on top
            if b[0] >= 0:
                self._draw_side_balloon(painter, b, dark=False)
        painter.restore()

    def _side_balloons(self, body_r: float, canal_half: float) -> list:
        # (depth, y, size, pressure, index): balloon i around the body, seen
        # from the side. The side view shows the vertical (y) plane; the
        # horizontal component becomes the depth (in front/behind the body).
        # Sized so that at ~0.7 (the inflation threshold) they touch the canal wall.
        max_size = (canal_half - body_r) / 1.6
        out = []
        for i, p in enumerate(self._pressures):
            a = math.radians(i * 360.0 / NUM_CHANNELS)
            size = max_size * (0.3 + p)
            depth, y = math.cos(a), math.sin(a) * (body_r + size * 0.8)
            out.append((depth, y, size, p, i))
        return sorted(out, key=lambda b: b[0])

    def _draw_side_balloon(self, painter, b, dark: bool) -> None:
        _depth, y, size, p, _i = b
        color = _mix(_BALLOON_EMPTY, _BALLOON_FULL, p)
        if dark:
            color = color.darker(140)
        painter.setPen(QPen(color.darker(150), 1))
        painter.setBrush(color)
        painter.drawEllipse(QPointF(0, y), size * 1.25, size * 0.8)

    def _paint_end(self, painter: QPainter, r: QRectF) -> None:
        tx, ty, _yaw, _pitch = self._pose
        c = r.center()
        canal_r = r.width() / 2 - 4
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_SKIN)
        painter.drawEllipse(c, canal_r + 4, canal_r + 4)
        painter.setBrush(_CANAL)
        painter.drawEllipse(c, canal_r, canal_r)

        body_r = canal_r * 0.28
        # fades in as the robot goes in (seen from outside, it's "behind" the entrance)
        alpha = int(255 * max(0.15, min(1.0, self._insertion)))
        center = QPointF(c.x() + tx * canal_r * 0.25, c.y() + ty * canal_r * 0.25)
        font = QFont(painter.font())
        font.setBold(True)
        for i, p in enumerate(self._pressures):
            a = math.radians(i * 360.0 / NUM_CHANNELS)
            size = body_r * (0.30 + 0.62 * p)
            dist = body_r + size * 0.85
            pos = QPointF(center.x() + math.cos(a) * dist, center.y() + math.sin(a) * dist)
            color = _mix(_BALLOON_EMPTY, _BALLOON_FULL, p)
            color.setAlpha(alpha)
            painter.setPen(QPen(color.darker(150), 1))
            painter.setBrush(color)
            painter.drawEllipse(pos, size, size)
            font.setPixelSize(max(7, int(size * 0.9)))
            painter.setFont(font)
            painter.setPen(QColor(255, 255, 255, alpha))
            painter.drawText(QRectF(pos.x() - size, pos.y() - size, 2 * size, 2 * size),
                             Qt.AlignmentFlag.AlignCenter, str(i + 1))
        body = QColor(_BODY)
        body.setAlpha(alpha)
        painter.setPen(QPen(_BODY_EDGE, 1.5))
        painter.setBrush(body)
        painter.drawEllipse(center, body_r, body_r)
        painter.setBrush(QColor(48, 52, 58, alpha))
        painter.drawEllipse(center, body_r * 0.35, body_r * 0.35)
