"""
A safety measure working as a timer used for the pedal actions
that should never happen by accident (e.g. LOCK and DEFLATE).
A quick tap on the pedal does nothing, the action only happens if
you keep it down for the whole time
    ---> UPDATE Fri02/10/2026: Lukas introduced idea of voice control
         for further safety measure (idk if try to implement it, idk if
         i still have time, maybe ask to work together even once got back
         to Italy)

How it works:
  - start() starts counting
  - progressChanged(0..1) is sent while counting, so the screen can
    show a progress bar
  - completed() is sent once the full time has passed
  - cancel() stops and resets it, for example when the pedal is
    released early ---> Letting go early never does half the action
"""

import time

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

# How often the progress is updated (in ms).
_TICK_MS = 30


class HoldToConfirm(QObject):
    progressChanged = pyqtSignal(float)  # 0.0 = just started vs. 1.0 = done
    completed = pyqtSignal()             # held for entire full time
    cancelled = pyqtSignal()             # stopped before the end

    def __init__(self, duration_s: float, parent=None):
        super().__init__(parent)
        self._duration = duration_s   # how long it has to be held in secs

        # When counting started, or None when it's not counting.
        self._started_at = None

        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self._on_tick)

    @property
    def is_running(self) -> bool:
        # True while counting.
        return self._started_at is not None

    def start(self) -> None:
        # Start counting from zero
        self._started_at = time.monotonic()
        self.progressChanged.emit(0.0)
        self._timer.start()

    def cancel(self) -> None:
        # Nothing to cancel if it isn't counting = cancelled()
        # sent when something was actually stopped only.
        if self._started_at is None:
            return
        self._timer.stop()
        self._started_at = None
        self.cancelled.emit()

    def _on_tick(self) -> None:
        # Safety check
        if self._started_at is None:
            self._timer.stop()
            return

        # Work out the progress from the real time che è trascorso e non
        # from the number of ticks --> cosi rimane accurate anche se alcuni
        # ticks arrivano in ritardo + time.monotonic() va sempre e solo in
        # avanti, so changing the computer's clock can't affect it.
        fraction = min(1.0, (time.monotonic() - self._started_at) / self._duration)
        self.progressChanged.emit(fraction)

        if fraction >= 1.0:
            # Held for long enough: stop, reset, and confirm.
            self._timer.stop()
            self._started_at = None
            self.completed.emit()


            
