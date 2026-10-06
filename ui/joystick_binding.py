from PyQt6.QtCore import QTimer

from ui.motion_viewmodel import MotionViewModel


class JoystickBinding:
    """Connects any joystick-shaped widget to a MotionViewModel.

    A "joystick" here is anything exposing a Qt signal
    ``positionChanged(float x, float y)`` with x/y normalized to roughly
    -1..1 and (0, 0) meaning "centered/released"--->Joystick and
    ButtonJoystick both satisfy this, and so will any future joystick-shaped
    source without this binding changing at all
    """

    _ACTIONS = {
        "translation": "apply_translation_from_drag",
        "orientation": "apply_orientation_from_drag",
    }

    _TICK_MS = 30 # ogni 30 ms fa un passo verso il target (~33 volte al secondo)
    _SMOOTHING = 0.2 # a ogni tick copre il 20% della distanza che manca al target
    _EPSILON = 0.01 # sotto questa soglia: arrivato al target / joystick al centre

    def __init__(self, viewmodel: MotionViewModel, joystick, mode: str = "translation",
                 smoothing: float | None = None):
        if mode not in self._ACTIONS:
            raise ValueError(f"mode must be one of {list(self._ACTIONS)}, got {mode!r}")

        self._viewmodel = viewmodel
        self._joystick = joystick
        self._apply = getattr(viewmodel, self._ACTIONS[mode])
        self._smoothing = self._SMOOTHING if smoothing is None else smoothing

        self._target = (0.0, 0.0)
        self._current = (0.0, 0.0)

        self._timer = QTimer()
        self._timer.setInterval(self._TICK_MS)
        self._timer.timeout.connect(self._on_tick)

        joystick.positionChanged.connect(self._on_position_changed)

    def _on_position_changed(self, x: float, y: float) -> None:
        self._target = (x, y)
        if abs(x) < self._EPSILON and abs(y) < self._EPSILON:
            # Released — hold the current position; don't spring back to center.
            self._timer.stop()
            return
        if not self._timer.isActive():
            self._timer.start()

    def _on_tick(self) -> None:
        tx, ty = self._target
        cx, cy = self._current
        nx = cx + (tx - cx) * self._smoothing
        ny = cy + (ty - cy) * self._smoothing
        arrived = abs(nx - tx) < self._EPSILON and abs(ny - ty) < self._EPSILON
        if arrived:
            nx, ny = tx, ty
        self._current = (nx, ny)
        self._apply(nx, ny)

        if arrived:
            self._timer.stop()

    def dispose(self) -> None:
        self._timer.stop()
        try:
            self._joystick.positionChanged.disconnect(self._on_position_changed)
        except (TypeError, RuntimeError):
            pass
