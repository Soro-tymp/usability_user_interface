"""
motion_viewmodel.py — MotionViewModel: the ViewModel between the joystick
Views and the MotionController Model.

Mirrors the real app's ui/viewmodels/motion_controller.py
(MotionControllerViewModel): observes the MotionController for pressure
changes (on_notified) and exposes the two drive actions that
JoystickBinding calls on user input.
"""

from ui.framework.subject_observer import SubjectObserverMixin
from ui.motion_controller import MotionController


class MotionViewModel(SubjectObserverMixin):
    """Holds the latest motion-controller pressures and exposes the motion
    actions that drive the Model — joystick-shaped views (Joystick,
    ButtonJoystick) call these instead of reaching into MotionController
    directly."""

    def __init__(self, motion_controller: MotionController):
        super().__init__(motion_controller.manager)
        self._motion_controller = motion_controller
        self._pressures = motion_controller.get_absolute_pressures()
        self.observe(motion_controller)

    @property
    def pressures(self):
        return self._pressures

    def on_notified(self, sources):
        pressures = self._motion_controller.get_absolute_pressures()
        if pressures != self._pressures:
            self._pressures = pressures
            return True, None
        return False, None

    # ------------------------------------------------------------------
    # Actions — called by joystick-style views on user input.
    # ------------------------------------------------------------------

    def apply_translation_from_drag(self, dx: float, dy: float) -> None:
        """Drive lateral translation from a normalized drag/joystick vector."""
        self._motion_controller.apply_translation_from_drag(dx, dy)

    def apply_orientation_from_drag(self, dx: float, dy: float) -> None:
        """Drive tip orientation from a normalized drag/joystick vector."""
        self._motion_controller.apply_orientation_from_drag(dx, dy)

    def reset_to_center(self) -> None:
        """Return all actuators to their neutral center pressures."""
        self._motion_controller.reset_state_to_centers()

    def inflate(self, level: float = 0.85) -> None:
        """Set all 6 channels to the same, higher-than-center pressure —
        called on confirming the "Inflate" step (see STEPS in
        main_procedure.py), mirroring the real ProcedurePage's own
        on_confirm hook for its inflate step
        (PressureManager.reset_pressures_to_midpoint)."""
        self._motion_controller.set_inflation_level(level)

    def deflate(self) -> None:
        """Set all 6 channels back down to 0 — called on confirming the
        final "Complete"/Finish step, mirroring the real ProcedurePage's
        Remove step (PressureManager.ramp_to_pressures([0.0] * NUM_CHANNELS)),
        just as an instant drop rather than a ramp."""
        self._motion_controller.set_inflation_level(0.0)
