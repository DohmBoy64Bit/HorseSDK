#!/usr/bin/env python3
"""
Race correlation report: race_ctx+0x450 vs finish_place / progress.

Reads gameplay_frida.json (from frida_gameplay_hooks.py --attach).
Writes:
  RE_Tools/analysis/race_correlation_report.json
  RE_Tools/docs/RaceCorrelationReport.md

  python RE_Tools/tools/scripts/analyze_race_correlation.py
  python RE_Tools/tools/scripts/analyze_race_correlation.py path/to/gameplay_frida.json
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_IN = ROOT / "RE_Tools" / "analysis" / "gameplay_frida.json"
OUT_JSON = ROOT / "RE_Tools" / "analysis" / "race_correlation_report.json"
OUT_MD = ROOT / "RE_Tools" / "docs" / "RaceCorrelationReport.md"


def load_ticks(data: dict) -> list[dict]:
    ticks = data.get("race_advance_sim") or []
    if not ticks and isinstance(data.get("events"), list):
        ticks = [e for e in data["events"] if e.get("type") == "race_advance_sim"]
    return ticks


def horse_rows(tick: dict) -> list[dict]:
    snap = tick.get("snapshot") or {}
    horses = snap.get("horses") or []
    ctx_score = snap.get("race_score_450")
    rows = []
    for h in horses:
        rows.append(
            {
                "tick": tick.get("tick"),
                "i": h.get("i"),
                "finish_place": h.get("finish_place"),
                "progress": h.get("progress"),
                "timer": h.get("timer"),
                "speed_f": h.get("speed_f"),
                "speed_220": h.get("speed_220"),
                "horse_score_450_wrong": h.get("score_450"),
                "race_score_450_ctx": ctx_score,
            }
        )
    return rows


def analyze(ticks: list[dict]) -> dict[str, Any]:
    all_horses: list[dict] = []
    for t in ticks:
        all_horses.extend(horse_rows(t))

    finished = [h for h in all_horses if isinstance(h.get("finish_place"), int) and h["finish_place"] >= 0]
    racing = [h for h in all_horses if h.get("finish_place") == -1]

    by_place: dict[int, list[int]] = defaultdict(list)
    for h in finished:
        by_place[h["finish_place"]].append(int(h["progress"] or 0))

    place_means = {str(k): mean(v) if v else 0 for k, v in sorted(by_place.items())}

    # Leader check: lowest finish_place should have highest mean progress
    progress_rank = sorted(
        ((int(p), place_means.get(str(p), 0)) for p in by_place),
        key=lambda x: -x[1],
    )

    ctx_scores = []
    for t in ticks:
        s = (t.get("snapshot") or {}).get("race_score_450")
        if s is not None:
            ctx_scores.append(int(s))

    wrong_horse_scores = [
        h["horse_score_450_wrong"]
        for h in all_horses
        if h.get("horse_score_450_wrong") is not None
    ]
    same_wrong = (
        len(set(wrong_horse_scores)) <= 1 and len(wrong_horse_scores) > 0
        if wrong_horse_scores
        else False
    )

    conclusions = []
    if not ticks:
        conclusions.append("No race_advance_sim ticks — re-run capture with an active race.")
    else:
        conclusions.append(
            f"Captured {len(ticks)} sim tick(s), {len(all_horses)} horse slot reading(s)."
        )
        if ctx_scores:
            conclusions.append(
                f"race_ctx+0x450 (race_score_450): min={min(ctx_scores)} max={max(ctx_scores)} "
                f"(single race power dword per RaceMechanics.md @ 0xE2FBD)."
            )
        else:
            conclusions.append(
                "snapshot.race_score_450 missing - update frida_gameplay_hooks.py and re-capture."
            )
        if same_wrong:
            conclusions.append(
                "Per-horse score_450 in JSON is identical garbage - do NOT read [horse+0x450]; "
                "use [race_ctx+0x450] only (see RaceMechanics.md)."
            )
        if progress_rank:
            conclusions.append(
                "finish_place vs progress (higher progress -> better placement): "
                + ", ".join(f"place={p} avg_progress={prog:.0f}" for p, prog in progress_rank)
            )
            if len(progress_rank) >= 2 and progress_rank[0][1] >= progress_rank[-1][1]:
                conclusions.append(
                    "OK: highest progress aligns with best (lowest) finish_place index."
                )
        if racing:
            conclusions.append(
                f"{len(racing)} slot reading(s) with finish_place=-1 (still racing)."
            )

    return {
        "source": "gameplay_frida.json",
        "tick_count": len(ticks),
        "horse_readings": len(all_horses),
        "race_score_450_ctx_values": ctx_scores,
        "finish_place_mean_progress": place_means,
        "progress_by_place_rank": [{"finish_place": p, "mean_progress": m} for p, m in progress_rank],
        "ticks_sample": ticks[:4],
        "conclusions": conclusions,
    }


def write_md(report: dict) -> str:
    lines = [
        "# Race correlation report (auto-generated)",
        "",
        "**Source:** `RE_Tools/analysis/gameplay_frida.json`",
        "**Script:** `analyze_race_correlation.py`",
        "**RE:** [RaceMechanics.md](RaceMechanics.md) — score @ `[race_ctx+0x450]`, not `[horse+0x450]`.",
        "",
        "## Summary",
        "",
    ]
    for c in report.get("conclusions") or []:
        lines.append(f"- {c}")
    lines.extend(
        [
            "",
            "## finish_place → mean progress",
            "",
            "| finish_place | mean progress |",
            "|--------------|---------------|",
        ]
    )
    for row in report.get("progress_by_place_rank") or []:
        lines.append(f"| {row['finish_place']} | {row['mean_progress']:.0f} |")
    lines.extend(
        [
            "",
            "## race_score_450 (ctx)",
            "",
            f"Values observed: `{report.get('race_score_450_ctx_values', [])}`",
            "",
            "## Re-capture",
            "",
            "```bat",
            "python RE_Tools\\tools\\scripts\\run_frida_race_capture.py",
            "```",
            "",
            "Play a full race, press Enter when done, then re-run this script.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    in_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_IN
    if not in_path.is_file():
        print(f"Missing {in_path}")
        print("Run: python RE_Tools/tools/scripts/run_frida_race_capture.py")
        return 1

    data = json.loads(in_path.read_text(encoding="utf-8"))
    ticks = load_ticks(data)
    report = analyze(ticks)
    report["input_path"] = str(in_path.relative_to(ROOT)).replace("\\", "/")

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    OUT_MD.write_text(write_md(report), encoding="utf-8")

    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")
    for c in report["conclusions"]:
        print(f"  - {c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
