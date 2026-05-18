#!/usr/bin/env python3
"""
Summarize race_score_450 vs finish_place from gameplay_frida.json.

  python RE_Tools/tools/scripts/analyze_gameplay_frida.py
  python RE_Tools/tools/scripts/analyze_gameplay_frida.py RE_Tools/analysis/gameplay_frida.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT = ROOT / "RE_Tools" / "analysis" / "gameplay_frida.json"


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    if not path.is_file():
        print(f"Missing {path} — run frida_gameplay_hooks.py --attach first")
        return 1

    data = json.loads(path.read_text(encoding="utf-8"))
    events = data.get("events") or data.get("race_advance_sim") or []
    if isinstance(data.get("summary"), dict):
        events = data["summary"].get("race_ticks") or events

    rows = []
    for ev in events:
        if ev.get("kind") != "race_advance_sim":
            continue
        snap = ev.get("snapshot") or {}
        score = snap.get("race_score_450")
        horses = snap.get("horses") or []
        finished = [h for h in horses if h.get("finish_place", -1) >= 0]
        rows.append((score, finished, ev.get("ts")))

    if not rows:
        print("No race_advance_sim events in JSON")
        return 0

    print(f"race ticks: {len(rows)}")
    for i, (score, finished, ts) in enumerate(rows[:12]):
        print(f"  [{i}] ts={ts} race_score_450={score} finished_slots={finished}")
    if len(rows) > 12:
        print(f"  ... {len(rows) - 12} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
