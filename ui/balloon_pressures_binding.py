"""
balloon_pressures_binding.py — BalloonPressuresBinding: pushes
MotionViewModel.pressures into a row of BalloonSlider widgets.

The mirror image of JoystickBinding: where JoystickBinding forwards
View -> ViewModel (user input driving the model), this binding forwards
ViewModel -> View (model state driving the display). It does that by
observing the viewmodel through the UpdateManager and reacting in
on_invoked — the framework's phase-2 slot for side-effecting widget
updates (see ObserverMixin / UpdateManager docstrings).
"""

from ui.balloon_slider import BalloonSlider
from ui.framework.subject_observer import ObserverMixin
from ui.motion_viewmodel import MotionViewModel


class BalloonPressuresBinding(ObserverMixin):

    def __init__(self, viewmodel: MotionViewModel, balloon_sliders: list[BalloonSlider]):
        super().__init__(viewmodel.manager)
        self._viewmodel = viewmodel
        self._balloon_sliders = balloon_sliders
        self.observe(viewmodel)

    def on_invoked(self) -> None:
        for slider, pressure in zip(self._balloon_sliders, self._viewmodel.pressures):
            slider.blockSignals(True)
            slider.set_pressure(pressure)
            slider.blockSignals(False)
