"""
This turns the joystick input into the simulated endoscope's
camera pose (see ui/camera_view.py and ui/endoscope_geometry.py).

Two groups of joystick-shaped sources (anything with a
positionChanged(float, float) signal):
  - translation_sources move the camera sideways inside the canal;
  - orientation_sources tilt the camera (yaw / pitch).

NB: Each stick is treated as a VELOCITY, meaning the pose keeps moving
while you push and stays exactly where it is when you let go.
"""

from PyQt6.QtCore import QObject, QTimer

_TICK_MS = 30
_TRANSLATION_UNITS_PER_SEC = 0.6   # full -1..1 range in ~3.3 s at full deflection
_ORIENTATION_UNITS_PER_SEC = 0.6


class CameraPoseBinding(QObject):
    def __init__(self, camera_view, translation_sources, orientation_sources, parent=None):
        super().__init__(parent)
        self._camera_view = camera_view
        self._groups = {
            "translation": list(translation_sources),
            "orientation": list(orientation_sources),
        }

        # How far each joystick is currently pushed, as (x, y).
        # The key is (group, id of the joystick), so two joysticks in the
        # same group don't overwrite each other.
        self._vectors = {}

        # Keep track of every connection, so dispose() can undo them.
        self._handlers = []
        for group, sources in self._groups.items():
            for source in sources:
                key = (group, id(source))
                self._vectors[key] = (0.0, 0.0)
                handler = self._make_handler(key)
                self._handlers.append((source, handler))
                source.positionChanged.connect(handler)
        # Current camera pose: sideways position (tx, ty) and tilt
        # (yaw, pitch). Everything starts centred.
        self._tx = self._ty = self._yaw = self._pitch = 0.0

        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self._on_tick)

    def _make_handler(self, key):
        # Each joystick gets its own small function, so we know which one
        # moved.
        def handler(x: float, y: float) -> None:
            self._vectors[key] = (x, y)
            #timer inizia quando qualcosa inizia a muoversi, stop again quando tutto si arresta
            moving = any(vx or vy for vx, vy in self._vectors.values())
            if moving and not self._timer.isActive():
                self._timer.start()
            elif not moving:
                self._timer.stop()
        return handler

    def _sum(self, group):
        vx = sum(v[0] for k, v in self._vectors.items() if k[0] == group)
        vy = sum(v[1] for k, v in self._vectors.items() if k[0] == group)
        return max(-1.0, min(1.0, vx)), max(-1.0, min(1.0, vy))

    def _on_tick(self) -> None:# group every stick in one group and limit result from -1 to 1
        dt = _TICK_MS / 1000.0
        tvx, tvy = self._sum("translation")
        ovx, ovy = self._sum("orientation")
        clamp = lambda v: max(-1.0, min(1.0, v))
        self._tx = clamp(self._tx + tvx * _TRANSLATION_UNITS_PER_SEC * dt)
        self._ty = clamp(self._ty + tvy * _TRANSLATION_UNITS_PER_SEC * dt)
        self._yaw = clamp(self._yaw + ovx * _ORIENTATION_UNITS_PER_SEC * dt)
        self._pitch = clamp(self._pitch + ovy * _ORIENTATION_UNITS_PER_SEC * dt)
        self._camera_view.set_pose(self._tx, self._ty, self._yaw, self._pitch)

    def set_pose(self, tx=0.0, ty=0.0, yaw=0.0, pitch=0.0) -> None:
        # Jump straight to a pose (new round: back to centre, or the game's random start)
        self._tx, self._ty, self._yaw, self._pitch = tx, ty, yaw, pitch
        self._camera_view.set_pose(tx, ty, yaw, pitch)

    def dispose(self) -> None:
        #Stop and detach from every source, called when closed
        self._timer.stop()
        for source, handler in self._handlers:
            try:
                source.positionChanged.disconnect(handler)
            except (TypeError, RuntimeError):
                pass
        self._handlers = []
