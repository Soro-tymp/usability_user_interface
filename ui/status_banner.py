"""
Made for the StatusBanner (i.e. strip above the camera view for the
big procedure messages ("Ready to proceed to the next step", the
countdown, "Hold the pedal to lock...", "The device can be safely
removed")) + an optional progress bar for the hold-to-confirm actions
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar

from ui.styles import COLOR_BACKGROUND_WIDGET, COLOR_PRIMARY, COLOR_TEXT_PRIMARY

# Background colour for each kind of message.
_KIND_COLORS = {
    "info": COLOR_BACKGROUND_WIDGET,#neutral = normal instructions
    "active": COLOR_PRIMARY,# smt happening
    "success": "#2E8B57",# green when step completed
    "warning": "#B8860B",# yellow if smt's off
}


class StatusBanner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("status-banner")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        self._label = QLabel()
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        layout.addWidget(self._label)

        # QProgressBar only takes whole numbers, so it
        # goes from 0 to 1000 instead of 0 to 1 so to move
        # smoothly instead of jumping 1% at a time
        self._progress = QProgressBar()
        self._progress.setRange(0, 1000)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(12)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self.show_message("", "info")

    def show_message(self, text: str, kind: str = "info") -> None:
        color = _KIND_COLORS.get(kind, _KIND_COLORS["info"])
        self.setStyleSheet(f"""
            #status-banner {{ background-color: {color}; }}
            #status-banner QLabel {{
                color: {COLOR_TEXT_PRIMARY}; font-size: 15pt; font-weight: 700;
            }}
            #status-banner QProgressBar {{
                background-color: #1E1E1E; border: 1px solid #555; border-radius: 5px;
            }}
            #status-banner QProgressBar::chunk {{
                background-color: #5EDA94; border-radius: 5px;
            }}
        """)
        self._label.setText(text)

    def set_progress(self, fraction) -> None:
        if fraction is None:
            self._progress.setVisible(False)
            return
        self._progress.setVisible(True)
        self._progress.setValue(int(max(0.0, min(1.0, fraction)) * 1000))
