"""
Turns the recorded sessions (sessions/*.jsonl, written by
ui/session_recorder.py) into one CSV with ONE ROW PER SESSION, ready to
open in Excel / pandas / R.

Run with:
    python analyze_sessions.py                     # all sessions -> sessions_summary.csv
    python analyze_sessions.py --mode clinical     # only clinician sessions
    python analyze_sessions.py --out results.csv

Columns:
  t_insert, t_inflate, t_align, t_complete
      seconds spent in each step. If Back was used, the time of every visit
      to that step is added up. Counting stops when the procedure is finished.
  total_s           from session start to the end of the deflation
  n_back            Back presses (= going back a step)
  n_pedal_presses   all pedal presses
  n_inflate_pauses  pedal released before the inflation threshold
  n_lock_rejected   pedal pressed in Align while NOT on target
  n_lock_cancels    lock holds stopped early (pedal released / slipped off target)
  n_target_entries  how many times the cross went onto the green zone
  n_danger_entries  how many times the cross went onto the red zone (ossicles)
  n_mode_switches   translation <-> rotation switches (X1/X4)
  align_path        total distance travelled by the camera pose during Align
                    (sum of |change| of tx, ty, yaw, pitch, all in -1..1 units)
                    --> lower = more direct steering
  time_to_first_target  seconds from entering Align (first time) to first time on target
  game only: age, age_group, difficulty, stars_collected / stars_total, game_time_s
      (time shown to the player, penalties included), penalty_s (red zone)
"""

import argparse
import csv
import glob
import json
import os

from ui.session_recorder import SESSIONS_DIR

STAGES = ["insert", "inflate", "align", "complete"]

COLUMNS = (["file", "session_id", "mode", "participant_id", "started", "outcome", "completed",
            "total_s"] + [f"t_{s}" for s in STAGES] +
           ["n_back", "n_pedal_presses", "n_inflate_pauses", "n_lock_rejected", "n_lock_cancels",
            "n_target_entries", "n_danger_entries", "n_mode_switches", "align_path",
            "time_to_first_target", "age", "age_group", "difficulty", "stars_collected",
            "stars_total", "game_time_s", "penalty_s"])


def summarise(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        events = [json.loads(line) for line in f if line.strip()]
    if not events:
        return {}

    start = events[0]
    row = {c: None for c in COLUMNS}
    row.update(file=os.path.basename(path), session_id=start.get("session_id"),
               mode=start.get("mode"), participant_id=start.get("participant_id"),
               started=start.get("wall"), completed=False)
    for s in STAGES:
        row[f"t_{s}"] = 0.0
    counts = dict(n_back=0, n_pedal_presses=0, n_inflate_pauses=0, n_lock_rejected=0,
                  n_lock_cancels=0, n_target_entries=0, n_danger_entries=0, n_mode_switches=0)
    align_path = 0.0
    last_pose = start.get("start_pose")
    first_align_t = None

    current_stage, stage_since, stopped = None, None, False

    for e in events:
        t, ev = e["t"], e["event"]
        if ev == "stage_enter" and not stopped:
            if current_stage is not None:
                row[f"t_{current_stage}"] += t - stage_since
            current_stage, stage_since = e["stage"], t
            if current_stage == "align" and first_align_t is None:
                first_align_t = t
        elif ev in ("finished", "session_end") and not stopped:
            if current_stage is not None:
                row[f"t_{current_stage}"] += t - stage_since
            stopped = True
            if ev == "finished":
                row["completed"] = True
                row["total_s"] = round(t, 3)
                row["game_time_s"] = e.get("game_time_s")
                row["penalty_s"] = e.get("penalty_s")
        if ev == "session_end":
            row["outcome"] = e.get("outcome")
        elif ev == "back":
            counts["n_back"] += 1
        elif ev == "pedal_down":
            counts["n_pedal_presses"] += 1
        elif ev == "inflation_paused":
            counts["n_inflate_pauses"] += 1
        elif ev == "lock_rejected_off_target":
            counts["n_lock_rejected"] += 1
        elif ev == "lock_hold_cancel":
            counts["n_lock_cancels"] += 1
        elif ev == "target_on":
            counts["n_target_entries"] += 1
            if first_align_t is not None and row["time_to_first_target"] is None \
                    and e["stage"] == "align":
                row["time_to_first_target"] = round(t - first_align_t, 3)
        elif ev == "danger_on":
            counts["n_danger_entries"] += 1
        elif ev == "mode_change":
            counts["n_mode_switches"] += 1
        elif ev == "player":
            row.update(age=e.get("age"), age_group=e.get("age_group"),
                       difficulty=e.get("difficulty"), stars_collected=0)
        elif ev == "stars_generated":
            row["stars_total"] = len(e.get("stars", []))
        elif ev == "star_collected":
            row["stars_collected"] = e.get("collected")
        elif ev == "pose":
            pose = [e["tx"], e["ty"], e["yaw"], e["pitch"]]
            if last_pose is not None and e["stage"] == "align":
                align_path += sum(abs(a - b) for a, b in zip(pose, last_pose))
            last_pose = pose

    if row["outcome"] is None:
        row["outcome"] = "crashed?"   # no session_end line: the app didn't close normally
    for s in STAGES:
        row[f"t_{s}"] = round(row[f"t_{s}"], 3)
    row.update(counts)
    row["align_path"] = round(align_path, 4)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dir", default=SESSIONS_DIR)
    parser.add_argument("--out", default="sessions_summary.csv")
    parser.add_argument("--mode", choices=["clinical", "game"], default=None)
    args = parser.parse_args()

    rows = [summarise(p) for p in sorted(glob.glob(os.path.join(args.dir, "*.jsonl")))]
    rows = [r for r in rows if r and (args.mode is None or r["mode"] == args.mode)]

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    done = [r for r in rows if r["completed"]]
    print(f"{len(rows)} sessions ({len(done)} completed) -> {args.out}")
    if done:
        for s in STAGES:
            mean = sum(r[f"t_{s}"] for r in done) / len(done)
            print(f"  mean t_{s:<9} {mean:6.1f} s")


if __name__ == "__main__":
    main()
