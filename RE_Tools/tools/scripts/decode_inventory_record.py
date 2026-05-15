"""
Decode one 352-byte inventory nested save (WriteNestedSave @ 0x6D440 / 0x6E0D6).

Verified against:
  Horsey.exe Capstone @ 0x6D440, 0x6EC40
  save_buffer_dump.bin + save_writer_trace.json (block @ 0xE339)

Output:
  RE_Tools/analysis/save_inventory_record_layout.json
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
TRACE = ROOT / "RE_Tools" / "analysis" / "save_writer_trace.json"
OUT = ROOT / "RE_Tools" / "analysis" / "save_inventory_record_layout.json"

RECORD_SIZE = 352
SAMPLE_OFF = 0xE339  # first inventory block (correlate_save_blocks_from_trace.py)


def u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def u16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def u64(b: bytes, o: int) -> int:
    return struct.unpack_from("<Q", b, o)[0]


def f32(b: bytes, o: int) -> float:
    return struct.unpack_from("<f", b, o)[0]


def vec2(b: bytes, o: int) -> tuple[float, float]:
    return struct.unpack_from("<ff", b, o)


def trace_slice(ev: list, start: int, end: int) -> list[dict]:
    out = []
    for e in ev:
        if not (start <= e["file_offset"] < end):
            continue
        fo = e["file_offset"]
        sz = e.get("size", 4)
        if e["writer"] == "WriteStdString":
            sz = 4 + u32(DUMP.read_bytes(), fo) if DUMP.is_file() else 4
        row = {
            "file_offset": fo,
            "rel": fo - start,
            "writer": e["writer"],
            "size": sz,
            "hex": (e.get("hex") or "")[:24],
        }
        if e.get("value_u32") is not None:
            row["value_u32"] = e["value_u32"]
        out.append(row)
    return out


def decode_block(dump: bytes, start: int, ev: list) -> dict:
    chunk = dump[start : start + RECORD_SIZE]
    end = start + RECORD_SIZE

    # --- 0x6D440 fixed header (when counts are 0 / empty name) ---
    name_len = u32(chunk, 0)
    name = chunk[4 : 4 + name_len].decode("utf-8", errors="replace") if name_len else ""

    header = {
        "file_offset": start,
        "size": 0x18,
        "insn": "0x6D440",
        "fields": [
            {
                "rel": 0x00,
                "size": 4 + name_len,
                "mem": "object+0x18",
                "writer": "WriteStdString",
                "value": {"len": name_len, "text": name},
            },
            {
                "rel": 0x04,
                "size": 4,
                "mem": "(end+0x138)-(beg+0x130)>>3",
                "writer": "WriteU32",
                "value": u32(chunk, 4),
                "note": "pointer-vector count; 0 => skip 0x6EC40",
            },
            {
                "rel": 0x08,
                "size": 4,
                "mem": "merged run index",
                "writer": "WriteU32",
                "value": u32(chunk, 8),
                "insn": "0x6D4F1",
            },
            {
                "rel": 0x0C,
                "size": 4,
                "mem": "(end+0xC0)-(beg+0xB8)>>3",
                "writer": "WriteU32",
                "value": u32(chunk, 0x0C),
                "insn": "0x6D508",
                "note": "secondary vector count; each entry u32 + vcall +0x48",
            },
            {
                "rel": 0x10,
                "size": 8,
                "mem": "object+0x0C",
                "writer": "WriteVec2F32",
                "value": vec2(chunk, 0x10),
                "insn": "0x6D574",
            },
        ],
    }

    # Opaque middle: compact trace has no WriteU8; sample is mostly packed bytes
    opaque_start = 0x18
    opaque_end = 0x141  # before footer WriteU64 in trace
    opaque = chunk[opaque_start:opaque_end]

    # Traced sub-header inside opaque (matches tail of 0x6EC40 when item exists)
    traced_header_end = 0x51
    traced_sub = {
        "rel": 0x18,
        "size": traced_header_end - 0x18,
        "insn": "0x6EC40 partial / 0x6D2A0 @ +0x150",
        "note": "Present in sample even when ptr-vector count=0; likely 6D2A0 sub-serializer",
        "fields": [
            {"rel": 0x1A, "size": 2, "writer": "WriteU16", "mem": "rbp+0x220", "value": u16(chunk, 0x1A)},
            {"rel": 0x1C, "size": 2, "writer": "WriteU16", "value": u16(chunk, 0x1C)},
            {"rel": 0x1E, "size": 2, "writer": "WriteU16", "value": u16(chunk, 0x1E)},
            {"rel": 0x20, "size": 4, "writer": "WriteU32", "mem": "rbp+0x1F8", "value": u32(chunk, 0x20)},
            {"rel": 0x24, "size": 4, "writer": "WriteU32FromU8", "value": u32(chunk, 0x24)},
            {"rel": 0x28, "size": 4, "writer": "WriteU32", "value": u32(chunk, 0x28)},
            {"rel": 0x2F, "size": 2, "writer": "WriteU16", "value": u16(chunk, 0x2F)},
            {"rel": 0x31, "size": 4, "writer": "WriteU32", "value": u32(chunk, 0x31)},
            {"rel": 0x35, "size": 4, "writer": "WriteU32", "value": u32(chunk, 0x35)},
            {"rel": 0x39, "size": 8, "writer": "WriteVec2F32", "mem": "rbp+0x1D4", "value": vec2(chunk, 0x39)},
            {"rel": 0x41, "size": 4, "writer": "WriteF32", "mem": "rbp+0xC0", "value": f32(chunk, 0x41)},
            {"rel": 0x45, "size": 4, "writer": "WriteF32", "value": f32(chunk, 0x45)},
            {"rel": 0x49, "size": 4, "writer": "WriteF32", "value": f32(chunk, 0x49)},
            {"rel": 0x4D, "size": 4, "writer": "WriteF32", "value": f32(chunk, 0x4D)},
        ],
    }

    packed_blob = {
        "rel": 0x51,
        "size": opaque_end - 0x51,
        "writer": "WriteU8 x N (compact trace omitted)",
        "insn": "vtable+0x48 or 0x6EC40 gene bytes @ 0x6ED86+",
        "hex_prefix": opaque[0x39 : 0x39 + 48].hex(),
        "byte_histogram_top": _top_bytes(opaque[0x39 :]),
    }

    footer = {
        "rel": 0x141,
        "size": RECORD_SIZE - 0x141,
        "insn": "0x6D440 tail / 0x6EC40",
        "fields": [
            {"rel": 0x141, "size": 8, "writer": "WriteU64", "mem": "rbp+0x2A8", "value": u64(chunk, 0x141)},
            {"rel": 0x149, "size": 4, "writer": "WriteU32", "value": u32(chunk, 0x149)},
            {"rel": 0x14D, "size": 2, "writer": "WriteU16", "value": u16(chunk, 0x14D)},
            {
                "rel": 0x14F,
                "size": 9,
                "writer": "(gap)",
                "hex": chunk[0x14F:0x158].hex(),
            },
            {"rel": 0x158, "size": 8, "writer": "WriteVec2F32", "value": vec2(chunk, 0x158)},
        ],
    }

    ec40_mem = {
        "note": "In-memory item object passed to 0x6EC40 (when ptr-vector count >= 1)",
        "insn": "0x6EC40",
        "fields_write_order": [
            {"mem": "+0x2A8", "writer": "WriteU64"},
            {"mem": "+0x1F8", "writer": "WriteU32"},
            {"mem": "+0x220", "writer": "WriteU16"},
            {"mem": "+0x1C", "writer": "WriteU8"},
            {"mem": "+0x1FC", "writer": "WriteU8"},
            {"mem": "+0x21C", "writer": "WriteU8"},
            {"mem": "+0x284", "writer": "WriteU8"},
            {"mem": "+0x214", "writer": "WriteU8"},
            {"mem": "+0x234", "writer": "WriteU8"},
            {"mem": "+0x210", "writer": "WriteU8"},
            {"mem": "+0x1CC", "writer": "WriteU8"},
            {"mem": "+0x206..+0x22", "writer": "WriteU8 bitfield pack"},
            {"mem": "+0x1A", "writer": "WriteU8 optional 0x3F prefix"},
            {"mem": "+0x1D4", "writer": "WriteVec2F32"},
            {"mem": "+0x168", "writer": "WriteStdString"},
            {"mem": "+0xC0", "writer": "WriteF32 via 0x6FF80"},
            {"mem": "+0xCC..+0x118", "writer": "WriteU32 gene slots if != -1"},
            {"mem": "+0x40", "writer": "WriteU32 x3 + WriteVec2F32"},
        ],
    }

    trace = json.loads(TRACE.read_text(encoding="utf-8"))["events"] if TRACE.is_file() else []

    return {
        "record_size": RECORD_SIZE,
        "sample_file_offset": start,
        "disasm": {
            "outer": "0x6D440 WriteNestedSave",
            "inventory_caller": "0x6E0D6",
            "item": "0x6EC40 WriteNestedItem",
        },
        "sections": [header, traced_sub, packed_blob, footer],
        "ec40_in_memory": ec40_mem,
        "trace_events": trace_slice(trace, start, end) if trace else [],
    }


def _top_bytes(b: bytes, n: int = 6) -> list[dict]:
    from collections import Counter

    return [{"byte": f"0x{k:02X}", "count": v} for k, v in Counter(b).most_common(n)]


def main() -> int:
    if not DUMP.is_file():
        print(f"Missing {DUMP}")
        return 1
    dump = DUMP.read_bytes()
    ev = json.loads(TRACE.read_text(encoding="utf-8"))["events"] if TRACE.is_file() else []
    report = decode_block(dump, SAMPLE_OFF, ev)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"  sample @ 0x{SAMPLE_OFF:X} name_len={report['sections'][0]['fields'][0]['value']['len']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
