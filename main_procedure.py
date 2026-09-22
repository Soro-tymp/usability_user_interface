"""
main_procedure.py — Minimal standalone launcher: joysticks + buttons +
camera placeholder + live balloon pressures, laid out the same way the
real app's ProcedurePage is.

A self-contained teaching example that shows the full View <-> ViewModel
<-> Model loop used throughout the Soro-tymp GUI, stripped down to just
the joystick-shaped input widgets and the 6-channel pressure display they
drive — but arranged in the same left-panel / center / right-panel +
bottom-bar structure as ui/pages/procedure_page.py's ProcedurePage:

    +------------------------------------------------------+
    | LeftPanel |     CenterViewport      | RightPanel      |
    | (Control, |   CameraView (expand)   | (StepInstruction |
    |  Back)    |   ControlPanel (toggle, |  Card, Button   |
    |           |    hidden by default:   |  pad, Confirm)  |
    |           |    2 joysticks + 6      |                 |
    |           |    balloon gauges)      |                 |
    +------------------------------------------------------+
    |                    BottomBar                          |
    +------------------------------------------------------+

Three joystick-shaped controls, exactly matching the real app's three:
  - Translation joystick (Control panel) — mode="translation"
  - Rotation joystick    (Control panel) — mode="orientation"
  - Button pad           (right panel)   — mode="translation", same as
    the real RightSidePanel's button_joystick: a press-only pad standing
    in for the analog Translation joystick, not a second way to orient.

  Joystick / ButtonJoystick  --JoystickBinding-->  MotionViewModel
        (View, user input)      (View -> ViewModel)      |
                                                           v
                                                  MotionController (Model)
                                                    (drag -> pressures)
                                                           |
  BalloonSlider x6  <--BalloonPressuresBinding--  MotionViewModel
   (View, live gauges)        (ViewModel -> View)

All three emit the same positionChanged(x, y) signal; JoystickBinding
smooths that into a MotionViewModel action (apply_translation_from_drag /
apply_orientation_from_drag), which asks MotionController to compute new
per-channel pressures and notify(). BalloonPressuresBinding observes that
notification and pushes the result into the 6 BalloonSlider gauges. No
hardware, no serial port.

The procedure wizard (STEPS below) mirrors ProcedurePage's own
_advance_step / _retreat_step / _show_current_step trio: Confirm (right
panel, or press Return/Enter) moves forward, Back (left panel) moves
back, and the directional button-pad only appears during the "Align"
step — same gating RightSidePanel does for the real one.

Run with:
    pip install -r requirements.txt
    python main_procedure.py
"""

import sys

from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout
from PyQt6.QtCore import Qt

from ui.balloon_pressures_binding import BalloonPressuresBinding
from ui.bottom_bar import BottomBar
from ui.camera_view import CameraView
from ui.control_panel import ControlPanel
from ui.framework.gui_marshaller import GuiMarshaller
from ui.framework.update_manager import UpdateManager
from ui.joystick_binding import JoystickBinding
from ui.motion_controller import MotionController
from ui.motion_viewmodel import MotionViewModel
from ui.panel_left import LeftPanel
from ui.panel_right import RightPanel
from ui.styles import COLOR_BACKGROUND_MAIN

# The mock procedure this demo walks through — the same shape as
# ProcedurePage's own _steps list, trimmed to what applies without real
# hardware:
#   'enter_stage': 'align' is what makes the button-pad appear (see
#     RightPanel / _show_current_step below), matching how the real
#     RightSidePanel only shows its own button_joystick during that step.
#   'on_confirm' names a MotionViewModel action (looked up in
#     _advance_step below) to run when that step's Confirm is clicked —
#     mirrors ProcedurePage._steps' own on_confirm callables, e.g. its
#     inflate step calling pressure_manager.reset_pressures_to_midpoint()
#     and its Remove step ramping back down to 0.
#   'on_retreat' is this demo's own addition (the real ProcedurePage
#     doesn't undo on_confirm effects when backing up): the inverse
#     action to run when Back leaves this step going backward, so
#     stepping back past Inflate deflates again, and stepping back past
#     Complete/Finish re-inflates — the wizard is fully reversible instead
#     of only being able to undo the step *index*, not its side effects.
STEPS = [
    {
        "title": "Step 1: Insert the Robot",
        "body": "Gently insert the robot into position. Click Confirm "
                "(or press Enter) when you're ready to continue.",
    },
    {
        "title": "Step 2: Inflate the Robot",
        "body": "Once the robot is in place, click Confirm (or press "
                "Enter) to inflate it — watch the balloon gauges jump up.",
        "on_confirm": "inflate",
        "on_retreat": "deflate",
    },
    {
        "title": "Step 3: Align the Robot",
        "body": "Use the button pad below, or open Control for the "
                "Translation/Rotation joysticks, to align the robot — "
                "watch the balloons respond. Confirm when you're done.",
        "enter_stage": "align",
    },
    {
        "title": "Step 4: Complete",
        "body": "Click Finish to deflate the robot back down and end the "
                "procedure. Back still reviews earlier steps.",
        "confirm_label": "Finish",
        "on_confirm": "deflate",
        "on_retreat": "inflate",
    },
]
BOTTOM_BAR_LABELS = ["1. Insert", "2. Inflate", "3. Align", "4. Complete"]


class ProcedureWindow(QMainWindow):
    def __init__(self, viewmodel: MotionViewModel):
        super().__init__()
        self.viewmodel = viewmodel
        self._current_step_index = 0

        self.setWindowTitle("Joystick + Buttons + Balloons demo (standalone)")
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
        self.camera_view = CameraView()
        center_layout.addWidget(self.camera_view, 1)
        self.control_panel = ControlPanel()
        center_layout.addWidget(self.control_panel)
        center_hbox.addWidget(center_widget, 1)

        self.right_panel = RightPanel()
        center_hbox.addWidget(self.right_panel)

        root.addLayout(center_hbox, 1)

        self.bottom_bar = BottomBar(BOTTOM_BAR_LABELS)
        root.addWidget(self.bottom_bar)

        self.setCentralWidget(central)

        # Wiring: View -> Binding -> ViewModel. The two analog joysticks
        # (in the Control panel) drive translation/orientation at the
        # default smoothing; the ButtonJoystick (right panel) also drives
        # translation — same as the real RightSidePanel's button_joystick
        # — with a gentler ramp since a press is always full magnitude.
        self._translation_binding = JoystickBinding(
            self.viewmodel, self.control_panel.joystick_translation, mode="translation")
        self._rotation_binding = JoystickBinding(
            self.viewmodel, self.control_panel.joystick_rotation, mode="orientation")
        self._button_pad_binding = JoystickBinding(
            self.viewmodel, self.right_panel.button_joystick, mode="translation", smoothing=0.06)

        # Wiring: ViewModel -> Binding -> View, the mirror direction —
        # pushes MotionController's computed pressures into the gauges.
        self._balloon_binding = BalloonPressuresBinding(
            self.viewmodel, self.control_panel.balloon_sliders)
        # BalloonSlider defaults to its own midpoint until told otherwise,
        # and the binding only pushes on a *change* (via notify) — nothing
        # has changed yet at startup, so without this the gauges would
        # show 0.5 until the first drag/inflate even though the model
        # already starts deflated at 0. Sync them once, immediately.
        self._balloon_binding.on_invoked()
        
        self.left_panel.btn_back.clicked.connect(self._retreat_step)
        self.right_panel.btn_confirm.clicked.connect(self._advance_step)
        self.control_panel.btn_reset.clicked.connect(self.viewmodel.reset_to_center)

        self._show_current_step()

    # ------------------------------------------------------------------
    # Control panel toggle — mirrors ProcedurePage._toggle_command_palette.
    # ------------------------------------------------------------------


    # ------------------------------------------------------------------
    # Step wizard — mirrors ProcedurePage._advance_step / _retreat_step /
    # _show_current_step, trimmed to drop the blocking StepPopup the real
    # app's first step uses (nothing to connect a camera to here).
    # ------------------------------------------------------------------

    def _run_action(self, action: str | None) -> None:
        if action == "inflate":
            self.viewmodel.inflate()
        elif action == "deflate":
            self.viewmodel.deflate()

    def _advance_step(self):
        index = self._current_step_index
        if index >= len(STEPS):
            return
        self._run_action(STEPS[index].get("on_confirm"))
        self._current_step_index = index + 1
        self._show_current_step()

    def _retreat_step(self):
        index = self._current_step_index
        if index <= 0:
            return
        # Undo whatever on_confirm did when we originally advanced from
        # index-1 into index, by running that step's declared inverse.
        self._run_action(STEPS[index - 1].get("on_retreat"))
        self._current_step_index = index - 1
        self._show_current_step()

    def _show_current_step(self):
        index = self._current_step_index
        finished = index >= len(STEPS)

        if not finished:
            step = STEPS[index]
            self.right_panel.step_card.set_content(step["title"], step["body"])
            self.right_panel.step_card.setVisible(True)
            self.right_panel.btn_confirm.setText(step.get("confirm_label", "Confirm"))
            self.right_panel.button_joystick.setVisible(step.get("enter_stage") == "align")
        else:
            self.right_panel.step_card.setVisible(False)
            self.right_panel.button_joystick.setVisible(False)

        self.left_panel.btn_back.setEnabled(index > 0)
        self.right_panel.btn_confirm.setEnabled(not finished)
        self.bottom_bar.set_current_index(min(index, len(STEPS) - 1))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # Same as clicking Confirm — works regardless of which widget
            # currently has keyboard focus.
            if self.right_panel.btn_confirm.isEnabled():
                self.right_panel.btn_confirm.click()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self._translation_binding.dispose()
        self._rotation_binding.dispose()
        self._button_pad_binding.dispose()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)

    gui_marshaller = GuiMarshaller(app)
    update_manager = UpdateManager(gui_marshaller)
    motion_controller = MotionController(update_manager)
    viewmodel = MotionViewModel(motion_controller)

    window = ProcedureWindow(viewmodel)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
