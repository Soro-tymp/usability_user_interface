from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel

from ui.styles import COLOR_TEXT_PRIMARY

SIDE_PANEL_WIDTH = 190


class LeftPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("left-panel")
        self.setFixedWidth(SIDE_PANEL_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(8)

        # Game mode only: the big round timer and the top-10 board
        self.timer_label = QLabel()
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer_label.setStyleSheet(
            f"font-size: 26pt; font-weight: 800; color: {COLOR_TEXT_PRIMARY};")
        self.timer_label.setVisible(False)
        layout.addWidget(self.timer_label)

        self.scoreboard_label = QLabel()
        self.scoreboard_label.setWordWrap(True)
        self.scoreboard_label.setTextFormat(Qt.TextFormat.RichText)
        self.scoreboard_label.setStyleSheet(f"font-size: 11pt; color: {COLOR_TEXT_PRIMARY};")
        self.scoreboard_label.setVisible(False)
        layout.addWidget(self.scoreboard_label)

        layout.addStretch()

        self.btn_leaderboard = QPushButton("🏆 Leaderboard (L)")
        self.btn_leaderboard.setVisible(False)
        layout.addWidget(self.btn_leaderboard)

        self.btn_back = QPushButton("Back")
        layout.addWidget(self.btn_back)

    def set_game_mode(self, enabled: bool) -> None:
        self.timer_label.setVisible(enabled)
        self.scoreboard_label.setVisible(enabled)
        self.btn_leaderboard.setVisible(enabled)
