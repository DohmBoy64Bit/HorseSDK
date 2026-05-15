"""
Decode save file footer @ 0x31B19..EOF (global nested saves after inventory).

Source: Horsey.exe @ 0x6E103 (WriteNestedSave global), 0x6E112 (vtable+0xB0)
Output: RE_Tools/analysis/save_footer_layout.json
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
TRACE = ROOT / "RE_Tools" / "analysis" / "save_writer_trace.json"
OUT = ROOT / "RE_Tools" / "analysis" / "save_footer_layout.json"

FOOTER_START = 0x31B19


def u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def decode_string(dump: bytes, off: int) -> dict | None:
    if off + 4 > len(dump):
        return None
    n = u32(dump, off)
    if n > 256:
        return None
    raw = dump[off + 4 : off + 4 + n]
    return {"len": n, "text": raw.decode("utf-8", errors="replace")}


def main() -> int:
    if not DUMP.is_file() or not TRACE.is_file():
        print("Need dump + trace")
        return 1
    dump = DUMP.read_bytes()
    end = len(dump)
    ev = json.loads(TRACE.read_text(encoding="utf-8"))["events"]
    tail_ev = [e for e in ev if e["file_offset"] >= FOOTER_START]

    # Three footer chunks from trace clustering (841 bytes total)
    chunks = [
        {"name": "global_nested_a", "start": 0x31B19, "end": 0x31C48, "caller": "0x6E103"},
        {"name": "global_nested_b_track", "start": 0x31C48, "end": 0x31DED, "caller": "0x6E103/0x6E112"},
        {"name": "global_nested_c_final", "start": 0x31DED, "end": end, "caller": "0x6E103 + Save_Write epilogue fields"},
    ]

    for c in chunks:
        c["size"] = c["end"] - c["start"]
        strings = []
        off = c["start"]
        while off < c["end"] - 4:
            s = decode_string(dump, off)
            if s and s["len"] <= 64:
                strings.append({"file_offset": off, **s})
                off += 4 + s["len"]
            off += 1
        c["std_strings_found"] = strings[:8]
        c["trace_events"] = sum(1 for e in tail_ev if c["start"] <= e["file_offset"] < c["end"])

    report = {
        "file_offset": FOOTER_START,
        "file_end": end,
        "size": end - FOOTER_START,
        "disasm": {
            "inventory_loop": "0x6E0B0..0x6E0FA rsi+=8 while rsi<0x180",
            "global_nested": "0x6E103 call 0x6D440 [rip+0x2AC55D]",
            "global_vcall": "0x6E112 call [rcx+0xB0]",
            "stream_note": "0x6FD90 @ 0x6E11C may finalize heap buffer (not more file bytes)",
        },
        "chunks": chunks,
        "notable_strings": [
            s for c in chunks for s in c.get("std_strings_found", []) if s.get("text")
        ],
    }

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} size={end - FOOTER_START}")
    for c in chunks:
        print(f"  {c['name']}: 0x{c['start']:X}+0x{c['size']:X} events={c['trace_events']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
