"""
It's what a camera on the tip of the robot would see inside the ear
canal. The 3D maths is in ui/endoscope_geometry.py; this file only
does the drawing.

The joysticks move the CAMERA, not a cursor:
  - translation slides the camera sideways, so near walls move more
    than the eardrum (parallax)
  - rotation turns the camera, so the eardrum is seen at an angle

The cross in the middle never moves, while showing where the camera, and so
the needle, is pointing. It turns green when that point is inside the
green target zone on the eardrum (_TARGET_ZONE).

The camera position is set by ui/camera_pose_binding.py through
set_pose().
"""

import os

from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import (QPainter, QPixmap, QColor, QPen, QPainterPath, QRadialGradient,
                         QBrush, QFont, QPolygonF, QTransform)
from PyQt6.QtWidgets import QWidget, QSizePolicy

from ui import endoscope_geometry as geo
from ui.styles import COLOR_BACKGROUND_INPUT

_IMAGE_PATH = os.path.join(os.path.dirname(__file__), "images", "camera_placeholder.png")

_TARGET_ZONE = (0.30, 0.61, 0.53, 0.79)  # the target zone on the eardrum image, as (left, top, right, bottom),
# each from 0 to 1 across the image == it's a rectangle drawn roughly around the green dashed line,
# so it isn't exact near the wedge's corners.

_CROSS_COLOR_OFF_TARGET = QColor(255, 255, 255, 210) # slightly see-through white
_CROSS_COLOR_ON_TARGET = QColor("#5EDA94")  # matches the green 
_WALL_COLOR = (205, 164, 142)               # skin colour
_MARGIN = 10                            # space between round window and widget's edge


def _quad_to_quad(src: QPolygonF, dst: QPolygonF):
    # works out the transformation that stretches one 4-sided shape onto
    # another + different PyQt6 versions expect QTransform.quadToQuad to be called in
    #two different ways, so this tries both.
    result = QTransform()
    try:
        ok = QTransform.quadToQuad(src, dst, result)
        return result if ok else None
    except TypeError:
        out = QTransform.quadToQuad(src, dst)
        if isinstance(out, tuple):
            ok, result = out
            return result if ok else None
        return out


class CameraView(QWidget):
    # sent when the cross moves onto the target (True) or off it (False).
    # main_procedure.py only allows LOCK while it's True.
    onTargetChanged = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(160, 120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._pose = geo.Pose()
        self._drum = self._load_drum_pixmap()

    @staticmethod
    def _load_drum_pixmap() -> QPixmap:
        if not os.path.exists(_IMAGE_PATH):
            return QPixmap()
        pixmap = QPixmap(_IMAGE_PATH)
        # dim it once to the eardrum's lighting level (only where the
        # image has pixels --> the transparent corners stay transparent)
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceAtop)
        painter.fillRect(pixmap.rect(), QColor(0, 0, 0, int((1.0 - geo.drum_brightness()) * 255)))
        painter.end()
        return pixmap

    
    # POSIZIONE DELLA TELECAMERA

    def set_pose(self, tx: float, ty: float, yaw: float, pitch: float) -> None:
        #called by camera_pose_binding.py each time a joystick moves ---> muove la cam (-1 1) e redraws
        was_on_target = self.is_on_target()
        self._pose = geo.Pose(tx, ty, yaw, pitch)
        self.update()
        now_on_target = self.is_on_target() # send it when it actually changes and not 4 every small movement
        if now_on_target != was_on_target:
            self.onTargetChanged.emit(now_on_target)

    def set_crosshair_position(self, x: float, y: float) -> None:
        # just slides camera sideways
        self.set_pose(x, y, self._pose.yaw, self._pose.pitch)

    def is_on_target(self) -> bool:
        uv = geo.aim_uv(self._pose)
        if uv is None:
            return False
        u0, v0, u1, v1 = _TARGET_ZONE
        return u0 <= uv[0] <= u1 and v0 <= uv[1] <= v1

    # DRAWING

    def paintEvent(self, event):
        # Qt calls this every time the view needs to be redrawn
        # ALWAYS FIRS THE ONES IN THE BACK ---> back to front painting style
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(COLOR_BACKGROUND_INPUT))
        # the round view--> as large as it fits in the widget (centered obv)
        diameter = max(20.0, min(self.width(), self.height()) - 2 * _MARGIN)
        radius = diameter / 2.0
        center = QPointF(self.width() / 2.0, self.height() / 2.0)
        #how zoomed in the view is
        focal = radius / geo.HALF_FOV_TAN

        def to_screen(p):# translates the positions given by endoscope_geometry.py into actual pixels
            return QPointF(center.x() + p[0] * focal, center.y() + p[1] * focal)

        #rim of the scope
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(10, 10, 10))
        painter.drawEllipse(center, radius + 4, radius + 4)

        circle = QPainterPath()
        circle.addEllipse(center, radius, radius)
        painter.save()
        painter.setClipPath(circle)
        painter.fillRect(self.rect(), QColor(*_WALL_COLOR))  # wall right at the lens

        # 1) Eardrum (farthest), drawn in perspective.
        corners = geo.drum_corners(self._pose)
        if corners is not None and not self._drum.isNull():
            # The image's own 4 corners...
            src = QPolygonF([QPointF(0, 0), QPointF(self._drum.width(), 0),
                             QPointF(self._drum.width(), self._drum.height()),
                             QPointF(0, self._drum.height())])
            # ...and where they should end up on screen.
            dst = QPolygonF([to_screen(p) for p in corners])
            transform = _quad_to_quad(src, dst)
            if transform is not None:
                painter.save()
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                painter.setTransform(transform, True)
                painter.drawPixmap(0, 0, self._drum)
                painter.restore()

        # 2) Canal walls, far --> near (nearer patches cover farther ones) + smoothing turned off
        # (with smootghing on = thin lines show between the patches)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        for pts, light, _ring in geo.wall_quads(self._pose):
            #wall colour w/light depending on distance
            color = QColor(int(_WALL_COLOR[0] * light), int(_WALL_COLOR[1] * light),
                           int(_WALL_COLOR[2] * light))
            painter.setPen(QPen(color, 1))   # same colour: hides seams
            painter.setBrush(color)
            painter.drawPolygon(QPolygonF([to_screen(p) for p in pts]))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # 3) Vignette at the rim, like a real endoscope.
        vignette = QRadialGradient(center, radius)
        vignette.setColorAt(0.0, QColor(0, 0, 0, 0))
        vignette.setColorAt(0.75, QColor(0, 0, 0, 0))
        vignette.setColorAt(1.0, QColor(0, 0, 0, 160))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(vignette))
        painter.drawEllipse(center, radius, radius)

        # 4) Fixed cross: two diameters line showing inside circle + a small ring at the aim point
        # green on target, white otherwise
        on_target = self.is_on_target()
        color = _CROSS_COLOR_ON_TARGET if on_target else _CROSS_COLOR_OFF_TARGET
        painter.setPen(QPen(color, 2))
        painter.drawLine(QPointF(center.x() - radius, center.y()),
                         QPointF(center.x() + radius, center.y()))
        painter.drawLine(QPointF(center.x(), center.y() - radius),
                         QPointF(center.x(), center.y() + radius))
        painter.setPen(QPen(color, 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, 9, 9)
        painter.restore()

        # outline of the view --> thicker and green when on target
        painter.setPen(QPen(color, 3 if on_target else 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, radius, radius)

        # HUD: status + current pose.
        font = QFont(painter.font())
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(color if on_target else QColor("#BBBBBB"))
        painter.drawText(QRectF(8, 6, 260, 20), Qt.AlignmentFlag.AlignLeft,
                         "ENDOSCOPE  •  ON TARGET" if on_target else "ENDOSCOPE")
        font.setBold(False)
        font.setPointSize(9)
        painter.setFont(font)
        painter.setPen(QColor("#999999"))
        p = self._pose
        painter.drawText(
            QRectF(8, self.height() - 42, 260, 36), Qt.AlignmentFlag.AlignLeft,
            f"shift  x {p.tx * geo.MAX_SHIFT:+.2f}  y {p.ty * geo.MAX_SHIFT:+.2f} R\n"
            f"tilt   yaw {p.yaw * geo.MAX_ANGLE_DEG:+.0f}°  pitch {p.pitch * geo.MAX_ANGLE_DEG:+.0f}°")
