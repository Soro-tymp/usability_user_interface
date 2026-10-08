# What is all of this???

This is a small desktop demo of the clinician interface while using the
ear robot. It has two on-screen joysticks and a directional button pad, 
(during the alignment phase) and moving them drives directly the six 
balloon pressure gauges in real time. The layout presents a panel on the 
left, the camera view in the middle, a panel on the right and the procedure 
steps along the bottom.

Actually no hardware is necessarily needed, everything can run on computer
and every action can be performed and tested even without the pedal and the
XAC (Xbox Adaptive Control joystick).

## To install the demo (everything in here is making reference to MacOs,
## for Windows systems the start could differ a bit)

Python 3.10 or newer is needed. Then:

```
pip install -r requirements.txt
```

## To run the demo make sure to use the following file:

```
python main_procedure.py
```

To quit, press `Esc` or just close the window.

## The screen presentation 

On the left there are two buttons, Control and Back. The first must be 
used in the very first step, while "Back" can be used if there's the 
need of returning back to the previous step.

In the middle there's a placeholder camera image (would be useful to 
substitute it with the one of an actual ear, may be reconstructed from
CT scans). 

The control panel has the two joysticks, which are "Translation" and
"Rotation" (future maybe to be combined into a single one), the 6 
balloon gauges and a button to reset everything to the center.

On the right the instructions for the current step can be found, the
Confirm button and, during the Align step only, the directional pad.

Along the bottom are the four steps of the mock procedure: Insert,
Inflate, Align and Complete (so that user doesn't loose track of 
the step of the procedure they are performing).

## Breaking down the procedure: the essentials

The procedure is driven by the foot pedal and the Xbox Adaptive Joystick,
but to test is is sufficient to have a computer.

**1. Insert.** Click Confirm or press Enter.

**2. Inflate.** Hold the pedal down to inflate all the balloons (if you let
go, inflation pauses). When the balloons reach the stability threshold (0.7,
needs to be fixed), inflation stops and the screen shows "Ready to proceed 
to the next step" with a 5-second countdown. After that the app moves on to
Align by itself. The threshold is `INFLATION_THRESHOLD` in `main_procedure.py`. 
I set it to 0.70 for now, it's just a placeholder. If you do not have a pedal
to test it just press "b" on the keyboard (it works as the pedal).

**3. Align.** Press X1 for translation or X4 for rotation (here I am not sure
of the buttons, is for sure two of the four displayed in a cross fashion, but
it could be that they were differing between mac and windows... anyhow, it 
should be pretty easy to change what is written on the screen relative to 
them. Apart from that in the folder there's a file useful to understand which
button does what. I explain it better below), then move the stick. The middle 
of the screen shows a simulated 3D endoscope view inside the ear canal. 
Translation moves the camera sideways, so the walls close to the camera shift 
more than the eardrum does. Rotation tilts the camera, so you see the eardrum 
at an angle. The cross in the middle doesn't move. When its line of sight 
lands on the green target zone, it turns green. At that point, hold the pedal 
for 5 seconds to lock the position. 

If you do not have the joystick simply use the on-screen joystick by using
a mouse. If you wanna check that the translation/rotation selection does
actually work you should be able to use T and R on the keyboard to discriminate
between the two.

The view is drawn in the file `ui/camera_view.py`, and the geometry behind 
it is in `ui/endoscope_geometry.py`. Depth, tilt, field of view and the movement
limits are all constants at the top of that second file. Imagine it as a cilinder
of radius z onto which everything else is built --> every measure is in units 
radii.

**4. Complete.** The device is now locked in place, so you can insert the
needle (imagine to do it lol) and do the injection by hand. Afterwards, 
hold the pedal for 5 seconds to deflate the balloons. The app will then 
tell you the device can be safely removed.

If you need to go back a step, use Back in the left panel. All the
timings and the threshold are constants at the top of
`main_procedure.py`, so you can tweak them easily.

## First time on the Windows PC

Before anything else, run:

```
python joystick_diagnostic.py
```

Press X1 and X4 and note which `btnN` number shows up for each one. They
need to match `BUTTON_X1` and `BUTTON_X4` at the top of the file
`ui/xac_joystick_source.py`.
## Game version (conference) and session recording

```
python main_procedure.py --game               # kids' game: timer, stars, top-10 board
python main_procedure.py --participant P07    # clinician session tagged with a CODE (never a name)
python analyze_sessions.py                    # all sessions -> sessions_summary.csv
```

**Game.** Pressing START asks the player's age (2–18, or "Grown-up"), which sets the
level and the leaderboard group. In Align, gold stars appear on the eardrum: keep the
cross on each star until its ring fills to collect it. Once all of them are collected the
green zone lights up and can be locked with the pedal. Levels (all in `DIFFICULTIES`
at the top of `ui/game_mode.py`):

| Age group | Level  | Stars | Extra                                  |
|-----------|--------|-------|----------------------------------------|
| 2–7       | Easy   | 2     | big stars                              |
| 8–11      | Medium | 3     | smaller stars                          |
| 12–18     | Hard   | 4     | collect in numbered order, stars move  |
| Grown-ups | Expert | 5     | in order, smaller, moving faster       |

Below the camera, a drawing of the robot (`ui/robot_view.py`) shows it in the ear
canal from the side, plus the front and back balloon rings seen from the end. It is
drawn **to scale** from the sizes in millimetres at the top of that file (canal 7.5 x 25 mm;
the robot's sizes are guesses: replace them with the real device's). The balloons are round;
the back ones (P4–P6) sit in between the front ones (P1–P3), every 60° around the robot. The
**front ring is P1–P3 (teal)** and the **back ring P4–P6 (orange)**, same colours as the
slider handles. The balloons grow until they touch the canal wall at the inflation
threshold and then always stay in contact (squashed on one side when the robot moves);
the colour shows the pressure and a balloon glows white while its pressure changes.
The robot shifts with translation and tilts with rotation (front and back rings move
opposite ways), slides in at the start, shows the needle once locked and slides out at the end.

On the right, the step explanations are shown big, in two parts: "🤖 The robot"
(what the real device does, for parents to explain) and "🎮 Your turn" (what to do).

Once locked, the needle goes in, leaves the medicine (a blue drop) on the eardrum and
comes back out by itself (`GAME_INJECTION_SECONDS`); the pedal only deflates after that.

The timer starts with START and stops once the balloons are deflated, +3 s every time
the cross touches the red zone (ossicles). Stars and a top-10 board **per age group**
are saved in `game_data/highscores.json` (delete it to reset the boards). Every round
starts from a random camera position with new star positions.

Keys: **L** (or the 🏆 button) = leaderboard window with all age groups side by side:
it opens on the second screen if there is one, **F11** inside it = full screen.
**N** = new round (if a kid walks away), **F11** = game full screen, **Ctrl+Q** = quit
(Esc is disabled in the game so kids can't close it).

**Recording.** Every round (game or clinician) is saved as one file in `sessions/`,
one event per line with a timestamp: step changes, pedal presses, Back, X1/X4
switches, target/red zone entries, lock attempts and the camera path. `analyze_sessions.py`
summarises them: time in each step, number of Back presses, cancelled locks,
red-zone touches, steering path length, etc. (see the top of that file for the
column list). `sessions/` and `game_data/` are in `.gitignore`, so participant data
never ends up on GitHub.
