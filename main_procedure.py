"""
A standalone version of the procedure screen, small enough to run on its
own. It has the joysticks, the buttons, a placeholder camera image and
the live balloon pressures, arranged like ProcedurePage in
ui/pages/procedure_page.py.

The main point of this file is to show how View, ViewModel and Model talk
to each other in the Soro-tymp GUI, without the rest of the app getting in
the way. Only the joystick inputs and the 6 pressure gauges are kept,
but they sit in the same layout as the real page.


Three joystick-shaped controls, exactly matching the real app's three:
  - Translation joystick 
  - Rotation joystick   
  - Button pad           

All three emit the same positionChanged(x, y) signal, then taken by
JoystickBinding that smooths that into a MotionViewModel action
(apply_translation_from_drag / apply_orientation_from_drag), which asks
MotionController to compute new pressures and notify(). BalloonPressuresBinding
observes that notification and pushes the result into the 6 BalloonSlider
gauges. 

PEDAL-DRIVEN PROCEDURE FLOW
  1 Insert   — insert the deflated head, click Confirm.
  2 Inflate  — HOLD the pedal: all balloons inflate; release = pause.
               At INFLATION_THRESHOLD (i.e. stability simulation) inflation
               stops, "Ready to proceed to the next step" + a 5 s
               countdown appear, then the app moves to Align on its own.
  3 Align    — X1 selects TRANSLATION, X4 selects ROTATION; the
               physical stick then drives the selected mode and moves
               the DEVICE: the simulated endoscope view moves while the
               cross at its centre stays fixed. The cross turns green when
               the target zone is under it, then HOLD the pedal 5 s to LOCK.
  4 Complete — device locked; the surgeon inserts the needle and injects
               manually. Then HOLD the pedal 5 s to deflate all
               balloons -> "The device can be safely removed".

If you do not have the pedal just hold "b" on the keyboard, it behaves exactly
like the pedal. If the joystick is not compatible with your computer (like in
my case) use T/R to select translation or rotation (even if not necessary, since
you're gonna use the on-screen joysticks with the mouse in that case I suppose).
Back still steps backward and undoes each stage.

Run with:
    pip install -r requirements.txt
    python main_procedure.py                      # clinician version
    python main_procedure.py --participant P07    # clinician version, tagged with a participant code
    python main_procedure.py --game               # conference game (see ui/game_mode.py)
                                                  # L = leaderboard window, N = new round

Every run is recorded in sessions/ (see ui/session_recorder.py), and
analyze_sessions.py summarises them into a CSV. N starts a new round/session.
"""

import argparse
import sys
import time

from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer

from ui.balloon_pressures_binding import BalloonPressuresBinding
from ui.bottom_bar import BottomBar
from ui.camera_view import CameraView
from ui.control_panel import ControlPanel
from ui.foot_pedal_source import FootPedalSource
from ui import game_mode
from ui import endoscope_geometry as geo
from ui.framework.gui_marshaller import GuiMarshaller
from ui.framework.update_manager import UpdateManager
from ui.hold_to_confirm import HoldToConfirm
from ui.joystick_binding import JoystickBinding
from ui.joystick_mode_router import JoystickModeRouter, MODE_TRANSLATION, MODE_ORIENTATION
from ui.motion_controller import MotionController
from ui.motion_viewmodel import MotionViewModel
from ui.panel_left import LeftPanel
from ui.panel_right import RightPanel
from ui.session_recorder import SessionRecorder
from ui.status_banner import StatusBanner
from ui.styles import COLOR_BACKGROUND_MAIN
from ui.camera_pose_binding import CameraPoseBinding
from ui.xac_joystick_source import XacJoystickSource, BUTTON_X1, BUTTON_X4


# PART 1 (CONSTANTS)
# TUNABLE CONSTANTS:  all randomly chosen, can be changed easily from here
# when needed (e.g. inflation threshold should be changed to a value for
# which the balloons are actually making the device stable in the ear, 0.7
# is just a value chosen to see if the demo worked)

INFLATION_THRESHOLD = 0.70

# INFLATE RATE/sec:
# How fast the balloons inflate while the pedal is held (pressure units
# per second, i do not use pascal in these constants). 0.2 = more or less 3.5s
# of holding to go from 0 to 0.70.
INFLATE_RATE_PER_SEC = 0.2
COUNTDOWN_SECONDS = 5          # "Ready to proceed" -> automatic move to Align
LOCK_HOLD_SECONDS = 5.0        # pedal hold needed to LOCK
DEFLATE_HOLD_SECONDS = 5.0     # pedal hold needed to DEFLATE
DEFLATE_RAMP_SECONDS = 1.5     # how long the balloons take to empty afterwards (again, just a value for the demo)
TICK_MS = 30
POSE_SAMPLE_MS = 100           # how often the camera pose is written to the session file (only if it moved)

STAGE_INSERT, STAGE_INFLATE, STAGE_ALIGN, STAGE_COMPLETE = range(4)
STAGE_NAMES = ["insert", "inflate", "align", "complete"]   # names used in the session files
BOTTOM_BAR_LABELS = ["1. Insert", "2. Inflate", "3. Align", "4. Complete"]
STEP_TITLES = [
    "Step 1: Insert the Robot",
    "Step 2: Inflate the Robot",
    "Step 3: Align the Robot",
    "Step 4: Complete",
]
_MODE_NAMES = {MODE_TRANSLATION: "TRANSLATION", MODE_ORIENTATION: "ROTATION"}


class ProcedureWindow(QMainWindow):
    def __init__(self, viewmodel: MotionViewModel, game: bool = False,
                 participant_id: str | None = None):
        super().__init__()
        self.viewmodel = viewmodel
        self._game = game
        self._participant_id = participant_id
        self._recorder: SessionRecorder | None = None

        # Timings: the game uses shorter ones (kids!), see ui/game_mode.py
        if game:
            self._inflate_rate = game_mode.GAME_INFLATE_RATE_PER_SEC
            self._countdown_s = game_mode.GAME_COUNTDOWN_SECONDS
            self._lock_hold_s = game_mode.GAME_LOCK_HOLD_SECONDS
            self._deflate_hold_s = game_mode.GAME_DEFLATE_HOLD_SECONDS
        else:
            self._inflate_rate = INFLATE_RATE_PER_SEC
            self._countdown_s = COUNTDOWN_SECONDS
            self._lock_hold_s = LOCK_HOLD_SECONDS
            self._deflate_hold_s = DEFLATE_HOLD_SECONDS

        # Game round state
        self._round_started_at = None   # time.monotonic() when START was pressed
        self._round_id = 0
        self._player_age = None          # asked when START is pressed
        self._group_id = None            # age group -> level + leaderboard
        self._difficulty = None
        self._star_field = None          # the stars to collect in Align
        self._board_group = None         # age group shown in the side panel (None = all ages)
        self._penalty_s = 0.0
        self._danger_count = 0
        self._stage = STAGE_INSERT
        self._locked = False
        self._finished = False          # i.e. balloons deflated and device removable
        self._inflate_level = 0.0
        self._deflate_from: list[float] = []
        self._deflate_elapsed = 0.0
        self._countdown_left = 0

        self.setWindowTitle("SoroTymp — pedal + joystick procedure demo")
        self.setMinimumSize(900, 600)
        self.setStyleSheet(f"QMainWindow {{ background-color: {COLOR_BACKGROUND_MAIN}; }}")

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        center_hbox = QHBoxLayout()
        center_hbox.setContentsMargins(0, 0, 0, 0)
        center_hbox.setSpacing(0)

        self.left_panel = LeftPanel()
        center_hbox.addWidget(self.left_panel)

        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        self.status_banner = StatusBanner()
        center_layout.addWidget(self.status_banner)
        self.camera_view = CameraView()
        center_layout.addWidget(self.camera_view, 1)
        self.control_panel = ControlPanel()
        center_layout.addWidget(self.control_panel)
        center_hbox.addWidget(center_widget, 1)

        self.right_panel = RightPanel()
        center_hbox.addWidget(self.right_panel)

        root.addLayout(center_hbox, 1)

        self.bottom_bar = BottomBar(game_mode.BOTTOM_BAR_LABELS if game else BOTTOM_BAR_LABELS)
        root.addWidget(self.bottom_bar)

        self.setCentralWidget(central)

        # On-screen controls (as before): View -> Binding -> ViewModel.
        self._translation_binding = JoystickBinding(
            self.viewmodel, self.control_panel.joystick_translation, mode="translation")
        self._rotation_binding = JoystickBinding(
            self.viewmodel, self.control_panel.joystick_rotation, mode="orientation")
        self._button_pad_binding = JoystickBinding(
            self.viewmodel, self.right_panel.button_joystick, mode="translation", smoothing=0.06)

        # PART 1.2 (JOYSTICK)
        # Physical Xbox Adaptive Joystick. The stick goes through a
        # router: X1 selects translation, X4 selects rotation, and only
        # the selected channel receives the stick's movement. Keep
        # in mind that in this case the router is enabled during
        # the alignment phase only (not once locked), so that the
        # stick cannot move the robot at any other stage.
        self._physical_joystick = XacJoystickSource()
        self._physical_joystick.buttonPressed.connect(self._on_joystick_button)
        self._mode_router = JoystickModeRouter(self._physical_joystick, MODE_TRANSLATION)
        self._mode_router.modeChanged.connect(self._on_mode_changed)
        self._physical_translation_binding = JoystickBinding(
            self.viewmodel, self._mode_router.translation, mode="translation")
        self._physical_orientation_binding = JoystickBinding(
            self.viewmodel, self._mode_router.orientation, mode="orientation")

        # PART 1.3 (3D-VIEW)
        # Simulated 3D endoscopy: translation sources shift the
        # camera inside the canal, while orientation sources tilt it.
        # Hence, the view changes while the cross at the centre stays
        # kindo of fixed.
        self._crosshair_binding = CameraPoseBinding(
            self.camera_view,
            translation_sources=[self.control_panel.joystick_translation,
                                 self.right_panel.button_joystick,
                                 self._mode_router.translation],
            orientation_sources=[self.control_panel.joystick_rotation,
                                 self._mode_router.orientation],
        )
        self.camera_view.onTargetChanged.connect(self._on_target_changed)
        self.camera_view.onDangerChanged.connect(self._on_danger_changed)

        # PART 1.4 (PEDAL)
        # Foot pedal: the meaning of holding depends on the current stage.
        self._foot_pedal = FootPedalSource()
        self._foot_pedal.pressed.connect(self._on_pedal_pressed)
        self._foot_pedal.released.connect(self._on_pedal_released)

        self._inflate_timer = QTimer(self)
        self._inflate_timer.setInterval(TICK_MS)
        self._inflate_timer.timeout.connect(self._on_inflate_tick)

        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._on_countdown_tick)

        self._lock_hold = HoldToConfirm(self._lock_hold_s, self)
        self._lock_hold.progressChanged.connect(self.status_banner.set_progress)
        self._lock_hold.completed.connect(self._on_lock_completed)
        self._lock_hold.cancelled.connect(lambda: self._log("lock_hold_cancel"))

        self._deflate_hold = HoldToConfirm(self._deflate_hold_s, self)
        self._deflate_hold.progressChanged.connect(self.status_banner.set_progress)
        self._deflate_hold.completed.connect(self._on_deflate_confirmed)
        self._deflate_hold.cancelled.connect(lambda: self._log("deflate_hold_cancel"))

        self._deflate_timer = QTimer(self)
        self._deflate_timer.setInterval(TICK_MS)
        self._deflate_timer.timeout.connect(self._on_deflate_tick)

        # ViewModel -> View: pressures into the 6 gauges.
        self._balloon_binding = BalloonPressuresBinding(
            self.viewmodel, self.control_panel.balloon_sliders)
        self._balloon_binding.on_invoked()

        self.left_panel.btn_back.clicked.connect(self._retreat_step)
        self.right_panel.btn_confirm.clicked.connect(self._on_confirm_clicked)
        self.control_panel.btn_reset.clicked.connect(self.viewmodel.reset_to_center)

        # PART 1.5 (RECORDING)
        # The camera pose is sampled every POSE_SAMPLE_MS and written only
        # when it changed --> gives the steering path for the analysis.
        self._last_logged_pose = None
        self._pose_sample_timer = QTimer(self)
        self._pose_sample_timer.setInterval(POSE_SAMPLE_MS)
        self._pose_sample_timer.timeout.connect(self._on_pose_sample)
        self._pose_sample_timer.start()

        # PART 1.6 (GAME)
        if game:
            self.setWindowTitle("SoroTymp — Ear Robot Challenge")
            self._highscores = game_mode.HighScores()
            self.left_panel.set_game_mode(True)
            self._leaderboard = game_mode.LeaderboardWindow(self._highscores,
                                                            forward_key=self.keyPressEvent)
            self.left_panel.btn_leaderboard.clicked.connect(self._leaderboard.toggle)
            self._refresh_scoreboards()
            self.camera_view.show_pose_readout = False
            self.camera_view.show_danger = True
            self.camera_view.drum_overlay = self._paint_stars
            # Stars: they move and pulse, so the game ticks continuously
            self._game_tick_last = time.monotonic()
            self._game_tick = QTimer(self)
            self._game_tick.setInterval(TICK_MS)
            self._game_tick.timeout.connect(self._on_game_tick)
            self._game_tick.start()
            self.right_panel.btn_confirm.setText("START ▶")
            self.right_panel.btn_confirm.setStyleSheet(
                "QPushButton { font-size: 18pt; font-weight: 800; padding: 14px; "
                "background-color: #2E8B57; color: white; border-radius: 10px; }"
                "QPushButton:disabled { background-color: #3C3C3C; color: #808080; }")
            self._round_timer = QTimer(self)
            self._round_timer.setInterval(100)
            self._round_timer.timeout.connect(self._update_round_timer)

        self._new_round()

   
    # PART 2: MANAGEMENT OF THE 4 STAGES OF THE PROCEDURE
    # Everything that happens when moving from one step to another:
    # which controls are on, what the banner says, what the step card says,
    # and what Confirm / Back do.

    # one function per ogni stage:
    def _enter_stage(self, stage: int) -> None:
        # Called every time step is changed, going forward or back.
        # Stop any timer from the previous step first, so nothing from the
        # old step carries over e fotte il tutto.
        self._stop_all_timers()
        self._stage = stage
        self._log("stage_enter", locked=self._locked, finished=self._finished)

        # Il joystick dovrebbe allow lo streering del device solo mentre
        # si sta ancora procedendo con l'alignment e non quando l'abbiamo
        # già bloccato, altrimenti non avrebbe nemmeno senso mettere il lock
        # come misura preventiva
        # --> Regarding safety measures: for now I used the 5sec-to-hold strategy
        #   but Lukas suggested smt about adding voice control or smt like that
        #   (data: Fri 02/10/2026)
        in_align = stage == STAGE_ALIGN and not self._locked

        # X1/X4 mode switching and the button pad are only useful in Align.
        self._mode_router.set_enabled(in_align)
        self.right_panel.button_joystick.setVisible(in_align)

        # Once the device is locked, the on-screen joysticks are greyed out
        # so it can't be moved by accident.
        self.control_panel.joystick_translation.setEnabled(not self._locked)
        self.control_panel.joystick_rotation.setEnabled(not self._locked)
        self.right_panel.btn_confirm.setEnabled(stage == STAGE_INSERT)# confirm usato solo come firsr step, poi usuamo pedale
        self.left_panel.btn_back.setEnabled(stage > STAGE_INSERT and not self._finished)#back non fa nulla nel primo step e alla fine quando abbiamo finito tutto 
        self.bottom_bar.set_current_index(stage)

        #Update
        self._show_default_banner()
        self._refresh_step_card()

    def _t(self, clinical: str, game: str) -> str:
        # Picks the clinician or the kid-friendly text
        return game if self._game else clinical

    def _show_default_banner(self) -> None:
        # The banner sets the "resting" message for each step. Mentre premiamo pedale,
        # the other parts of the code temporarily replace it con una progress bar.
        self.status_banner.set_progress(None)# nasconde any leftover
        if self._stage == STAGE_INSERT:
            self.status_banner.show_message(self._t(
                "Insert the deflated head, then press Confirm",
                "Press START to begin! ▶"), "info")
        elif self._stage == STAGE_INFLATE:
            self.status_banner.show_message(self._t(
                "Hold the pedal to inflate the balloons",
                "HOLD the pedal 🦶 to blow up the balloons 🎈"), "info")
        elif self._stage == STAGE_ALIGN:
            # Show which joystick mode is active, and change the message
            # once on the target.
            mode = _MODE_NAMES[self._mode_router.mode]
            stars = self._star_field
            if self._game and self.camera_view.is_in_danger():
                self._show_danger_banner()
            elif stars is not None and not stars.done:
                if stars.cfg["ordered"]:
                    text = (f"Collect the stars IN ORDER ⭐ {stars.collected}/{stars.total} — "
                            f"next: number {stars.next_index() + 1}")
                else:
                    text = (f"Keep the cross on a star to collect it ⭐ "
                            f"{stars.collected}/{stars.total}")
                self.status_banner.show_message(text, "info")
            elif self._game and not self.camera_view.is_on_target():
                self.status_banner.show_message(
                    "All the stars! 🌟 Now put the cross on the GREEN zone. "
                    "Don't touch the RED!", "info")
            elif self.camera_view.is_on_target():
                self.status_banner.show_message(self._t(
                    f"[{mode}]  On target — hold the pedal for "
                    f"{self._lock_hold_s:.0f} s to LOCK",
                    "On the green! 🎯 HOLD the pedal to lock!"), "active")
            else:
                self.status_banner.show_message(self._t(
                    f"[{mode}]  Steer the endoscope until the green target zone is "
                    f"under the cross (X1 = translation, X4 = rotation)",
                    "Use the joystick 🕹️ to put the cross on the GREEN zone. "
                    "Don't touch the RED!"), "info")
        elif self._stage == STAGE_COMPLETE:
            if self._finished:
                self.status_banner.show_message(self._t(
                    "The device can be safely removed",
                    "All done! 🎉"), "success")
            else:
                self.status_banner.show_message(self._t(
                    "Device LOCKED — insert the needle and inject. "
                    f"When done, hold the pedal for {self._deflate_hold_s:.0f} s to deflate",
                    "Locked! 💉 Medicine given. HOLD the pedal to let the air out"), "success")

    def _show_danger_banner(self) -> None:
        # game only for now: in the clinician version the red zone is recorded but not shown
        self.status_banner.show_message(
            f"Ouch! That's the red zone (+{game_mode.RED_ZONE_PENALTY_S:.0f} s). Move away!",
            "warning")

    def _refresh_step_card(self) -> None:
        # Step card sits on rx panel and hold infos for the clinician/user
        # it is refreshed at any step change
        card = self.right_panel.step_card
        if self._game:
            card.set_content(game_mode.STEP_TITLES[self._stage],
                             game_mode.STEP_BODIES[self._stage])
            return
        title = STEP_TITLES[self._stage]
        if self._stage == STAGE_INSERT:
            body = ("Gently insert the deflated robot head into the ear canal. "
                    "Click Confirm (or press Enter) when it is in place.")
        elif self._stage == STAGE_INFLATE:
            body = (f"Hold the foot pedal to inflate all balloons. Release to "
                    f"pause. Inflation stops automatically at the stability "
                    f"threshold ({INFLATION_THRESHOLD:.2f}).")
        elif self._stage == STAGE_ALIGN:
            mode = _MODE_NAMES[self._mode_router.mode]
            target = "ON TARGET" if self.camera_view.is_on_target() else "not on target yet"
            body = (f"Joystick mode: {mode}\n"
                    f"X1 = translation, X4 = rotation.\n\n"
                    f"Moving the joystick moves the device: the endoscope view "
                    f"changes while the cross stays centred.\n\n"
                    f"Target: {target}.\n\n"
                    f"When the cross is green, hold the pedal for "
                    f"{self._lock_hold_s:.0f} s to lock the device.")
        else:
            if self._finished:
                body = ("All balloons deflated. The device can be safely "
                        "removed from the ear canal.")
            else:
                body = ("The device is locked in position. Insert the needle "
                        "and inject manually. When the procedure is finished, "
                        f"hold the pedal for {self._deflate_hold_s:.0f} s to "
                        "deflate all balloons.")
        card.set_content(title, body)

    def _on_confirm_clicked(self) -> None:
        # NB: Confirm ha senso e significa qualcosa solo in Insert, ossia che
        # la testa del device è in place, e quindi possiamo andare oltre con
        # inflation.
        if self._stage == STAGE_INSERT:
            if self._game and self._round_started_at is None:
                if not self._ask_player_age():
                    return   # age dialog closed without choosing: stay on START
                self._round_started_at = time.monotonic()
                self._round_timer.start()
            self._log("confirm")
            self._enter_stage(STAGE_INFLATE)

    def _retreat_step(self) -> None:
        # definition for back button: every step is undone by it but cannot work in first step
        # (nothing to go back to) and at the very end when the whole procedure is finished.
        # I think is useful to keep it like this also not only for the demo, because if not
        # implemented it could cause the clinician to start the procedure all over again and
        # from scratches with no justifyinble loss of time (i can't explain it better than this
        # on code but i swear it makes sense in my mind, in case just ask lol)
        if self._stage == STAGE_INSERT or self._finished:
            return
        self._log("back")
        if self._stage == STAGE_INFLATE:
            self._set_level(0.0)
            self._enter_stage(STAGE_INSERT)
        elif self._stage == STAGE_ALIGN:
            # Back to Inflate means starting the inflation over.
            self._set_level(0.0)
            self._enter_stage(STAGE_INFLATE)
        elif self._stage == STAGE_COMPLETE:
            # Unlock and go back to aligning; pressures stay where they are.
            self._locked = False
            self._enter_stage(STAGE_ALIGN)

    def _stop_all_timers(self) -> None: #literally stop every timer and cancel every pedal hold in progress
        # called on every step change so nothing keeps running inthe background and avoids unwanted changes
        # of steps
        self._inflate_timer.stop()
        self._countdown_timer.stop()
        self._lock_hold.cancel()
        self._deflate_hold.cancel()
        self._deflate_timer.stop()

    
    # PART 3: HARDWARE (PEDAL)
    # The pedal does something different in every step: inflate in
    # Inflate, lock in Align, deflate in Complete. These two methods check
    # which step we're in and decide what pressing or releasing it means.
    # (Holding "b" on the keyboard is the same thng as holding the pedal btw)

    def _on_pedal_pressed(self) -> None:
        self._log("pedal_down")
        if self._stage == STAGE_INFLATE:
            if self._countdown_timer.isActive():
                return  # threshold already reached, waiting for Align
            # ricomincia ancora da questo livello non da zero, mi sembra piu pratico cosi
            self._inflate_level = max(self.viewmodel.pressures)
            self._inflate_timer.start()
            self.status_banner.show_message(self._t(
                "Inflating…", "Inflating… keep holding! 🎈"), "active")
        elif self._stage == STAGE_ALIGN and not self._locked:
            if self._star_field is not None and not self._star_field.done:
                self._log("lock_rejected_stars_missing")
                self.status_banner.show_message(
                    f"Collect all the stars first! ⭐ {self._star_field.collected}/"
                    f"{self._star_field.total}", "warning")
                return
            if not self.camera_view.is_on_target():
                self._log("lock_rejected_off_target")
                self.status_banner.show_message(self._t(
                    "Cannot lock: the cross is not on the target zone",
                    "Not yet! Put the cross on the GREEN zone first"), "warning")
                return
            self.status_banner.show_message(self._t(
                "Keep holding to LOCK the device…", "Keep holding… 🔒"), "active")
            self._log("lock_hold_start")
            self._lock_hold.start()
        elif self._stage == STAGE_COMPLETE and self._locked and not self._finished:
            if self._deflate_timer.isActive():
                return
            self.status_banner.show_message(self._t(
                "Keep holding to DEFLATE all balloons…", "Keep holding… 💨"), "active")
            self._log("deflate_hold_start")
            self._deflate_hold.start()

    def _on_pedal_released(self) -> None:
        # Letting go pauses inflation. The balloons stay at the pressure they've reached.
        self._log("pedal_up")
        if self._stage == STAGE_INFLATE:
            if self._inflate_timer.isActive():
                self._inflate_timer.stop()
                self._log("inflation_paused", level=round(self._inflate_level, 3))
                self.status_banner.show_message(self._t(
                    f"Inflation paused at {self._inflate_level:.2f} — hold the "
                    f"pedal again to continue",
                    "Keep going! HOLD the pedal again 🦶"), "info")
        elif self._stage == STAGE_ALIGN and not self._locked:
            # Released early (or after a "cannot lock" warning): nothing
            # happens, back to the normal Align message.
            self._lock_hold.cancel()
            self._show_default_banner()
        elif self._stage == STAGE_COMPLETE and not self._finished:
            if self._deflate_timer.isActive():
                return  # deflation already running, finishes on its own
            self._deflate_hold.cancel()
            self._show_default_banner()

    
    # PART 3.2 Inflate stage

    # _SET_LEVEL Sets all balloons to the same level straight away. It's used by
    # the "Back" command to deflate everything to 0. The neutral level is cleared
    # perchè una volta tornati indietro il livello not stable anymore.

    def _set_level(self, level: float) -> None:
        self.viewmodel.set_neutral_level(None)
        self.viewmodel.inflate(level)

    def _on_inflate_tick(self) -> None:
        # Runs every TICK_MS while the pedal is held in Inflate.
        # Each tick adds a small step, so pressure goes up at
        # INFLATE_RATE_PER_SEC, and never goes past the threshold.
        step = self._inflate_rate * (TICK_MS / 1000.0)
        self._inflate_level = min(INFLATION_THRESHOLD, self._inflate_level + step)
        self.viewmodel.inflate(self._inflate_level)
        if self._inflate_level >= INFLATION_THRESHOLD:
            self._inflate_timer.stop()
            # Steer around the inflated, stable level from now on.
            self.viewmodel.set_neutral_level(INFLATION_THRESHOLD)
            self._log("inflation_reached", level=INFLATION_THRESHOLD)
            self._countdown_left = self._countdown_s
            self._show_countdown()
            self._countdown_timer.start()

    def _show_countdown(self) -> None:
        self.status_banner.show_message(self._t(
            f"Ready to proceed to the next step\n"
            f"Alignment starts in {self._countdown_left}…",
            f"Balloons ready! 🎈 Aiming in {self._countdown_left}…"), "success")
        self.status_banner.set_progress(
            1.0 - self._countdown_left / self._countdown_s)

    def _on_countdown_tick(self) -> None:
        self._countdown_left -= 1
        if self._countdown_left <= 0:
            self._countdown_timer.stop()
            self._enter_stage(STAGE_ALIGN)
        else:
            self._show_countdown()

    
    # PART 4: Align stage
    

    def _on_joystick_button(self, button: int) -> None: #use X1/X4 or R/T to select and then move the controls. Ignored outside of align and when locked
        if self._stage != STAGE_ALIGN or self._locked:
            return
        if button == BUTTON_X1:
            self._mode_router.set_mode(MODE_TRANSLATION)
        elif button == BUTTON_X4:
            self._mode_router.set_mode(MODE_ORIENTATION)

    def _on_mode_changed(self, _mode: str) -> None:
        self._log("mode_change", mode=_MODE_NAMES[self._mode_router.mode])
        if not self._lock_hold.is_running:
            self._show_default_banner()
        self._refresh_step_card()

    def _on_target_changed(self, on_target: bool) -> None:
        self._log("target_on" if on_target else "target_off")
        if self._stage != STAGE_ALIGN or self._locked:
            return
        if not on_target and self._lock_hold.is_running:
            # If moved off target during the holding the lock is cancelled and aborted (start over the alignment)
            self._lock_hold.cancel()
            self.status_banner.set_progress(None)
            self.status_banner.show_message(self._t(
                "Lock cancelled: the cross left the target zone",
                "Oops, you slipped off the green. Try again!"), "warning")
        elif not self._lock_hold.is_running:
            self._show_default_banner()
        self._refresh_step_card()

    def _on_danger_changed(self, in_danger: bool) -> None:
        # Cross on/off the red zone (ossicles). Always recorded; in the game it
        # costs RED_ZONE_PENALTY_S seconds every time the cross goes onto it.
        self._log("danger_on" if in_danger else "danger_off")
        if self._locked or self._finished:
            return
        if in_danger:
            self._danger_count += 1
            if self._game and self._round_started_at is not None:
                self._penalty_s += game_mode.RED_ZONE_PENALTY_S
                self._update_round_timer()
        if self._game and self._stage == STAGE_ALIGN and not self._lock_hold.is_running:
            self._show_default_banner()

    def _on_lock_completed(self) -> None:
        self._log("locked")
        self._locked = True
        self._enter_stage(STAGE_COMPLETE)


    # PART 3.3: Complete stage

    def _on_deflate_confirmed(self) -> None:# deflate hold is done but p doesnt jump to 0 immediately, b ut gradually!!
        self._deflate_from = list(self.viewmodel.pressures)
        self._deflate_elapsed = 0.0
        self._log("deflate_confirmed")
        self.status_banner.set_progress(None)
        self.status_banner.show_message(self._t(
            "Deflating…", "Letting the air out… 💨"), "active")
        self._deflate_timer.start()

    def _on_deflate_tick(self) -> None: #lower all baloons together in a straight line
        self._deflate_elapsed += TICK_MS / 1000.0
        fraction = min(1.0, self._deflate_elapsed / DEFLATE_RAMP_SECONDS)
        self.viewmodel.set_pressures(
            [p * (1.0 - fraction) for p in self._deflate_from])
        if fraction >= 1.0:
            self._deflate_timer.stop()
            self.viewmodel.set_neutral_level(None)
            self._finished = True
            self._enter_stage(STAGE_COMPLETE)
            self._on_round_finished()

    # PART 5: ROUNDS / SESSIONS AND RECORDING
    # One round = one go through the 4 steps = one session file in sessions/.

    def _log(self, event: str, **data) -> None:
        if self._recorder is not None:
            self._recorder.log(event, stage=STAGE_NAMES[self._stage], **data)

    def _on_pose_sample(self) -> None:
        pose = tuple(round(v, 4) for v in self.camera_view.pose)
        if pose != self._last_logged_pose:
            self._last_logged_pose = pose
            self._log("pose", tx=pose[0], ty=pose[1], yaw=pose[2], pitch=pose[3])

    def _new_round(self) -> None:
        # Start again from scratch (N key, end of a game round, or app start).
        if self._recorder is not None and not self._recorder.closed:
            self._recorder.close("abandoned")
        self._stop_all_timers()
        self._locked = False
        self._finished = False
        self._stage = STAGE_INSERT
        self._set_level(0.0)
        self._mode_router.set_mode(MODE_TRANSLATION)
        self._round_id += 1
        self._round_started_at = None
        self._player_age = self._group_id = self._difficulty = None
        self._star_field = None
        # the green zone only counts once all the stars are collected
        self.camera_view.set_target_enabled(not self._game)
        self._penalty_s = 0.0
        self._danger_count = 0

        start_pose = (game_mode.random_start_pose(self.camera_view) if self._game
                      else (0.0, 0.0, 0.0, 0.0))
        self._recorder = SessionRecorder(
            mode="game" if self._game else "clinical",
            participant_id=self._participant_id,
            meta={"inflation_threshold": INFLATION_THRESHOLD,
                  "inflate_rate_per_sec": self._inflate_rate,
                  "countdown_s": self._countdown_s,
                  "lock_hold_s": self._lock_hold_s,
                  "deflate_hold_s": self._deflate_hold_s,
                  "start_pose": [round(v, 4) for v in start_pose]})
        self._last_logged_pose = None
        self._crosshair_binding.set_pose(*start_pose)
        # where the cross starts (set_pose only reports CHANGES of target/red zone)
        self._log("start_state", on_target=self.camera_view.is_on_target(),
                  in_danger=self.camera_view.is_in_danger())
        if self._game:
            self._round_timer.stop()
            self._update_round_timer()
        self._enter_stage(STAGE_INSERT)

    def _on_round_finished(self) -> None:
        # Balloons fully deflated = end of the procedure.
        total = self._recorder.elapsed() if self._recorder else 0.0
        game_time = None
        if self._game and self._round_started_at is not None:
            self._round_timer.stop()
            game_time = time.monotonic() - self._round_started_at + self._penalty_s
            self.left_panel.timer_label.setText(f"⏱ {game_time:.1f}s")
        self._log("finished", session_s=round(total, 3), danger_entries=self._danger_count,
                  game_time_s=None if game_time is None else round(game_time, 2),
                  penalty_s=self._penalty_s if self._game else None)
        if self._recorder is not None:
            self._recorder.close("completed")
        if game_time is not None:
            self.camera_view.celebrate()
            # Let the confetti fall for a moment before the results pop up
            round_id = self._round_id
            QTimer.singleShot(1500, lambda: self._show_results(game_time, round_id))

    def _show_results(self, game_time: float, round_id: int) -> None:
        if round_id != self._round_id:
            return   # N was pressed meanwhile, a new round already started
        rank = self._highscores.rank_for(game_time, self._group_id)
        stars = game_mode.stars_for(game_time, self._difficulty)
        dialog = game_mode.ResultDialog(game_time, self._penalty_s, rank, stars,
                                        self._group_id, self._difficulty, self)
        dialog.exec()
        name = dialog.name()
        if name is not None:
            self._highscores.add(name, game_time, stars, self._player_age,
                                 self._group_id, self._difficulty)
            self._refresh_scoreboards()
        self._new_round()

    # PART 6: GAME ONLY (age, stars, leaderboard)

    def _ask_player_age(self) -> bool:
        dialog = game_mode.AgeDialog(self)
        if not dialog.exec() or dialog.age is None:
            return False
        self._player_age = dialog.age
        group = game_mode.group_for_age(dialog.age)
        self._group_id, self._difficulty = group[0], group[4]
        self._board_group = self._group_id
        self._refresh_scoreboards()
        aim = geo.aim_uv(geo.Pose(*self.camera_view.pose))
        self._star_field = game_mode.StarField(self._difficulty, self.camera_view, avoid_uv=aim)
        self._log("player", age=self._player_age, age_group=self._group_id,
                  difficulty=self._difficulty)
        self._log("stars_generated", stars=self._star_field.as_record(),
                  ordered=self._star_field.cfg["ordered"],
                  moving=self._star_field.cfg["orbit"] > 0)
        return True

    def _on_game_tick(self) -> None:
        now = time.monotonic()
        dt, self._game_tick_last = now - self._game_tick_last, now
        stars = self._star_field
        if stars is None:
            return
        collecting = self._stage == STAGE_ALIGN and not self._locked and not stars.done
        aim = geo.aim_uv(geo.Pose(*self.camera_view.pose)) if collecting else None
        collected = stars.update(dt, aim)
        if collected is not None:
            self._log("star_collected", index=collected, collected=stars.collected,
                      total=stars.total)
            if stars.done:
                self._log("all_stars_collected")
                self.camera_view.set_target_enabled(True)
            if not self._lock_hold.is_running:
                self._show_default_banner()
        self.camera_view.update()   # animation (pulsing / moving stars)

    def _paint_stars(self, painter, img_w: int, img_h: int) -> None:
        if self._star_field is not None:
            self._star_field.paint(painter, img_w, img_h, self.camera_view.target_enabled)

    def _refresh_scoreboards(self) -> None:
        self.left_panel.scoreboard_label.setText(self._highscores.as_html(self._board_group))
        self._leaderboard.refresh()

    def _update_round_timer(self) -> None:
        if self._round_started_at is None:
            seconds = 0.0
        else:
            seconds = time.monotonic() - self._round_started_at + self._penalty_s
        self.left_panel.timer_label.setText(f"⏱ {seconds:.1f}s")

  
    # "EXTRA": Keyboard shortcuts to test it without the hardware

    def keyPressEvent(self, event):
        key = event.key()
        ctrl = event.modifiers() & Qt.KeyboardModifier.ControlModifier
        if key == Qt.Key.Key_Escape and not self._game:
            self.close()   # in the game Esc does nothing (kids!), use Ctrl+Q
        elif key == Qt.Key.Key_Q and ctrl:
            self.close()
        elif key == Qt.Key.Key_N:
            self._new_round()   # abandon the current round/session and start a new one
        elif key == Qt.Key.Key_L and self._game:
            self._leaderboard.toggle()   # separate leaderboard window (second screen)
        elif key == Qt.Key.Key_F11:
            self.showNormal() if self.isFullScreen() else self.showFullScreen()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.right_panel.btn_confirm.isEnabled():
                self.right_panel.btn_confirm.click()
        elif key == Qt.Key.Key_T:
            self._on_joystick_button(BUTTON_X1)   # same as X1
        elif key == Qt.Key.Key_R:
            self._on_joystick_button(BUTTON_X4)   # same as X4
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        if self._game:
            self._game_tick.stop()
            self._leaderboard.close()   # otherwise the app keeps running with only that window
        if self._recorder is not None:
            self._recorder.close("closed")   # does nothing if already completed
        self._pose_sample_timer.stop()
        self._stop_all_timers()
        self._translation_binding.dispose()
        self._rotation_binding.dispose()
        self._button_pad_binding.dispose()
        self._physical_translation_binding.dispose()
        self._physical_orientation_binding.dispose()
        self._mode_router.dispose()
        self._physical_joystick.dispose()
        self._foot_pedal.dispose()
        self._crosshair_binding.dispose()
        super().closeEvent(event)


def main():
    parser = argparse.ArgumentParser(description="SoroTymp procedure demo")
    parser.add_argument("--game", action="store_true",
                        help="conference game version (timer, stars, high scores)")
    parser.add_argument("--participant", default=None,
                        help="participant CODE for the session files (e.g. P07), never a name")
    args, qt_args = parser.parse_known_args()

    app = QApplication([sys.argv[0]] + qt_args)

    gui_marshaller = GuiMarshaller(app)
    update_manager = UpdateManager(gui_marshaller)
    motion_controller = MotionController(update_manager)
    viewmodel = MotionViewModel(motion_controller)

    window = ProcedureWindow(viewmodel, game=args.game, participant_id=args.participant)
    if args.game:
        window.showMaximized()
    else:
        window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
