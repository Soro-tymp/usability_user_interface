"""
The physical joystick has only one stick, but in the Align step it has
two jobs:
- translation
- rotation(orientation in the code)
----> maybe will be merged in future idk

This class sends the stick's movement down one track or the other, depending
on the mode that's selected: on the joystick, X1 picks translation and X4
picks rotation (the buttons are handled in main_procedure.py)

It has two outputs, `translation` and `orientation`. Each one has the
same positionChanged(x, y) signal as an on-screen joystick, so the rest
of the app can use them exactly like normal joysticks, without changing
any of the existing code.
"""

from PyQt6.QtCore import QObject, pyqtSignal

MODE_TRANSLATION = "translation"
MODE_ORIENTATION = "orientation"


class _Output(QObject):
    positionChanged = pyqtSignal(float, float)


class JoystickModeRouter(QObject):
    modeChanged = pyqtSignal(str)

    def __init__(self, source, initial_mode: str = MODE_TRANSLATION, parent=None):
        super().__init__(parent)

        # The two output + dictionary to find the right one from
        # the mode name
        self.translation = _Output(self)
        self.orientation = _Output(self)
        self._outputs = {MODE_TRANSLATION: self.translation,
                         MODE_ORIENTATION: self.orientation}
        self._mode = initial_mode

        # Off to begin with ---> main_procedure.py switches it on only during
        # the alignment when devise is not locked
        self._enabled = False
        self._source = source #physical stick
        source.positionChanged.connect(self._on_source_position)

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_mode(self, mode: str) -> None:
        if mode not in self._outputs or mode == self._mode:
            return
        self._outputs[self._mode].positionChanged.emit(0.0, 0.0)
        self._mode = mode
        self.modeChanged.emit(mode)

    def set_enabled(self, enabled: bool) -> None:
        if self._enabled and not enabled:
            self._outputs[self._mode].positionChanged.emit(0.0, 0.0)
        self._enabled = enabled

    def _on_source_position(self, x: float, y: float) -> None:
        if self._enabled:
            self._outputs[self._mode].positionChanged.emit(x, y)

    def dispose(self) -> None:
        try:
            self._source.positionChanged.disconnect(self._on_source_position)
        except (TypeError, RuntimeError):
            pass
