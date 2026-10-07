

from ui.balloon_slider import BalloonSlider
from ui.framework.subject_observer import ObserverMixin
from ui.motion_viewmodel import MotionViewModel


class BalloonPressuresBinding(ObserverMixin):

    def __init__(self, viewmodel: MotionViewModel, balloon_sliders: list[BalloonSlider],
                 robot_view=None):
        super().__init__(viewmodel.manager)
        self._viewmodel = viewmodel
        self._balloon_sliders = balloon_sliders
        self._robot_view = robot_view   # optional: the robot cartoon's balloons
        self.observe(viewmodel)

    def on_invoked(self) -> None:
        for slider, pressure in zip(self._balloon_sliders, self._viewmodel.pressures):
            slider.blockSignals(True)
            slider.set_pressure(pressure)
            slider.blockSignals(False)
        if self._robot_view is not None:
            self._robot_view.set_pressures(self._viewmodel.pressures)
