"""
Infer nested-save file regions from compact save_writer_trace.json + dump.

When Frida block hooks miss (no save during capture), this matches the
0x6D440 on-disk layout using trace clusters after the grid U8 gap.

Source (Horsey.exe):
  0x6E043 pair count + 8*N bytes
  0x6E0A6 main WriteNestedSave (ctx rdi) — large first blob
  0x6E0D6 inventory WriteNestedSave — ~352 byte repeats

Output:
  RE_Tools/analysis/save_block_correlation.json
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TRACE = ROOT / "RE_Tools" / "analysis" / "save_writer_trace.json"
DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
GRID = ROOT / "RE_Tools" / "analysis" / "save_grid_layout.json"
OUT = ROOT / "RE_Tools" / "analysis" / "save_block_correlation.json"

TAIL_DEFAULT = 0xDEA7  # first traced byte after grid_main (compact run)
INVENTORY_SPAN = 352  # 0x160 — repeating 0x6E0D6 nested item


def u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def decode_std_string(dump: bytes, off: int) -> dict | None:
    if off + 4 > len(dump):
        return None
    n = u32(dump, off)
    if n > 512:
        return None
    if off + 4 + n > len(dump):
        return None
    raw = dump[off + 4 : off + 4 + n]
    text = raw.split(b"\x00")[0].decode("utf-8", errors="replace")
    return {"len": n, "text": text, "hex": raw[:24].hex()}


def tail_start(grid: dict | None, trace_final: int) -> int:
    if grid and grid.get("milestones"):
        return grid["milestones"].get("first_compact_trace_offset") or TAIL_DEFAULT
    return TAIL_DEFAULT


def writers_in_range(ev: list, start: int, end: int) -> list[dict]:
    return [e for e in ev if start <= e["file_offset"] < end]


def summarize_block(
    dump: bytes,
    ev: list,
    start: int,
    end: int,
    label: str,
    caller_rva: str,
) -> dict:
    sub = writers_in_range(ev, start, end)
    wcounts: dict[str, int] = {}
    for e in sub:
        wcounts[e["writer"]] = wcounts.get(e["writer"], 0) + 1
    entry: dict = {
        "label": label,
        "caller_rva": caller_rva,
        "file_offset": start,
        "file_end": end,
        "bytes": end - start,
        "trace_events": len(sub),
        "writers": wcounts,
    }
    s = decode_std_string(dump, start)
    if s:
        entry["first_std_string"] = s
    return entry


def main() -> int:
    if not TRACE.is_file():
        print(f"Missing {TRACE}")
        return 1

    trace = json.loads(TRACE.read_text(encoding="utf-8"))
    ev = trace["events"]
    dump = DUMP.read_bytes() if DUMP.is_file() else b""
    grid = json.loads(GRID.read_text(encoding="utf-8")) if GRID.is_file() else None

    tail = tail_start(grid, trace.get("save_completions", [{}])[-1].get("final_size", 0))
    if not dump or tail + 4 > len(dump):
        print("Need aligned save_buffer_dump.bin")
        return 1

    pair_count = u32(dump, tail)
    pairs_end = tail + 4 + pair_count * 8
    pair_bytes = dump[tail:pairs_end]

    strings = [e for e in ev if e.get("writer") == "WriteStdString" and e["file_offset"] >= pairs_end]

    blocks: list[dict] = []
    blocks.append(
        {
            "label": "pair_vector",
            "caller_rva": "0x6E043",
            "file_offset": tail,
            "file_end": pairs_end,
            "bytes": pairs_end - tail,
            "pair_count": pair_count,
            "hex": pair_bytes.hex(),
        }
    )

    if strings:
        # Main nested @ 0x6E0A6 — first std string block until second string or inventory cadence
        s0 = strings[0]["file_offset"]
        if len(strings) > 1:
            s1 = strings[1]["file_offset"]
            main_end = s1 if (s1 - s0) > INVENTORY_SPAN else s0 + 1134
        else:
            main_end = len(dump)
        blocks.append(
            summarize_block(dump, ev, s0, main_end, "WriteNestedSave_main", "0x6E0A6")
        )

        # Inventory nested @ 0x6E0D6 — 352-byte cadence
        for i in range(1, len(strings)):
            start = strings[i]["file_offset"]
            if i + 1 < len(strings):
                end = strings[i + 1]["file_offset"]
            else:
                end = max(e["file_offset"] + e.get("size", 4) for e in ev)
            if end - start < 16:
                continue
            if end - start > INVENTORY_SPAN * 3 and i > 1:
                # oversized — cap to typical inventory span
                end = start + INVENTORY_SPAN
            blocks.append(
                summarize_block(
                    dump,
                    ev,
                    start,
                    end,
                    "WriteNestedSave_inventory",
                    "0x6E0D6",
                )
            )

    inv = [b for b in blocks if b["label"] == "WriteNestedSave_inventory"]
    report = {
        "method": "trace_cluster",
        "sources": {
            "trace": str(TRACE),
            "dump": str(DUMP),
            "dump_size": len(dump),
            "grid_layout": str(GRID) if GRID.is_file() else None,
        },
        "milestones": {
            "tail_traced_start": tail,
            "pairs_end": pairs_end,
            "grid_main_end": tail,
        },
        "pair_section": blocks[0] if blocks else None,
        "nested_main": blocks[1] if len(blocks) > 1 else None,
        "nested_inventory": {
            "count": len(inv),
            "typical_bytes": INVENTORY_SPAN,
            "total_bytes": sum(b["bytes"] for b in inv),
            "samples": inv[:5],
        },
        "all_blocks": blocks,
    }

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"  tail=0x{tail:X} pairs={pair_count} nested_main=1 inventory={len(inv)}")
    if len(blocks) > 1:
        m = blocks[1]
        name = (m.get("first_std_string") or {}).get("text", "?")
        print(f"  main nested @ 0x{m['file_offset']:X} +{m['bytes']}B name={name!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
