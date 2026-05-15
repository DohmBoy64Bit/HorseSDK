"""
Decode SaveContext block @ file 0x959..0xA3D from save_writer_trace + dump.

Verified: Horsey.exe Save_Write @ 0x6DCCA..0x6DDC9, SaveContext.h
Output: RE_Tools/analysis/save_context_block.json
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
TRACE = ROOT / "RE_Tools" / "analysis" / "save_writer_trace.json"
OUT = ROOT / "RE_Tools" / "analysis" / "save_context_block.json"

START = 0x959
END = 0xA3D


def u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def decode_event(dump: bytes, e: dict) -> dict:
    fo = e["file_offset"]
    sz = e.get("size", 4)
    raw = dump[fo : fo + sz]
    row = {
        "file_offset": fo,
        "size": sz,
        "writer": e["writer"],
        "writer_rva": e.get("writer_rva"),
        "source": e.get("source"),
        "hex": raw[:16].hex(),
    }
    if e["writer"] == "WriteF32" and sz == 4:
        row["value"] = struct.unpack_from("<f", raw, 0)[0]
    elif sz == 4:
        row["value_u32"] = u32(raw, 0)
        src = row.get("source") or ""
        if src.startswith("ctx[rdi+0x308]"):
            row["text"] = struct.pack("<I", row["value_u32"] & 0xFFFFFFFF).decode(
                "ascii", errors="replace"
            )
    elif sz == 8 and e["writer"] == "WriteVec2F32":
        row["value"] = struct.unpack_from("<ff", raw, 0)
    return row


def main() -> int:
    if not DUMP.is_file() or not TRACE.is_file():
        print("Need dump + trace")
        return 1
    dump = DUMP.read_bytes()
    ev = json.loads(TRACE.read_text(encoding="utf-8"))["events"]
    sub = sorted([e for e in ev if START <= e["file_offset"] < END], key=lambda x: x["file_offset"])
    fields = [decode_event(dump, e) for e in sub]
    traced = sum(f["size"] for f in fields)

    report = {
        "file_offset": START,
        "file_offset_decimal": START,  # 0x959 = 2393
        "file_end": END,
        "size": END - START,
        "disasm": "Save_Write @ 0x6DCCA..0x6DDC9 (rdi = SaveContext)",
        "fields": fields,
        "coverage": {
            "traced_bytes": traced,
            "gap_bytes": (END - START) - traced,
            "pct": round(100 * traced / (END - START), 1),
        },
        "semantics": {
            "0x114": "float (1.0 in sample)",
            "0x254": "timestamp-like u32",
            "0x268": "u32 21 — horse/registry related",
            "0x308": "active horse name fourcc (Dale)",
            "0x440": "u32 0x100 flags",
            "0x31C": "6× SaveSlot6 (12 B each on disk)",
            "0x2CC": "13× SaveRow13 (8 B each on disk)",
            "0x39C": "vec2 camera/world",
        },
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    active = next((f.get("text") for f in fields if f.get("text")), None)
    if not active:
        # fourcc @ ctx+0x308 in dump (file 0x975 in sample)
        fo = START + (0x975 - START) if START <= 0x975 < END else START + 0x1C
        if fo + 4 <= END:
            active = struct.pack("<I", u32(dump, fo) & 0xFFFFFFFF).decode("ascii", errors="replace")
    print(f"Wrote {OUT} fields={len(fields)} active_horse={active!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
