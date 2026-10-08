"""
A cartoon of the robot in the ear canal, animated live from the same
data as the rest of the screen:
  - 2 rings of 3 balloons: FRONT ring (P1-P3, near the tip, teal) and BACK
    ring (P4-P6, orange), same colours as the slider handles
  - front balloons at 0°, 120°, 240° and back balloons in between, at 60°, 180°,
    300° (angle 0 = right, y pointing down like the joystick)
  - the balloons are round, filling the space between the robot and the wall
  - while inflating, the balloons grow until they touch the canal wall at the
    inflation threshold. After that (set_seated(True)) they always touch the
    wall: when the robot moves, the ones on one side get squashed and the ones on
    the other side stretched, and the pressure shows as how deep the colour is
  - a balloon whose pressure is changing glows white, so you can see which
    balloons are doing the work
  - the robot shifts/tilts with the camera pose: translation moves both rings
    the same way, rotation moves the front ring one way and the back ring the
    other way (= tilt)
  - the robot is just a short head with the 2 rings, followed by thin tubes/wires
    (air for the front ring, air for the back ring, camera cable) going out of the ear
  - it slides in when the procedure starts, shows the needle once locked, and
    slides out at the end (set_insertion / set_needle, eased smoothly)

Drawings: SIDE VIEW (left, canal cut lengthwise, entrance on the left, eardrum on the
right) and two END VIEWS (right, looking down the canal: front ring and back ring).

SCALE: everything is drawn from the sizes in millimetres below (canal and robot),
so the proportions are real. The robot ones are GUESSES: put the real device's here.
"""

import math

from PyQt6.QtCore import Qt, QPointF, QRectF, QTimer
from PyQt6.QtGui import (QPainter, QColor, QPen, QFont, QFontMetrics, QPainterPath,
                         QLinearGradient, QBrush)
from PyQt6.QtWidgets import QWidget, QSizePolicy

from ui.motion_controller import NUM_CHANNELS
from ui.styles import COLOR_TEXT_SECONDARY

FRONT_COLOR = QColor("#1E9EA3")     # balloons P1-P3
BACK_COLOR = QColor("#F08A24")      # balloons P4-P6
# Around the robot (angle 0 = right, y down like the joystick). The back balloons sit
# IN BETWEEN the front ones: seen from the end, the 6 alternate front/back every 60°.
FRONT_ANGLES_DEG = (0.0, 120.0, 240.0)    # P1, P2, P3
BACK_ANGLES_DEG = (60.0, 180.0, 300.0)    # P4, P5, P6


def balloon_angle(index: int) -> float:
    return (FRONT_ANGLES_DEG + BACK_ANGLES_DEG)[index]

_TICK_MS = 30
_EASE = 0.12                        # fraction of the remaining distance covered per tick
_GLOW_DECAY = 0.06                  # per tick
_SKIN = QColor(205, 164, 142)
_SKIN_DARK = QColor(150, 105, 88)
_CANAL = QColor(70, 45, 40)
_DRUM = QColor("#EDE3DF")            # pearly grey-pink membrane
_MIDDLE_EAR = QColor(58, 38, 52)
_LABEL = QColor(74, 46, 37)
_MEDICINE = QColor("#4FA3FF")
_BODY = QColor("#D8DEE3")
_BODY_EDGE = QColor("#7C8790")
_TARGET_GREEN = QColor("#5EDA94")
# REAL SIZES (mm). Ear canal: average adult. Robot: guesses, replace with the device's.
CANAL_DIAMETER_MM = 7.5
CANAL_LENGTH_MM = 25.0
ROBOT_DIAMETER_MM = 3.0
ROBOT_LENGTH_MM = 8.5          # from the tip to the back of the head (the wires start there)
TIP_TO_FRONT_RING_MM = 2.4     # tip -> centre of the front balloon ring
TIP_TO_BACK_RING_MM = 6.4      # tip -> centre of the back balloon ring
BALLOON_LENGTH_MM = 2.8        # balloon size along the canal, when inflated
WIRE_DIAMETER_MM = 0.35
CAMERA_DISTANCE_MM = 4.0       # how close the tip gets to the eardrum
MIN_CANAL_SHOWN = 0.6          # narrow screens: show at least this inner part of the canal, bigger
ROBOT_SIZE = ROBOT_DIAMETER_MM / CANAL_DIAMETER_MM   # robot radius / canal radius
_SHIFT = 0.20                       # ring offset at full translation (x canal radius)
_TILT = 0.05                        # extra ring offset at full rotation (front +, back -)
_WIRE_COLORS = (QColor("#1E9EA3"), QColor("#F08A24"), QColor("#8A949C"))  # front air, back air, camera


def ring_color(index: int) -> QColor:
    return FRONT_COLOR if index < 3 else BACK_COLOR


def _pressure_color(index: int, p: float) -> QColor:
    # light tint of the ring colour at 0 (still tells front from back), full colour at 1
    base = ring_color(index)
    pale = QColor(240, 242, 242)
    f = 0.25 + 0.75 * max(0.0, min(1.0, p))
    return QColor(int(pale.red() + (base.red() - pale.red()) * f),
                  int(pale.green() + (base.green() - pale.green()) * f),
                  int(pale.blue() + (base.blue() - pale.blue()) * f))


class RobotView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(260, 150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._pressures = [0.0] * NUM_CHANNELS
        self._glow = [0.0] * NUM_CHANNELS
        self._pose = (0.0, 0.0, 0.0, 0.0)
        self._on_target = False
        self._seated = False             # True once inflated: balloons touch the wall
        self.contact_level = 0.7         # pressure at which they first touch it
        # current value / where it's going (eased every tick)
        self._insertion, self._insertion_target = 0.0, 0.0
        self._needle, self._needle_target = 0.0, 0.0
        self._drop_y = None              # where the medicine went on the eardrum (x canal radius)
        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self._on_tick)

    # inputs

    def set_pressures(self, pressures) -> None:
        for i, p in enumerate(pressures):
            if abs(p - self._pressures[i]) > 0.002:
                self._glow[i] = 1.0
        self._pressures = list(pressures)
        self._kick()

    def set_pose(self, tx: float, ty: float, yaw: float, pitch: float) -> None:
        self._pose = (tx, ty, yaw, pitch)
        self.update()

    def set_on_target(self, on_target: bool) -> None:
        self._on_target = on_target
        self.update()

    def set_seated(self, seated: bool) -> None:
        self._seated = seated
        self.update()

    def set_insertion(self, value: float, animate: bool = True) -> None:
        # 0 = outside the ear, 1 = fully inserted
        self._insertion_target = value
        if value < 1.0:
            self._drop_y = None          # new procedure: no medicine on the eardrum yet
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
        for i, g in enumerate(self._glow):
            if g > 0:
                self._glow[i] = max(0.0, g - _GLOW_DECAY)
                done = False
        if done:
            self._timer.stop()
        self.update()

    # geometry shared by both views

    def _ring_offsets(self) -> dict:
        # where each ring's centre sits in the canal cross-section (x, y), in
        # canal radii: translation moves both, rotation moves them opposite ways
        tx, ty, yaw, pitch = self._pose
        return {"front": (tx * _SHIFT + yaw * _TILT, ty * _SHIFT + pitch * _TILT),
                "back": (tx * _SHIFT - yaw * _TILT, ty * _SHIFT - pitch * _TILT)}

    def _fill(self, p: float) -> float:
        # how much of the gap to the wall a balloon fills (1 = touching)
        if self._seated:
            return 1.0
        return max(0.0, min(1.0, p / self.contact_level))

    # drawing

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        end_size = min((h - 34) / 2, w * 0.22)
        side_rect = QRectF(0, 16, w - end_size - 16, h - 18)
        front_rect = QRectF(w - end_size - 4, 16, end_size, end_size)
        back_rect = QRectF(w - end_size - 4, h - end_size - 2, end_size, end_size)

        font = QFont(painter.font())
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(QColor(COLOR_TEXT_SECONDARY))
        painter.drawText(QRectF(side_rect.left(), 0, side_rect.width(), 14),
                         Qt.AlignmentFlag.AlignHCenter, "Robot in the ear canal")
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(FRONT_COLOR)
        painter.drawText(QRectF(front_rect.left() - 60, 0, front_rect.width() + 64, 14),
                         Qt.AlignmentFlag.AlignRight, "Front ring (P1–P3)")
        painter.setPen(BACK_COLOR)
        painter.drawText(QRectF(back_rect.left() - 60, back_rect.top() - 15, back_rect.width() + 64, 14),
                         Qt.AlignmentFlag.AlignRight, "Back ring (P4–P6)")

        self._paint_side(painter, side_rect)
        offsets = self._ring_offsets()
        self._paint_end(painter, front_rect, offsets["front"], 0)
        self._paint_end(painter, back_rect, offsets["back"], 3)

    def _paint_side(self, painter: QPainter, r: QRectF) -> None:
        # pixels per mm: the whole canal fits, with some room on the left for the wires.
        # When the view is narrow that makes everything tiny, so we zoom in and only
        # show the inner part of the canal (the entrance goes past the left edge).
        ppm = min(r.height() * 0.66 / CANAL_DIAMETER_MM,
                  max(r.width() * 0.80 / CANAL_LENGTH_MM,
                      r.width() * 0.95 / (CANAL_LENGTH_MM * MIN_CANAL_SHOWN)))
        canal_half = CANAL_DIAMETER_MM / 2 * ppm
        cy = r.center().y()
        middle_ear_w = max(18.0, 2.5 * ppm)      # a bit of the middle ear, behind the eardrum
        drum_x = r.right() - middle_ear_w
        entrance_x = drum_x - CANAL_LENGTH_MM * ppm
        top_wall, bottom_wall = cy - canal_half, cy + canal_half

        # head/skin around the canal, the canal itself, then the eardrum
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_SKIN)
        skin_left = max(entrance_x, r.left())
        painter.drawRoundedRect(QRectF(skin_left, r.top(), r.right() - skin_left, r.height()), 10, 10)
        # the eardrum: a thin membrane closing the canal, tilted (like in the 3D view)
        # and pulled in at its centre (like a shallow cone towards the middle ear)
        tilt = canal_half * math.tan(math.radians(15))
        drum_top = QPointF(drum_x - tilt, top_wall)
        drum_bottom = QPointF(drum_x + tilt, bottom_wall)
        drum_ctrl = QPointF(drum_x + canal_half * 0.45, cy)

        def drum_x_at(y):
            t = max(0.0, min(1.0, (y - top_wall) / (2 * canal_half)))
            return ((1 - t) ** 2 * drum_top.x() + 2 * t * (1 - t) * drum_ctrl.x()
                    + t * t * drum_bottom.x())

        # middle ear: the small air space behind the eardrum
        middle = QPainterPath(drum_top)
        middle.quadTo(drum_ctrl, drum_bottom)
        middle.lineTo(QPointF(r.right() - 2, bottom_wall + canal_half * 0.25))
        middle.lineTo(QPointF(r.right() - 2, top_wall - canal_half * 0.25))
        middle.closeSubpath()
        painter.setBrush(_MIDDLE_EAR)
        painter.drawPath(middle)
        # ear canal, up to the eardrum
        canal = QPainterPath(QPointF(entrance_x, top_wall))
        canal.lineTo(drum_top)
        canal.quadTo(drum_ctrl, drum_bottom)
        canal.lineTo(QPointF(entrance_x, bottom_wall))
        canal.closeSubpath()
        grad = QLinearGradient(entrance_x, 0, drum_x, 0)
        grad.setColorAt(0.0, _SKIN_DARK)
        grad.setColorAt(1.0, _CANAL)
        painter.setBrush(QBrush(grad))
        painter.drawPath(canal)
        drum = QPainterPath(drum_top)
        drum.quadTo(drum_ctrl, drum_bottom)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(_DRUM, max(3.0, 0.25 * ppm)))
        painter.drawPath(drum)
        # tiny ear bone (malleus) attached to the middle of the eardrum
        painter.setPen(QPen(QColor("#E8D9B5"), max(2.0, 0.3 * ppm)))
        umbo = QPointF(drum_x_at(cy), cy)
        painter.drawLine(umbo, QPointF(umbo.x() + middle_ear_w * 0.5, top_wall - canal_half * 0.1))
        # medicine left on the eardrum
        if self._drop_y is not None:
            y = cy + self._drop_y * canal_half
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(_MEDICINE)
            painter.drawEllipse(QPointF(drum_x_at(y), y), max(3.0, 0.35 * ppm), max(4.0, 0.5 * ppm))

        # labels, so that everyone knows what they're looking at
        band = r.height() / 2 - canal_half
        font = QFont(painter.font())
        font.setPixelSize(int(max(9, min(13, band * 0.45))))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(_LABEL)
        fm = QFontMetrics(font)
        canal_text, drum_text, middle_text = "EAR CANAL  ⟶", "EARDRUM ↘", "middle ear ↗"
        canal_left = max(entrance_x, r.left()) + 8
        label_right = r.right() - 4
        top_band = QRectF(canal_left, top_wall - band, label_right - canal_left, band)
        bottom_band = QRectF(canal_left, bottom_wall, label_right - canal_left, band)
        left, right = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
        painter.drawText(top_band, right, drum_text)
        painter.drawText(bottom_band, right, middle_text)
        # "EAR CANAL" top-left, or bottom-left if it would bump into "EARDRUM"
        if fm.horizontalAdvance(canal_text + drum_text) + 20 < top_band.width():
            painter.drawText(top_band, left, canal_text)
        elif fm.horizontalAdvance(canal_text + middle_text) + 20 < bottom_band.width():
            painter.drawText(bottom_band, left, canal_text)

        # nothing goes through the canal walls (balloons pressing on them get flattened)
        painter.save()
        clip = QPainterPath()
        clip.addRect(QRectF(entrance_x, top_wall, r.right() - entrance_x, 2 * canal_half))
        if entrance_x > r.left():
            clip.addRect(QRectF(r.left(), r.top(), entrance_x - r.left(), r.height()))
        painter.setClipPath(clip)

        body_r = ROBOT_DIAMETER_MM / 2 * ppm
        ring_w = BALLOON_LENGTH_MM / 2 * ppm       # half-length of a balloon along the canal
        # tip goes from just outside the entrance (0) to near the eardrum (1)
        tip_start = entrance_x - 1.0 * ppm
        tip_end = drum_x - CAMERA_DISTANCE_MM * ppm
        tip_x = tip_start + (tip_end - tip_start) * self._insertion
        offsets = self._ring_offsets()
        front_x, back_x = tip_x - TIP_TO_FRONT_RING_MM * ppm, tip_x - TIP_TO_BACK_RING_MM * ppm
        front_y = cy + offsets["front"][1] * canal_half
        back_y = cy + offsets["back"][1] * canal_half
        angle = math.degrees(math.atan2(front_y - back_y, front_x - back_x))

        # balloons that point away from the viewer go behind the body
        rings = [(front_x, front_y, 0), (back_x, back_y, 3)]
        # seen from the side, cos(angle) = towards the viewer: balloons pointing
        # away are drawn first (behind the body), the others after it
        balloons = [(x, y, first + k) for x, y, first in rings for k in range(3)]
        for x, y, i in balloons:
            if math.cos(math.radians(balloon_angle(i))) < -0.01:
                self._draw_side_balloon(painter, i, x, y, body_r, ring_w, top_wall, bottom_wall)

        # body, camera cone, needle, wires: in the robot's own (tilted) frame,
        # origin at the back ring
        painter.save()
        painter.translate(back_x, back_y)
        painter.rotate(angle)
        ring_gap = math.hypot(front_x - back_x, front_y - back_y)
        tip_rel = ring_gap + TIP_TO_FRONT_RING_MM * ppm
        tail = tip_rel - ROBOT_LENGTH_MM * ppm
        fov = QPainterPath()
        fov.moveTo(tip_rel, 0)
        fov.lineTo(tip_rel + CAMERA_DISTANCE_MM * ppm, -canal_half * 0.9)
        fov.lineTo(tip_rel + CAMERA_DISTANCE_MM * ppm, canal_half * 0.9)
        fov.closeSubpath()
        cone = QColor(_TARGET_GREEN if self._on_target else QColor(255, 255, 255))
        cone.setAlpha(60 if self._insertion > 0.9 else 0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(cone)
        painter.drawPath(fov)

        # thin tubes/wires going back out of the ear (air for the front and back
        # balloons, camera cable), sagging a little
        for k, color in enumerate(_WIRE_COLORS):
            y0 = (k - 1) * body_r * 0.5
            wire = QPainterPath(QPointF(tail + 1, y0))
            far = tail - r.width()
            wire.cubicTo(QPointF(tail - r.width() * 0.3, y0),
                         QPointF(far + r.width() * 0.3, y0 + body_r * 2),
                         QPointF(far, y0 + body_r * 2))
            painter.setPen(QPen(color, max(1.5, WIRE_DIAMETER_MM * ppm)))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(wire)
        painter.setPen(QPen(_BODY_EDGE, 1.5))
        painter.setBrush(_BODY)
        painter.drawRoundedRect(QRectF(tail, -body_r, tip_rel - tail, 2 * body_r), body_r, body_r)
        painter.setBrush(QColor("#30343A"))      # camera lens
        painter.drawEllipse(QPointF(tip_rel - body_r * 0.4, 0), body_r * 0.32, body_r * 0.32)
        if self._needle > 0.01:
            needle_y = front_y + body_r * 0.45
            reach = (drum_x_at(needle_y) - tip_x) * self._needle
            painter.setPen(QPen(QColor("#C0C8D0"), max(2.0, 0.2 * ppm)))
            painter.drawLine(QPointF(tip_rel, body_r * 0.45), QPointF(tip_rel + reach, body_r * 0.45))
            if self._needle > 0.97:
                # the medicine goes onto the eardrum, and stays there
                self._drop_y = (needle_y - cy) / canal_half
        painter.restore()

        for x, y, i in balloons:
            if math.cos(math.radians(balloon_angle(i))) >= -0.01:
                self._draw_side_balloon(painter, i, x, y, body_r, ring_w, top_wall, bottom_wall)
        painter.restore()

    def _draw_side_balloon(self, painter, i, x, y, body_r, ring_w, top_wall, bottom_wall):
        p = self._pressures[i]
        fill = self._fill(p)
        a = math.radians(balloon_angle(i))
        color = _pressure_color(i, p)
        if math.cos(a) < 0:
            color = color.darker(118)            # behind the body
        bulge = ring_w * (0.5 + 0.5 * fill)      # half-size along the canal
        path = QPainterPath()
        if abs(math.sin(a)) < 0.3:
            # pointing at (or away from) the viewer: a round balloon over the body
            ry = body_r * (0.6 + 0.55 * fill)
            path.addEllipse(QPointF(x, y), bulge, ry)
            shine = QPointF(x - bulge * 0.35, y - ry * 0.45)
        else:
            # pointing down or up: a round balloon from the body to the wall. When it
            # touches, it goes a little "past" the wall and the clipping flattens it.
            direction = 1 if math.sin(a) > 0 else -1
            start = y + direction * body_r * 0.55
            wall = bottom_wall if direction > 0 else top_wall
            length = max(body_r * 0.4, abs(wall - start) * fill + (ring_w * 0.25 if self._seated else 0))
            cy = start + direction * length / 2
            path.addEllipse(QPointF(x, cy), bulge, length / 2)
            shine = QPointF(x - bulge * 0.35, cy - length * 0.22)
        self._paint_balloon(painter, i, path, color, shine, bulge * 0.25)

    def _paint_balloon(self, painter, i, path: QPainterPath, color: QColor, shine: QPointF,
                       shine_r: float, alpha: int = 255) -> None:
        # balloon body + a little white shine, + a white outline while its pressure changes
        color = QColor(color)
        color.setAlpha(alpha)
        painter.setPen(QPen(color.darker(150), 1))
        painter.setBrush(color)
        painter.drawPath(path)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, int(110 * alpha / 255)))
        painter.drawEllipse(shine, shine_r * 1.4, shine_r)
        if self._glow[i] > 0:
            painter.setPen(QPen(QColor(255, 255, 255, int(230 * self._glow[i] * alpha / 255)), 2.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

    def _paint_end(self, painter: QPainter, r: QRectF, offset, first: int) -> None:
        c = r.center()
        canal_r = r.width() / 2 - 3
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_SKIN)
        painter.drawEllipse(c, canal_r + 3, canal_r + 3)
        painter.setBrush(_CANAL)
        painter.drawEllipse(c, canal_r, canal_r)
        painter.save()
        wall = QPainterPath()
        wall.addEllipse(c, canal_r, canal_r)
        painter.setClipPath(wall)                  # balloons flatten against the wall

        body_r = canal_r * ROBOT_SIZE
        # fades in as the robot goes in (seen from outside it's behind the entrance)
        alpha = int(255 * max(0.15, min(1.0, self._insertion)))
        center = QPointF(c.x() + offset[0] * canal_r, c.y() + offset[1] * canal_r)
        rel = (offset[0] * canal_r, offset[1] * canal_r)
        labels = []
        for i in range(first, first + 3):
            angle_deg = balloon_angle(i)
            p = self._pressures[i]
            fill = self._fill(p)
            a = math.radians(angle_deg)
            d = (math.cos(a), math.sin(a))
            # distance from the ring centre to the wall along d (circle intersection)
            dot = rel[0] * d[0] + rel[1] * d[1]
            to_wall = -dot + math.sqrt(max(0.0, dot * dot - (rel[0] ** 2 + rel[1] ** 2) + canal_r ** 2))
            start = body_r * 0.7
            gap = max(2.0, to_wall - start)
            length = max(body_r * 0.4, gap * fill + (canal_r * 0.08 if self._seated else 0))
            bulge = min(canal_r * 0.36, length * 0.6) * (0.6 + 0.4 * fill)
            painter.save()
            painter.translate(center)
            painter.rotate(angle_deg)
            painter.translate(start, 0)
            path = QPainterPath()
            path.addEllipse(QPointF(length / 2, 0), length / 2, bulge)
            self._paint_balloon(painter, i, path, _pressure_color(i, p),
                                QPointF(length * 0.55, -bulge * 0.45), bulge * 0.22, alpha)
            painter.restore()
            dist = start + min(length, to_wall - start) * 0.6
            labels.append((QPointF(center.x() + d[0] * dist, center.y() + d[1] * dist), i, p))
        painter.restore()

        body = QColor(_BODY)
        body.setAlpha(alpha)
        painter.setPen(QPen(_BODY_EDGE, 1.5))
        painter.setBrush(body)
        painter.drawEllipse(center, body_r, body_r)
        painter.setBrush(QColor(48, 52, 58, alpha))
        painter.drawEllipse(center, body_r * 0.35, body_r * 0.35)
        font = QFont(painter.font())
        font.setBold(True)
        font.setPixelSize(max(8, int(canal_r * 0.2)))
        painter.setFont(font)
        for pos, i, p in labels:
            painter.setPen(QColor(255, 255, 255, alpha) if p > 0.45 else QColor(60, 60, 60, alpha))
            painter.drawText(QRectF(pos.x() - 12, pos.y() - 10, 24, 20),
                             Qt.AlignmentFlag.AlignCenter, str(i + 1))

