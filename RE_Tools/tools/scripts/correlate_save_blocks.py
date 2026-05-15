"""
Merge save_block_trace.json with save_buffer_dump.bin / save_grid_layout.json.

Output:
  RE_Tools/analysis/save_block_correlation.json
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BLOCKS = ROOT / "RE_Tools" / "analysis" / "save_block_trace.json"
DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
GRID = ROOT / "RE_Tools" / "analysis" / "save_grid_layout.json"
OUT = ROOT / "RE_Tools" / "analysis" / "save_block_correlation.json"


def decode_std_string(dump: bytes, off: int) -> dict | None:
    if off + 4 > len(dump):
        return None
    n = struct.unpack_from("<I", dump, off)[0]
    if n == 0 or n > 256:
        return None
    if off + 4 + n > len(dump):
        return None
    raw = dump[off + 4 : off + 4 + n]
    text = raw.split(b"\x00")[0].decode("utf-8", errors="replace")
    return {"len": n, "text": text, "hex": raw[:32].hex()}


def main() -> int:
    if not BLOCKS.is_file() or not json.loads(BLOCKS.read_text()).get("events"):
        print("No Frida block events — falling back to trace cluster correlator")
        import subprocess
        import sys

        script = ROOT / "RE_Tools" / "tools" / "scripts" / "correlate_save_blocks_from_trace.py"
        return subprocess.call([sys.executable, str(script)])

    blocks = json.loads(BLOCKS.read_text(encoding="utf-8"))

    ev = blocks.get("events") or []
    dump = DUMP.read_bytes() if DUMP.is_file() else b""
    grid = json.loads(GRID.read_text(encoding="utf-8")) if GRID.is_file() else {}

    nested = [e for e in ev if e.get("kind") == "block" and e.get("block") == "WriteNestedSave"]
    items = [e for e in ev if e.get("kind") == "block" and e.get("block") == "WriteNestedItem"]
    calls = [e for e in ev if e.get("kind") == "nested_call"]
    grid_ev = [e for e in ev if e.get("kind") == "grid_dims"]
    pairs = [e for e in ev if e.get("kind") == "pair_count"]

    enriched = []
    for i, b in enumerate(nested):
        off = b.get("file_offset", -1)
        size = b.get("bytes", 0)
        entry = {
            "index": i,
            "file_offset": off,
            "bytes": size,
            "after_offset": b.get("after_offset"),
            "rva": b.get("rva"),
            "obj": b.get("extra", {}).get("obj"),
        }
        if dump and 0 <= off < len(dump):
            entry["header_hex"] = dump[off : min(off + 32, len(dump))].hex()
            s = decode_std_string(dump, off)
            if s:
                entry["first_std_string"] = s
        # match nested_call by nearest offset before block
        prior = [c for c in calls if c.get("file_offset", 0) <= off]
        if prior:
            entry["caller"] = prior[-1].get("label")
            entry["caller_rva"] = prior[-1].get("rva")
        enriched.append(entry)

    item_summary = {
        "count": len(items),
        "total_bytes": sum(x.get("bytes", 0) for x in items if x.get("bytes", 0) > 0),
        "samples": items[:15],
    }

    report = {
        "sources": {
            "blocks": str(BLOCKS),
            "dump": str(DUMP) if DUMP.is_file() else None,
            "dump_size": len(dump),
            "save_completions": blocks.get("save_completions"),
        },
        "grid": grid_ev,
        "pair_count_writes": pairs,
        "grid_layout_milestones": grid.get("milestones"),
        "nested_save_blocks": enriched,
        "nested_items": item_summary,
        "nested_calls": calls,
    }

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"  nested_saves={len(enriched)} nested_items={len(items)} grid_events={len(grid_ev)}")
    for e in enriched[:8]:
        name = (e.get("first_std_string") or {}).get("text", "?")
        print(f"    0x{e['file_offset']:X} +{e['bytes']}B caller={e.get('caller','?')} name={name!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
