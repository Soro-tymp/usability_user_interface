"""
motion_controller.py — Minimal motion/kinematics model.

Trimmed down from the main app's controllers/motion_controller.py: keeps
the kinematics math that maps a joystick drag vector to 6 per-channel
balloon pressures around a neutral center, and drops everything that talks
to real hardware (DeviceController, serial commands) — nothing here needs
a physical device to run. The math itself (kinematics_from_drag, the
orientation mapping) is copied unmodified in spirit from the real
MotionController, just without the numpy dependency.
"""

import math
from typing import List

from ui.framework.subject_observer import SubjectMixin
from ui.framework.update_manager import UpdateManager

NUM_CHANNELS = 6
MIN_PRESSURE = 0.0
MAX_PRESSURE = 1.0

# Per-channel (x, y) weights for mapping a drag vector to orientation
# pressures — equivalent to the real MotionController's 4x6 H matrix
# reduced to just its orientation rows (translation is handled instead by
# kinematics_from_drag below), normalized so a unit drag maps to a unit
# offset from center.
_ORIENTATION_WEIGHTS = [
    (1.0, 0.0),
    (-0.5, 0.866025403784439),
    (-0.5, -0.866025403784439),
    (1.0, 0.0),
    (-0.5, 0.866025403784439),
    (-0.5, -0.866025403784439),
]


class MotionController(SubjectMixin):
    """Maps drag vectors to 6-channel balloon pressures around a center.

    Maintains current_pressures and calls notify() whenever they change,
    so anything observing this controller (e.g. MotionViewModel) picks up
    the new values through the UpdateManager.
    """

    def __init__(self, update_manager: UpdateManager):
        super().__init__(update_manager)
        self.NUM_CHANNELS = NUM_CHANNELS
        self.mins: List[float] = [MIN_PRESSURE] * NUM_CHANNELS
        self.maxs: List[float] = [MAX_PRESSURE] * NUM_CHANNELS
        self.centers: List[float] = [(mn + mx) / 2.0 for mn, mx in zip(self.mins, self.maxs)]
        self.ranges: List[float] = [max(1e-6, mx - mn) for mn, mx in zip(self.mins, self.maxs)]
        # Starts deflated (every channel at its minimum), not centered —
        # the robot has no reason to be inflated before it's even been
        # inserted. The "Inflate" step (see STEPS in main_procedure.py) is
        # what first brings it up to a working pressure.
        self.current_pressures: List[float] = self.mins.copy()

    def get_absolute_pressures(self) -> List[float]:
        return self.current_pressures.copy()

    def reset_state_to_centers(self) -> None:
        self._apply_pressures(self.centers.copy())

    def set_inflation_level(self, level: float) -> List[float]:
        """Set every channel to the same pressure level (clamped to
        [min, max]) — a simplified stand-in for the real MotionController's
        set_inflation_level/set_inflation_percentage, which vary the target
        per-channel from real slider-configured limits. Here mins/maxs are
        uniform (0..1) across all 6 channels, so a flat level is enough."""
        level = max(self.mins[0], min(self.maxs[0], level))
        self._apply_pressures([level] * self.NUM_CHANNELS)
        return self.current_pressures.copy()

    def kinematics_from_drag(self, dx: float, dy: float) -> List[float]:
        """Pure-mapping: absolute pressures from a drag vector, centered
        about each actuator's neutral pressure. Channels are arranged
        evenly around a circle (60 degrees apart for 6 channels), so a
        drag toward a channel's direction raises that channel's pressure
        and lowers the opposite one's."""
        mag = math.hypot(dx, dy)
        out = []
        for i in range(self.NUM_CHANNELS):
            theta_i = math.radians(i * (360.0 / self.NUM_CHANNELS))
            proj = dx * math.cos(theta_i) + dy * math.sin(theta_i)
            offset = proj * mag * (self.ranges[i] / 2.0)
            v = self.centers[i] + offset
            v = max(self.mins[i], min(self.maxs[i], v))
            out.append(v)
        return out

    def apply_translation_from_drag(self, dx: float, dy: float) -> List[float]:
        """Drive lateral translation from a normalized drag/joystick vector."""
        self._apply_pressures(self.kinematics_from_drag(dx, dy))
        return self.current_pressures.copy()

    def apply_orientation_from_drag(self, dx: float, dy: float) -> List[float]:
        """Drive tip orientation from a normalized drag/joystick vector,
        using a fixed set of per-channel weights instead of translation's
        radial geometry."""
        out = []
        for i in range(self.NUM_CHANNELS):
            wx, wy = _ORIENTATION_WEIGHTS[i]
            offset = (wx * dx + wy * dy) * (self.ranges[i] / 2.0)
            v = self.centers[i] + offset
            v = max(self.mins[i], min(self.maxs[i], v))
            out.append(v)
        self._apply_pressures(out)
        return self.current_pressures.copy()

    def _apply_pressures(self, pressures: List[float]) -> None:
        self.current_pressures = [
            max(self.mins[i], min(self.maxs[i], pressures[i]))
            for i in range(self.NUM_CHANNELS)
        ]
        self.notify()
