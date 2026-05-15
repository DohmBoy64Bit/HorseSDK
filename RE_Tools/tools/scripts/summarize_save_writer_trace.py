"""Summarize save_writer_trace.json -> save_writer_trace_summary.json"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TRACE = ROOT / "RE_Tools" / "analysis" / "save_writer_trace.json"
OUT = ROOT / "RE_Tools" / "analysis" / "save_writer_trace_summary.json"


def main() -> int:
    data = json.loads(TRACE.read_text(encoding="utf-8"))
    ev = data.get("events", [])
    by_writer = Counter(e["writer"] for e in ev)
    header = [e for e in ev if e["file_offset"] < 0x100]
    tail = [e for e in ev if e["file_offset"] >= 0xF0 and e["file_offset"] < 0x200]
    fed0 = [e for e in ev if e.get("writer_rva") == "0x6FED0"]
    report = {
        "event_count": len(ev),
        "save_completions": data.get("save_completions"),
        "by_writer": dict(by_writer),
        "header_writes": header[:40],
        "region_F0_200": tail[:40],
        "write_u32_count_calls": [
            {"file_offset": e["file_offset"], "value_u32": e.get("value_u32")}
            for e in fed0[:20]
        ],
        "last_writes": ev[-15:],
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} ({len(ev)} events)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
