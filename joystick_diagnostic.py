"""
DISCLAIMER: I didn't write this script myself, it was actually
written by AI so I could understand how the computer read the buttons
and the stick on the Xbox Joystick. It's a helper tool for learning
and testing, and it isn't part of the procedure app itself so it never
uses it.

What it does is just to show the number the computer assigns to each button
(btn0, btn1, ...) and the value of each stick axis as it is moved. I used
it to check that BUTTON_X1, BUTTON_X4, AXIS_X and AXIS_Y in
ui/xac_joystick_source.py actually matched the real joystick.
"""

import os

os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")

import time

import pygame

POLL_SECONDS = 0.1


def main():
    pygame.init()
    pygame.display.init()
    pygame.display.set_mode((1, 1), pygame.HIDDEN)
    pygame.joystick.init()

    print("Waiting for a joystick... (plug it in now if you haven't)")
    joystick = None
    while joystick is None:
        pygame.joystick.quit()
        pygame.joystick.init()
        if pygame.joystick.get_count() > 0:
            joystick = pygame.joystick.Joystick(0)
            joystick.init()
        else:
            time.sleep(POLL_SECONDS)

    print(f"Connected: {joystick.get_name()}")
    print(f"  axes: {joystick.get_numaxes()}   buttons: {joystick.get_numbuttons()}")
    print("Move the stick and press buttons. Ctrl+C to stop.\n")

    try:
        while True:
            pygame.event.pump()
            axes = [round(joystick.get_axis(i), 2) for i in range(joystick.get_numaxes())]
            buttons = [joystick.get_button(i) for i in range(joystick.get_numbuttons())]
            axes_str = "  ".join(f"axis{i}={v:+.2f}" for i, v in enumerate(axes))
            buttons_str = "  ".join(f"btn{i}={'X' if b else '.'}" for i, b in enumerate(buttons))
            print(f"\r{axes_str}    {buttons_str}   ", end="", flush=True)
            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
