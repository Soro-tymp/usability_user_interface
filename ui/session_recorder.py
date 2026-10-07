"""
Records everything that happens during one run of the procedure, so it
can be analysed afterwards (time spent in each step, mistakes, how the
joystick was used...). Used both for clinician training sessions and for
the conference game.

One session = one file in sessions/, one JSON object per line (JSONL):

    {"t": 12.345, "wall": "2026-10-07T14:03:11.120", "event": "stage_enter",
     "stage": "align", ...extra fields...}

  - t    = seconds since the session started (time.monotonic(), so it
           can't be messed up by the computer's clock changing)
  - wall = real date/time, just to know when it happened
  - every line is written and flushed straight away: if the app crashes
    the data up to that moment is still on disk.

analyze_sessions.py turns a folder of these files into a CSV with one
row per session.

PRIVACY: never put names in participant_id, use a code (e.g. "P07").
"""

import json
import os
import time
import uuid
from datetime import datetime

SESSIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sessions")


class SessionRecorder:
    def __init__(self, mode: str, participant_id: str | None = None,
                 meta: dict | None = None, out_dir: str = SESSIONS_DIR):
        os.makedirs(out_dir, exist_ok=True)
        self.session_id = uuid.uuid4().hex[:8]
        self._t0 = time.monotonic()
        self._closed = False

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        who = participant_id or "anon"
        self.path = os.path.join(out_dir, f"{stamp}_{mode}_{who}_{self.session_id}.jsonl")
        self._file = open(self.path, "a", encoding="utf-8")

        self.log("session_start", mode=mode, participant_id=participant_id,
                 session_id=self.session_id, **(meta or {}))

    def elapsed(self) -> float:
        return time.monotonic() - self._t0

    def log(self, event: str, stage: str | None = None, **data) -> None:
        if self._closed:
            return
        record = {
            "t": round(self.elapsed(), 4),
            "wall": datetime.now().isoformat(timespec="milliseconds"),
            "event": event,
            "stage": stage,
        }
        record.update(data)
        self._file.write(json.dumps(record) + "\n")
        self._file.flush()

    def close(self, outcome: str) -> None:
        # outcome: "completed", "abandoned" (new round started before the
        # end) or "closed" (window closed before the end)
        if self._closed:
            return
        self.log("session_end", outcome=outcome)
        self._closed = True
        self._file.close()

    @property
    def closed(self) -> bool:
        return self._closed
