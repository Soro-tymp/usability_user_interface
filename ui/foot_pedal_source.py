"""
Reads the USB foot pedal (Accuratus X1P) and
re-emits it as two plain Qt signals: pressed() and released().

The pedal behaves like a keyboard that sends the letter "b" to the
operating system --> pedal pressed down = "b"

Because of that, pressing and holding the "b" key on the keyboard
simulates the pedal --> useful for testing because REMEMBER: the
controller does not work on any other thing except from an actual
Xbox and a windows (actually i think on the box it even stated windows11,
so maybe also older versions are not compatible with it tbf).

Pynput package is needed (see requirements.txt)

This class onlu tells if the pedal is held down or not, what the press
actually translates into is depending on the step of the procedure the
user will be in at the moment, so it's smt decided in main_procedure.

DISCLAIMER: Idk if it's the same for windows, but if you're workin on
macOS, make sure to grant permission (first time only), since pynput
needs Accessibility + Input Monitoring permission granted to
whatever runs this app (Terminal, or your code editor's terminal).
"""

from pynput import keyboard
from PyQt6.QtCore import QObject, pyqtSignal

PEDAL_KEY = 'b'


class FootPedalSource(QObject):
    # Sends pressed() when the pedal goes down and released() when it
    # comes back up. Operating-system key auto-repeat (i.e. held down = b b b b b...)
    # is filtered out, so pressed() fires once per press."""

    pressed = pyqtSignal()
    released = pyqtSignal()

    # These two are only used inside this file.
    # pynput listens to the keyboard on its own separate thread, not the
    # main one where the window runs. Qt only allows timers and widgets to
    # be touched from the main thread, so the pynput functions below don't
    # do anything themselves. They just send one of these signals, and
    # Qt hands it over to the main thread, where _handle_down and
    # _handle_up can safely do the work.
    # (this fixed the " Timers cannot be started from another thread" error.)
    # (explained better on slide here not too clear tbh sorry bout that)
    _pedal_down = pyqtSignal()
    _pedal_up = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._held = False # pedal down rn?
        self._listener = None #pynput keyboard listener

        self._pedal_down.connect(self._handle_down)
        self._pedal_up.connect(self._handle_up)

        # Start listening to the keyboard. If it fails (usually missing
        # permissions on macOS), print why but let the app keep running:
        # the on-screen controls still work without the pedal.
        try:
            self._listener = keyboard.Listener(
                on_press=self._on_press, on_release=self._on_release)
            self._listener.start()
            print("[FootPedalSource] Listening for the pedal (sends 'b').")
        except Exception as exc:  # pynput raises OS-specific errors here
            print(f"[FootPedalSource] Could not start listening for the "
                  f"pedal ({exc}). On macOS, check Accessibility / Input "
                  f"Monitoring permissions for this terminal.")

    @property
    def is_held(self) -> bool:
        return self._held

    @staticmethod
    def _matches(key) -> bool: # check key + avoid crashing for special keys like shift that have no .char
        return getattr(key, 'char', None) == PEDAL_KEY

    def _on_press(self, key) -> None:
        # pynput background thread — emit only.
        if self._matches(key):
            self._pedal_down.emit()

    def _on_release(self, key) -> None:
        if self._matches(key):
            self._pedal_up.emit()

    def _handle_down(self) -> None:
        # Main thread, if pedal down already --> ignore the key that's just being repeated
        if not self._held:
            self._held = True
            self.pressed.emit()

    def _handle_up(self) -> None:
        if self._held:
            self._held = False
            self.released.emit()

    def dispose(self) -> None:
        #Stop listening. Called when closing
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
