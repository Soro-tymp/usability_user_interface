"""
It keeps the maths that turns a joystick movement into pressures for
the 6 balloons, measured from a resting centre pressure. Everything
that talks to the real hardware has been removed, so it runs on any
computer without the robot plugged in.

Two methods were added for the pedal-driven procedure: set_neutral_level
and set_pressures.

"""

import math
from typing import List

from ui.framework.subject_observer import SubjectMixin
from ui.framework.update_manager import UpdateManager

NUM_CHANNELS = 6
MIN_PRESSURE = 0.0
MAX_PRESSURE = 1.0

# weights (x, y) per ognuno dei 6 balloon, usati per la orientation:
# dicono quanto ogni balloon reagisce al joystick quando si ruota.
# Vengono dalle righe di orientation della H matrix 4x6 del
# MotionController reale (la translation invece non li usa, è gestita
# da kinematics_from_drag più sotto). Sono scalati in modo che con lo
# stick tutto spinto il balloon si sposti del suo offset massimo dal centre.
# I numeri sono cos/sin di 0°, 120° e 240°, ripetuti due volte:
# i balloon 0-1-2 e 3-4-5 hanno gli stessi weights
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

    def set_neutral_level(self, level: float | None) -> None:
        """Move the neutral point the joysticks steer around.
        Translation/orientation are computed as offsets from `centers`.
        That would be the midpoint (0.5), so as soon as you touch a
        joystick after inflating, every balloon would jump from the
        inflation level back toward 0.5. Once the balloons have reached
        the stability threshold (see main_procedure.py) the
        neutral point is set to 0.7 instead (arbitrary), sois compensated
        around the stable state. None restores the default midpoints."""
        if level is None:
            self.centers = [(mn + mx) / 2.0 for mn, mx in zip(self.mins, self.maxs)]
        else:
            self.centers = [max(mn, min(mx, level)) for mn, mx in zip(self.mins, self.maxs)]

    def set_pressures(self, pressures: List[float]) -> None:
        """Set each channel individually --> Used for the final
        deflation ramp, so every balloon goes down from its OWN current
        value instead of all jumping to one shared level first."""
        self._apply_pressures(list(pressures))

    def reset_state_to_centers(self) -> None:
        self._apply_pressures(self.centers.copy())

    def set_inflation_level(self, level: float) -> List[float]:
        """Set every channel to the same pressure level a + here mins/maxs are
        uniform (0..1) across all 6 channels, so a flat level is enough."""
        level = max(self.mins[0], min(self.maxs[0], level))
        self._apply_pressures([level] * self.NUM_CHANNELS)
        return self.current_pressures.copy()

    def kinematics_from_drag(self, dx: float, dy: float) -> List[float]:
        """ Calcola le 6 pressioni dei balloon a partire da un movimento del
joystick, partendo dalla pressione di riposo (centre) di ognuno. Le
calcola soltanto, non le applica. I balloon sono distribuiti in cerchio
(uno ogni 60°), quindi spingendo lo stick verso un balloon quello si
gonfia e quello opposto si sgonfia."""
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
        invece della geometria a cerchio usata per la translation,
        usa i weights fissi di _ORIENTATION_WEIGHTS (uno per balloon).
        A differenza della translation qui l'effetto è lineare: metà
        spinta = metà effetto"""
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
        # tutte le modifiche alle pressioni passano da qui --> ogni valore
        # viene tenuto dentro i limiti (min/max), poi salvato
        self.current_pressures = [
            max(self.mins[i], min(self.maxs[i], pressures[i]))
            for i in range(self.NUM_CHANNELS)
        ]
        self.notify() # update gauges on the screen
