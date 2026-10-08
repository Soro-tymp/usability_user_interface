from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

from ui.styles import COLOR_PRIMARY, COLOR_PRIMARY_PRESSED, COLOR_TEXT_PRIMARY


class StepInstructionCard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("step-instruction-card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            #step-instruction-card {{
                background-color: {COLOR_PRIMARY_PRESSED};
                border: 3px solid {COLOR_PRIMARY};
                border-radius: 16px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        self._title_label = QLabel()
        self._title_label.setWordWrap(True)
        self._title_label.setMinimumHeight(45)
        self._title_label.setStyleSheet(
            f"font-size: 12pt; font-weight: 700; color: {COLOR_TEXT_PRIMARY}; border: none;")
        layout.addWidget(self._title_label)

        self._body_label = QLabel()
        self._body_label.setWordWrap(True)
        # A fixed floor instead of relying purely on wordWrap's
        # heightForWidth, which needs the layout to already know this
        # widget's final width to compute a wrapped height — a chicken-
        # and-egg the layout doesn't always resolve before the first
        # paint, silently clipping the text otherwise.
        self._body_label.setMinimumHeight(135)
        self._body_label.setStyleSheet(
            f"font-size: 10pt; color: {COLOR_TEXT_PRIMARY}; border: none;")
        layout.addWidget(self._body_label)

    def set_large(self) -> None:
        # Game: big text, for kids and parents to read from a distance
        self.set_text_size(big=False)
        self._body_label.setTextFormat(Qt.TextFormat.RichText)
        self._body_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._body_label.setMinimumHeight(200)
        # the card fills the panel (see RightPanel.expand_card): keep title + text
        # together in the middle of it, instead of an empty strip at the bottom
        layout = self.layout()
        layout.insertStretch(0, 1)
        layout.addStretch(1)

    def set_text_size(self, big: bool) -> None:
        # big = wide panel (large screen): even bigger text, so the card doesn't look empty
        title_pt, body_pt = (28, 19) if big else (22, 15)
        self._title_label.setStyleSheet(
            f"font-size: {title_pt}pt; font-weight: 800; color: {COLOR_TEXT_PRIMARY}; border: none;")
        self._body_label.setStyleSheet(
            f"font-size: {body_pt}pt; color: {COLOR_TEXT_PRIMARY}; border: none;")

    def set_content(self, title: str, body: str) -> None:
        self._title_label.setText(title)
        self._body_label.setText(body)
        
