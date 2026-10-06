"""
The ViewModel between the joystick Views and the MotionController Model

Mirrors the real app's ui/viewmodels/motion_controller.py
(MotionControllerViewModel): observes the MotionController for pressure
changes (on_notified) and exposes the two drive actions that
JoystickBinding calls on user input.
"""

from ui.framework.subject_observer import SubjectObserverMixin
from ui.motion_controller import MotionController


class MotionViewModel(SubjectObserverMixin):
    """Holds the latest motion-controller pressures and exposes the motion
    actions that drive the Model, joystick-shaped views (Joystick,
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

    # Actions called by joystick-style views on user input.

    def apply_translation_from_drag(self, dx: float, dy: float) -> None:
        #drive lateral translation from a normalized drag/joystick vector
        self._motion_controller.apply_translation_from_drag(dx, dy)

    def apply_orientation_from_drag(self, dx: float, dy: float) -> None:
        #drive tip orientation from a normalized drag/joystick vector
        self._motion_controller.apply_orientation_from_drag(dx, dy)

    def reset_to_center(self) -> None:
        #return all actuators to their neutral center pressures
        self._motion_controller.reset_state_to_centers()

#added for pedal-driven proc.
    def set_neutral_level(self, level: float | None) -> None:
       # Once the balloons are inflated, main_procedure.py sets this to the
       # inflation level, so steering moves the pressures around the
       # inflated state instead of the original centre.
       # None goes back to the normal centre.
        self._motion_controller.set_neutral_level(level)

    def set_pressures(self, pressures) -> None:
        # sets all 6 p directly ---> used for gradual deflation
        self._motion_controller.set_pressures(pressures)

    def inflate(self, level: float = 0.85) -> None:
        self._motion_controller.set_inflation_level(level)

    def deflate(self) -> None:#set all 6 channels back down to 0
        self._motion_controller.set_inflation_level(0.0)
