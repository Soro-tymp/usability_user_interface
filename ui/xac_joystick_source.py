"""
Reads the physical joystick using pygame, and makes it look like one of
the on-screen joysticks.

The rest of the app doesn't care where a joystick position comes from.
JoystickBinding (ui/joystick_binding.py) only needs an object with a
positionChanged(x, y) signal, with x and y between about -1 and 1. The
mouse joystick and the button pad already work like that

        --> This class does the same thing, but reads real hardware, so it
            plugs into the existing code without changing it. It's connected up in
            main_procedure.py.

NB!!!: Needs the pygame package (it's in requirements.txt).
       + this joystick needs Windows 11. On macOS it shows up as plugged in,
       but its stick and buttons can't be read.

Checking the axis and button numbers (do this once, on the Windows PC):
AXIS_X / AXIS_Y and BUTTON_X1 / BUTTON_X4 below are a first guess.
Run `python joystick_diagnostic.py` with the joystick plugged in. It
shows live which number changes when you move the stick or press a
button.
"""

import os

# Windows: by default pygame only reads the joystick when its own window
# is in front. Here the Qt window is always the one in front, so the stick
# would just read 0 all the time. This tells it to read the joystick
# anyway --> It has to be set before pygame is imported.
# It does absolutely nothing on macOS, però è l'unica cosa che sono riuscito
# a fare quando ci ho lavorato sui computer del lab per testarlo 
os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")

import time

import pygame
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

# SETTINGS AND CONSTANT TO ADJUST ON THE REAL HARDWARE
# Which axis numbers are left/right and up/down on the stick.
AXIS_X = 0
AXIS_Y = 1

# Set to True if a direction feels backwards (e.g. pushing up moves down).
AXIS_INVERT_X = False
AXIS_INVERT_Y = False

# The number pygame gives to the X1 and X4 buttons. First guess:
# check them with joystick_diagnostic.py and put here the "btnN" number
# that lights up when you press each one.
BUTTON_X1 = 0  # selects TRANSLATION
BUTTON_X4 = 3  # selects ROTATION

# A real stick never rests exactly at (0, 0) ---> worth creating a threshold for deadzone
# to clear unwanted hardware noise 
# Abything in the range is counted as centre
DEADZONE = 0.15

# How often to check the stick (in ms)
POLL_MS = 30

# On macOS, Xbox controllers sometimes take a moment to show up after the
# app starts, so instead of checking only once, keep trying for up to
# 2 seconds.
_CONNECT_RETRY_SECONDS = 2.0
_CONNECT_RETRY_INTERVAL = 0.1


class XacJoystickSource(QObject):
    #Checks the physical stick every POLL_MS and sends its position
    #with the positionChanged(x, y) signal as the on-screen joysticks.
    # If no joystick is found, it just stays quiet and the rest of the app
    # works normally with the on-screen controls

    positionChanged = pyqtSignal(float, float)

    # Sent once when a button is pressed (not when it's released), with
    # the button's number
    buttonPressed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        pygame.init()

        # On macOS, pygame may not update controllers unless it has a
        # window of its own ---> We don't want to see it, so it's 1x1 pixel
        # and hidden
        pygame.display.init()
        pygame.display.set_mode((1, 1), pygame.HIDDEN)
        pygame.joystick.init()

        self._joystick = self._connect_with_retry()
        if self._joystick is None:
            print("[XacJoystickSource] No physical joystick detected — "
                  "steering from the Xbox Adaptive Joystick is disabled. "
                  "(On-screen joysticks still work normally.)")
        else:
            print(f"[XacJoystickSource] Connected: {self._joystick.get_name()}")

        self._last_emitted = (0.0, 0.0)
        # Which buttons were down on the previous check, to spot new presses.
        self._last_buttons: list[bool] = []

        # Start checking the stick regularly.
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    @staticmethod
    def _connect_with_retry():
        # Look for a joystick every 0.1 s for up to 2 s.
        # pygame only notices new devices when it restarts its joystick
        # module, hence the quit()/init() each time.
        deadline = time.monotonic() + _CONNECT_RETRY_SECONDS
        while time.monotonic() < deadline:
            pygame.joystick.quit()
            pygame.joystick.init()
            if pygame.joystick.get_count() > 0:
                # Use the first joystick found.
                joystick = pygame.joystick.Joystick(0)
                joystick.init()
                return joystick
            time.sleep(_CONNECT_RETRY_INTERVAL)
        return None

    def _poll(self) -> None:
        if self._joystick is None:
            return
        pygame.event.pump()
        try:
            x = self._joystick.get_axis(AXIS_X)
            y = self._joystick.get_axis(AXIS_Y)
            buttons = [bool(self._joystick.get_button(i))
                       for i in range(self._joystick.get_numbuttons())]
        except pygame.error:
            # Unplugged while the app was running: stop reading it
            # instead of crashing.
            print("[XacJoystickSource] Joystick disconnected.")
            self._joystick = None
            return

        if AXIS_INVERT_X:
            x = -x
        if AXIS_INVERT_Y:
            y = -y
        if abs(x) < DEADZONE and abs(y) < DEADZONE:
            x, y = 0.0, 0.0

        # Buttons: only react at the moment a button goes down, so holding
        # it doesn't keep selecting the mode over and over.
        for i, down in enumerate(buttons):
            was_down = self._last_buttons[i] if i < len(self._last_buttons) else False
            if down and not was_down:
                self.buttonPressed.emit(i)
        self._last_buttons = buttons

        # Only send the position if it changed since last time.
        if (x, y) != self._last_emitted:
            self._last_emitted = (x, y)
            self.positionChanged.emit(x, y)

    def dispose(self) -> None:
        #Stops checking the joystick and lets go of it ---> called when the
        #window closes
        self._timer.stop()
        if self._joystick is not None:
            self._joystick.quit()
            self._joystick = None
        pygame.joystick.quit()
