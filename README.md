# Joystick + Buttons + Balloons demo

A small desktop app showing two on-screen joysticks and a directional
button pad that live-drive 6 "balloon" pressure gauges, laid out like the
real clinician app (left panel, center camera view, right panel, bottom
procedure-stage bar). No hardware needed — runs entirely on your computer.

## Install

Requires Python 3.10+.

```
pip install -r requirements.txt
```

## Run

```
python main_procedure.py
```

Press `Esc` or close the window to quit.

## What to expect

- **Left panel:** Control and Back buttons.
- **Center:** a static camera placeholder image, and a Control panel
  (opened via the left panel's Control button) with 2 joysticks
  (Translation, Rotation), the 6 balloon gauges, and a Reset to center
  button.
- **Right panel:** the current step's instructions, a directional button
  pad (only during the "Align" step), and a Confirm button.
- **Bottom bar:** the 4 mock procedure steps — Insert → Inflate → Align →
  Complete.

Click Confirm (or press Enter) to move forward through the steps, Back to
go back. Confirming Inflate fills the balloon gauges; confirming the last
step ("Finish") empties them again — and it's fully reversible in both
directions. The joysticks and button pad work at any step once the
Control panel is open.
