"""
Everything specific to the conference GAME version (python main_procedure.py --game).
The procedure itself is the same as the clinician one, only:
  - pressing START asks the player's age --> picks the level and the leaderboard
  - shorter holds/countdowns (kids from 4 to 15 years old, + grown-ups)
  - in Align, STARS appear on the eardrum: keep the cross on each one to
    collect it. Only when they're all collected does the green zone light up
    and the device can be locked. Older players get more, smaller stars, that
    must be collected in order and that move (see DIFFICULTIES).
  - a timer that starts with START and stops when the balloons are deflated
  - touching the red zone (ossicles) adds RED_ZONE_PENALTY_S seconds
  - stars rating + one top-10 board per age group (saved in game_data/highscores.json),
    shown in the side panel and in a separate window (L key) for a second screen
  - every round starts from a random camera position, so it's never the same twice

All the numbers below are guesses: play a few rounds yourself and tune
them (especially star3_s / star2_s, the times for 3 and 2 stars).
"""

import json
import math
import os
import random
from datetime import datetime

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QColor, QPen, QPolygonF, QFont, QGuiApplication
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
                             QLineEdit, QPushButton, QWidget)

from ui import endoscope_geometry as geo
from ui.styles import COLOR_BACKGROUND_MAIN, COLOR_BACKGROUND_WIDGET, COLOR_TEXT_PRIMARY

# Shorter timings than the clinician version
GAME_INFLATE_RATE_PER_SEC = 0.35
GAME_COUNTDOWN_SECONDS = 2
GAME_LOCK_HOLD_SECONDS = 2.0
GAME_DEFLATE_HOLD_SECONDS = 2.0

RED_ZONE_PENALTY_S = 3.0
HIGHSCORE_SIZE = 10

# (id saved in the files, label on screen, min age, max age, difficulty)
AGE_GROUPS = [
    ("4-7", "Ages 4–7", 4, 7, "easy"),
    ("8-11", "Ages 8–11", 8, 11, "medium"),
    ("12-15", "Ages 12–15", 12, 15, "hard"),
    ("adult", "Grown-ups", 16, 200, "expert"),
]
ADULT_AGE = 16   # what the "Grown-up" button records

# Levels. radius = star size on the eardrum image (0..1 = whole image width),
# dwell_s = how long the cross must stay on a star to collect it,
# ordered = stars are numbered and must be collected 1, 2, 3...,
# orbit/orbit_speed = stars move in a small circle (image units, rad/s).
DIFFICULTIES = {
    "easy":   dict(label="Easy",   n_stars=2, radius=0.075, dwell_s=0.4, ordered=False,
                   orbit=0.0, orbit_speed=0.0, star3_s=40.0, star2_s=80.0),
    "medium": dict(label="Medium", n_stars=3, radius=0.060, dwell_s=0.5, ordered=False,
                   orbit=0.0, orbit_speed=0.0, star3_s=45.0, star2_s=90.0),
    "hard":   dict(label="Hard",   n_stars=4, radius=0.050, dwell_s=0.6, ordered=True,
                   orbit=0.030, orbit_speed=1.2, star3_s=55.0, star2_s=110.0),
    "expert": dict(label="Expert", n_stars=5, radius=0.042, dwell_s=0.7, ordered=True,
                   orbit=0.028, orbit_speed=2.2, star3_s=60.0, star2_s=120.0),
}

# Where stars can go: the end of the canal that the camera can actually see
# (centre u, v and radius, image units). The image is wider than the canal
# (DRUM_HALF_SIZE 1.15 vs canal radius 1), so beyond ~0.43 it's hidden by the walls.
VISIBLE_DISK = (0.5, 0.5, 0.40)

HIGHSCORES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                               "game_data", "highscores.json")

BOTTOM_BAR_LABELS = ["1. Go in", "2. Balloons", "3. Stars & aim", "4. Finish"]
STEP_TITLES = [
    "1. Go into the ear 👂",
    "2. Blow up the balloons 🎈",
    "3. Collect the stars ⭐",
    "4. Give the medicine 💉",
]
# Step card text: for the parents to read out, and explains what the real robot does.
STEP_BODIES = [
    "Doctors gently slide a tiny soft robot into the ear.\n\n"
    "Press START to begin. Be quick, you're being timed!",
    "Little balloons on the robot fill with air so it stays still, "
    "like a gentle hug inside the ear.\n\n"
    "HOLD the pedal down until they're full.",
    "The camera on the robot shows the eardrum.\n\n"
    "Use the joystick and keep the cross on each STAR ⭐ to collect it.\n\n"
    "Then aim at the GREEN zone (the safe place for the medicine) and HOLD the pedal.\n\n"
    "RED = tiny ear bones, don't touch them!",
    "The robot is locked, so the doctor can give the medicine through "
    "the eardrum.\n\nHOLD the pedal to let the air out of the balloons. Finished!",
]


def group_for_age(age: int) -> tuple:
    for group in AGE_GROUPS:
        if group[2] <= age <= group[3]:
            return group
    return AGE_GROUPS[-1]


def group_label(group_id: str | None) -> str:
    for gid, label, *_ in AGE_GROUPS:
        if gid == group_id:
            return label
    return "All ages"


def stars_for(seconds: float, difficulty: str) -> int:
    d = DIFFICULTIES[difficulty]
    if seconds <= d["star3_s"]:
        return 3
    if seconds <= d["star2_s"]:
        return 2
    return 1


def random_start_pose(camera_view) -> tuple[float, float, float, float]:
    # A random camera position where the cross is neither on the green nor
    # on the red zone and is reasonably far from the green one, so every round
    # needs a bit of steering.
    u0, v0, u1, v1 = camera_view.target_zone
    cu, cv = (u0 + u1) / 2, (v0 + v1) / 2
    for _ in range(500):
        pose = tuple(random.uniform(-0.7, 0.7) for _ in range(4))
        uv = geo.aim_uv(geo.Pose(*pose))
        if uv is None or not (0.15 <= uv[0] <= 0.85 and 0.15 <= uv[1] <= 0.85):
            continue
        if camera_view.uv_on_target(uv) or camera_view.uv_in_danger(uv):
            continue
        if math.hypot(uv[0] - cu, uv[1] - cv) < 0.25:
            continue
        return pose
    return (0.0, 0.0, 0.0, 0.0)


# STARS (the multiple targets)

class StarField:
    """The stars to collect in Align. Positions are in eardrum-image units
    (u, v from 0 to 1, same as CameraView.target_zone), so they are drawn ON
    the eardrum, in perspective, and hidden by the canal walls like the image."""

    def __init__(self, difficulty: str, camera_view, avoid_uv=None):
        self.difficulty = difficulty
        self.cfg = DIFFICULTIES[difficulty]
        self._camera_view = camera_view
        self.t = 0.0
        self.stars = self._generate(avoid_uv)   # dicts: cu, cv, phase, collected_at
        self._dwell_index = None
        self._dwell = 0.0

    def _candidates(self, reach: float) -> list[tuple[float, float]]:
        # Every spot (on a 0.01 grid) where a star fits: visible, and the star
        # plus the circle it moves on stay off the red zone and the green zone.
        u0, v0, u1, v1 = self._camera_view.target_zone
        cu, cv, radius = VISIBLE_DISK
        spots = []
        for i in range(101):
            for j in range(101):
                uv = (i / 100, j / 100)
                if math.dist(uv, (cu, cv)) > radius - reach:
                    continue
                if u0 - reach <= uv[0] <= u1 + reach and v0 - reach <= uv[1] <= v1 + reach:
                    continue
                ring = [(uv[0] + reach * math.cos(a), uv[1] + reach * math.sin(a))
                        for a in [k * math.pi / 4 for k in range(8)]] + [uv]
                if any(self._camera_view.uv_in_danger(p) for p in ring):
                    continue
                spots.append(uv)
        return spots

    def _generate(self, avoid_uv):
        # Pick random spots, far enough from each other and from where the cross
        # starts. A few attempts, keeping the one with the most stars.
        reach = self.cfg["radius"] + self.cfg["orbit"]
        spots = self._candidates(reach)
        if avoid_uv is not None:
            spots = [p for p in spots if math.dist(p, avoid_uv) >= reach + 0.06]
        best = []
        for _ in range(40):
            random.shuffle(spots)
            chosen = []
            for p in spots:
                if all(math.dist(p, q) >= 2 * reach + 0.02 for q in chosen):
                    chosen.append(p)
                    if len(chosen) == self.cfg["n_stars"]:
                        break
            if len(chosen) > len(best):
                best = chosen
            if len(best) == self.cfg["n_stars"]:
                break
        return [dict(cu=u, cv=v, phase=random.uniform(0, 2 * math.pi), collected_at=None)
                for u, v in best]

    @property
    def total(self) -> int:
        return len(self.stars)

    @property
    def collected(self) -> int:
        return sum(1 for s in self.stars if s["collected_at"] is not None)

    @property
    def done(self) -> bool:
        return self.collected == self.total

    def position(self, i: int) -> tuple[float, float]:
        s = self.stars[i]
        a = s["phase"] + self.t * self.cfg["orbit_speed"]
        return (s["cu"] + self.cfg["orbit"] * math.cos(a),
                s["cv"] + self.cfg["orbit"] * math.sin(a))

    def next_index(self) -> int | None:
        # ordered levels: the lowest-numbered star still there
        for i, s in enumerate(self.stars):
            if s["collected_at"] is None:
                return i
        return None

    def _collectable(self) -> list[int]:
        if self.cfg["ordered"]:
            i = self.next_index()
            return [] if i is None else [i]
        return [i for i, s in enumerate(self.stars) if s["collected_at"] is None]

    def update(self, dt: float, aim_uv) -> int | None:
        # Called every tick. aim_uv = where the cross points (None = can't
        # collect right now, the stars still move). Returns the index of a star
        # that has just been collected.
        self.t += dt
        hit = None
        if aim_uv is not None:
            for i in self._collectable():
                if math.dist(aim_uv, self.position(i)) <= self.cfg["radius"]:
                    hit = i
                    break
        if hit is None:
            self._dwell_index, self._dwell = None, 0.0
            return None
        if hit != self._dwell_index:
            self._dwell_index, self._dwell = hit, 0.0
        self._dwell += dt
        if self._dwell >= self.cfg["dwell_s"]:
            self.stars[hit]["collected_at"] = self.t
            self._dwell_index, self._dwell = None, 0.0
            return hit
        return None

    def as_record(self) -> list[dict]:
        return [dict(u=round(s["cu"], 4), v=round(s["cv"], 4)) for s in self.stars]

    # drawing (called by CameraView inside the eardrum's perspective transform,
    # so 1 unit = 1 pixel of the eardrum image)

    def paint(self, painter, img_w: int, img_h: int, target_active: bool) -> None:
        if target_active:
            # green zone glows once all the stars are collected
            u0, v0, u1, v1 = self._camera_view.target_zone
            glow = 0.5 + 0.5 * math.sin(self.t * 5)
            painter.setPen(QPen(QColor(94, 218, 148, 255), 6))
            painter.setBrush(QColor(94, 218, 148, int(40 + 70 * glow)))
            painter.drawRoundedRect(QRectF(u0 * img_w, v0 * img_h,
                                           (u1 - u0) * img_w, (v1 - v0) * img_h), 12, 12)

        next_i = self.next_index() if self.cfg["ordered"] else None
        for i, s in enumerate(self.stars):
            u, v = self.position(i)
            cx, cy = u * img_w, v * img_h
            r = self.cfg["radius"] * img_w
            if s["collected_at"] is not None:
                # little burst for half a second after collecting
                age = self.t - s["collected_at"]
                if age < 0.5:
                    f = age / 0.5
                    painter.setPen(QPen(QColor(255, 200, 61, int(255 * (1 - f))), 5))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawEllipse(QPointF(cx, cy), r * (1 + 1.5 * f), r * (1 + 1.5 * f))
                continue
            active = next_i is None or i == next_i
            pulse = 1.0 + (0.12 * math.sin(self.t * 6) if active else 0.0)
            painter.setPen(QPen(QColor(90, 60, 0), 3))
            painter.setBrush(QColor(255, 200, 61, 255 if active else 110))
            painter.drawPolygon(_star_polygon(cx, cy, r * pulse))
            if self.cfg["ordered"]:
                font = QFont()
                font.setPixelSize(max(8, int(r * 0.9)))
                font.setBold(True)
                painter.setFont(font)
                painter.setPen(QColor(60, 40, 0))
                painter.drawText(QRectF(cx - r, cy - r, 2 * r, 2 * r),
                                 Qt.AlignmentFlag.AlignCenter, str(i + 1))
            if i == self._dwell_index:
                # white ring filling up while the cross stays on the star
                painter.setPen(QPen(QColor(255, 255, 255), 5))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                span = int(-360 * 16 * min(1.0, self._dwell / self.cfg["dwell_s"]))
                painter.drawArc(QRectF(cx - r * 1.4, cy - r * 1.4, r * 2.8, r * 2.8), 90 * 16, span)


def _star_polygon(cx, cy, r) -> QPolygonF:
    pts = []
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        rr = r if k % 2 == 0 else r * 0.45
        pts.append(QPointF(cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return QPolygonF(pts)


# LEADERBOARD

class HighScores:
    def __init__(self, path: str = HIGHSCORES_PATH):
        self._path = path
        self.entries: list[dict] = []
        try:
            with open(path, encoding="utf-8") as f:
                self.entries = json.load(f)
        except (OSError, ValueError):
            self.entries = []
        self.entries.sort(key=lambda e: e["seconds"])
        self.latest = None   # the entry added last, highlighted on the boards

    def top(self, group_id: str | None) -> list[dict]:
        rows = [e for e in self.entries if group_id is None or e.get("group") == group_id]
        return rows[:HIGHSCORE_SIZE]

    def rank_for(self, seconds: float, group_id: str) -> int:
        # 1 = best, within the age group. Ties go after the existing entries.
        return 1 + sum(1 for e in self.entries
                       if e.get("group") == group_id and e["seconds"] <= seconds)

    def add(self, name: str, seconds: float, stars: int, age: int, group_id: str,
            difficulty: str) -> None:
        entry = {"name": name, "seconds": round(seconds, 1), "stars": stars, "age": age,
                 "group": group_id, "difficulty": difficulty,
                 "date": datetime.now().isoformat(timespec="seconds")}
        self.entries.append(entry)
        self.entries.sort(key=lambda e: e["seconds"])
        self.latest = entry
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.entries, f, indent=1)
        os.replace(tmp, self._path)   # never leaves a half-written file

    def as_html(self, group_id: str | None, big: bool = False) -> str:
        size = 18 if big else 11
        title_size = 24 if big else 13
        rows = ""
        for i, e in enumerate(self.top(group_id), 1):
            style = " style='background-color:#6B5310'" if e is self.latest else ""
            stars = f"<td style='color:#FFC83D'>{'★' * e['stars']}</td>" if big else ""
            rows += (f"<tr{style}><td>{i}.</td><td>{_escape(e['name'])}</td>"
                     f"<td align='right'>{e['seconds']:.1f}s</td>{stars}</tr>")
        if not rows:
            rows = "<tr><td>Be the first!</td></tr>"
        return (f"<div style='font-size:{title_size}pt; font-weight:800; color:#FFC83D'>"
                f"🏆 {group_label(group_id)}</div>"
                f"<table width='100%' cellspacing='4' style='font-size:{size}pt'>{rows}</table>")


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class LeaderboardWindow(QWidget):
    # A separate window with every age group side by side: drag it onto a second
    # screen (it opens there by itself if there is one) and press F11 for full screen.
    # L toggles it from the game window. Other keys are passed back to the game.
    def __init__(self, highscores: HighScores, forward_key=None):
        super().__init__()
        self._highscores = highscores
        self._forward_key = forward_key
        self._placed = False
        self.setWindowTitle("Ear Robot Challenge — Leaderboard")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)  # keep the game focused
        self.resize(1100, 600)
        self.setStyleSheet(f"background-color: {COLOR_BACKGROUND_MAIN}; color: {COLOR_TEXT_PRIMARY};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)
        title = QLabel("🏆 Ear Robot Challenge 🏆")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 36pt; font-weight: 800;")
        layout.addWidget(title)

        columns = QHBoxLayout()
        columns.setSpacing(30)
        self._columns = {}
        for gid, *_ in AGE_GROUPS:
            label = QLabel()
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setAlignment(Qt.AlignmentFlag.AlignTop)
            label.setStyleSheet(f"background-color: {COLOR_BACKGROUND_WIDGET}; "
                                "border-radius: 14px; padding: 14px;")
            columns.addWidget(label, 1)
            self._columns[gid] = label
        layout.addLayout(columns, 1)
        self.refresh()

    def refresh(self) -> None:
        for gid, label in self._columns.items():
            label.setText(self._highscores.as_html(gid, big=True))

    def toggle(self) -> None:
        if self.isVisible():
            self.hide()
            return
        if not self._placed:
            screens = QGuiApplication.screens()
            if len(screens) > 1:
                self.move(screens[1].availableGeometry().topLeft())
            self._placed = True
        self.show()
        self.raise_()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F11:
            self.showNormal() if self.isFullScreen() else self.showFullScreen()
        elif event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.showNormal()
        elif self._forward_key is not None:
            self._forward_key(event)


# DIALOGS

class AgeDialog(QDialog):
    # Big buttons, one tap: the age picks the level and the leaderboard.
    def __init__(self, parent=None):
        super().__init__(parent)
        self.age = None
        self.setWindowTitle("How old are you?")
        self.setModal(True)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {COLOR_BACKGROUND_WIDGET}; }}
            QLabel {{ color: {COLOR_TEXT_PRIMARY}; }}
            QPushButton {{ font-size: 22pt; font-weight: 800; min-width: 80px; min-height: 64px;
                           background-color: #2B9DA1; color: white; border-radius: 12px; }}
            QPushButton:hover {{ background-color: #35B5BA; }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("How old are you? 🎂")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 26pt; font-weight: 800;")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(10)
        for k, age in enumerate(range(4, 16)):
            button = QPushButton(str(age))
            button.setAutoDefault(False)
            button.clicked.connect(lambda _=False, a=age: self._pick(a))
            grid.addWidget(button, k // 4, k % 4)
        layout.addLayout(grid)

        adult = QPushButton("Grown-up 🧑")
        adult.setAutoDefault(False)
        adult.setStyleSheet("background-color: #8E7CFF;")
        adult.clicked.connect(lambda: self._pick(ADULT_AGE))
        layout.addWidget(adult)

    def _pick(self, age: int) -> None:
        self.age = age
        self.accept()


class ResultDialog(QDialog):
    # The end-of-round screen: stars, time, and a name field if the time
    # makes it into the top 10 of the age group. Enter (or the button) = play again.
    def __init__(self, seconds: float, penalty_s: float, rank: int, stars: int,
                 group_id: str, difficulty: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Well done!")
        self.setModal(True)
        self.setMinimumWidth(460)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {COLOR_BACKGROUND_WIDGET}; }}
            QLabel {{ color: {COLOR_TEXT_PRIMARY}; }}
            QLineEdit {{ font-size: 20pt; padding: 6px; }}
            QPushButton {{ font-size: 18pt; font-weight: 700; padding: 12px;
                           background-color: #2E8B57; color: white; border-radius: 10px; }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("🎉 Well done, Doctor! 🎉")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 24pt; font-weight: 800;")
        layout.addWidget(title)

        level = QLabel(f"{DIFFICULTIES[difficulty]['label']} level · {group_label(group_id)}")
        level.setAlignment(Qt.AlignmentFlag.AlignCenter)
        level.setStyleSheet("font-size: 13pt; color: #AAAAAA;")
        layout.addWidget(level)

        star_label = QLabel(
            f"<span style='color:#FFC83D'>{'★' * stars}</span>"
            f"<span style='color:#555'>{'★' * (3 - stars)}</span>")
        star_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        star_label.setStyleSheet("font-size: 64pt;")
        layout.addWidget(star_label)

        time_text = f"Your time: <b>{seconds:.1f} s</b>"
        if penalty_s > 0:
            time_text += (f"<br><span style='font-size:12pt'>(includes +{penalty_s:.0f} s "
                          f"for touching the red zone)</span>")
        time_label = QLabel(time_text)
        time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        time_label.setWordWrap(True)
        time_label.setStyleSheet("font-size: 20pt;")
        layout.addWidget(time_label)

        self._name_edit = None
        if rank <= HIGHSCORE_SIZE:
            rank_label = QLabel(f"You're number {rank} for {group_label(group_id)}! 🏆"
                                f"<br>Type your name:")
            rank_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rank_label.setWordWrap(True)
            rank_label.setStyleSheet("font-size: 16pt;")
            layout.addWidget(rank_label)
            self._name_edit = QLineEdit()
            self._name_edit.setMaxLength(12)
            self._name_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self._name_edit)
            self._name_edit.setFocus()

        button = QPushButton("Play again ▶")
        button.setDefault(True)
        button.clicked.connect(self.accept)
        layout.addWidget(button)

    def name(self) -> str | None:
        # None = not in the top 10. An empty name still counts on the board.
        if self._name_edit is None:
            return None
        return self._name_edit.text().strip() or "Doctor"
