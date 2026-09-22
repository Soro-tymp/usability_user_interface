from PyQt6.QtCore import QTimer

from ui.motion_viewmodel import MotionViewModel


class JoystickBinding:
    """Connects any joystick-shaped widget to a MotionViewModel.

    A "joystick" here is anything exposing a Qt signal
    ``positionChanged(float x, float y)`` with x/y normalized to roughly
    -1..1 and (0, 0) meaning "centered/released" — Joystick and
    ButtonJoystick both satisfy this, and so will any future joystick-shaped
    source (a physical USB joystick reader, say) without this binding
    changing at all.

    This is the View -> ViewModel direction. A joystick only ever drives the
    model on user input, so it doesn't observe anything — it just forwards
    positionChanged into the viewmodel action selected by ``mode``.

    positionChanged only fires when the raw input changes — a single event
    on ButtonJoystick press, a sparse stream while dragging an analog
    Joystick — so applying it directly would snap the commanded position
    straight to its target every time. Instead this binding treats each
    positionChanged as a new *target* and eases the driven (x, y) vector
    toward it on a fixed tick, so a press-and-hold (or a drag) reads as
    smooth continuous motion instead of discrete jumps.

    Deliberately not spring-loaded: (0, 0) — the joystick-released
    convention every joystick-shaped view emits — stops the ramp right
    where it is instead of easing back to center. The next positionChanged
    (a new press, or a new drag position) is what moves it from there.
    """

    _ACTIONS = {
        "translation": "apply_translation_from_drag",
        "orientation": "apply_orientation_from_drag",
    }

    _TICK_MS = 30       # ~33 Hz ramp rate
    _SMOOTHING = 0.2    # default fraction of the remaining distance covered per tick
    _EPSILON = 0.01      # snap-to-target / centered threshold

    def __init__(self, viewmodel: MotionViewModel, joystick, mode: str = "translation",
                 smoothing: float | None = None):
        """
        smoothing: fraction of the remaining distance closed per tick — lower
            is less sensitive (takes longer, and a quick tap moves less far,
            before reaching the target) before reaching the target/limits.
            Defaults to _SMOOTHING; override per-instance for a source that
            should feel gentler than the rest, e.g. a press-only pad like
            ButtonJoystick where a single press always commands full
            magnitude, so the ramp rate is the only thing standing between
            "press" and "at the limit."
        """
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

        # Snap once within epsilon so the asymptotic ease-in never leaves
        # the target approached-but-never-quite-reached.
        arrived = abs(nx - tx) < self._EPSILON and abs(ny - ty) < self._EPSILON
        if arrived:
            nx, ny = tx, ty
        self._current = (nx, ny)
        self._apply(nx, ny)

        if arrived:
            self._timer.stop()

    def dispose(self) -> None:
        """Detach from the joystick's signal and stop ramping. Idempotent."""
        self._timer.stop()
        try:
            self._joystick.positionChanged.disconnect(self._on_position_changed)
        except (TypeError, RuntimeError):
            pass
