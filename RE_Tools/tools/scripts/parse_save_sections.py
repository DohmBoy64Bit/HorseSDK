"""
Parse save_buffer_dump.bin sections after the fixed header (uses layout + heuristics).

Correlates with Save_Write @ 0x6DDF9 (horse u16 vector), 0x6DEA9/6DEB7, 0x6DF30 grid.

If save_writer_trace.json exists (from frida_trace_save_writers.py), anchors offsets from trace.

Output: RE_Tools/analysis/save_sections.json
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
LAYOUT = ROOT / "RE_Tools" / "analysis" / "save_field_layout.json"
TRACE = ROOT / "RE_Tools" / "analysis" / "save_writer_trace.json"
OUT = ROOT / "RE_Tools" / "analysis" / "save_sections.json"

# After 13-row table (0x8C + 13*8)
ROW_TABLE_END = 0x8C + 13 * 8  # 0xF4 — static ctx-only estimate; use trace for file offsets

TRACE_LAYOUT = ROOT / "RE_Tools" / "analysis" / "save_trace_layout.json"


def u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def u16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def read_cstr(b: bytes, o: int, max_len: int = 128) -> str:
    end = b.find(b"\x00", o, o + max_len)
    if end < 0:
        end = o + max_len
    return b[o:end].decode("utf-8", errors="replace")


def find_trace_anchor(trace: dict, writer_rva: str, min_off: int = 0) -> int | None:
    for ev in trace.get("events", []):
        if ev.get("writer_rva") == writer_rva and ev.get("file_offset", 0) >= min_off:
            return ev["file_offset"]
    return None


def parse_u16_horse_vector(b: bytes, start: int) -> dict:
    """Save_Write @ 0x6DDF9: u32 count; each record 4×u16 (8 bytes on disk), src stride 0x24."""
    count = u32(b, start)
    off = start + 4
    records = []
    if count > 10000 or count == 0xFFFFFFFF:
        return {
            "file_offset": start,
            "error": f"implausible count {count}",
            "note": "likely misaligned — use save_writer_trace.json",
        }
    for i in range(count):
        if off + 8 > len(b):
            break
        records.append(
            {
                "index": i,
                "file_offset": off,
                "u16_x4": [u16(b, off), u16(b, off + 2), u16(b, off + 4), u16(b, off + 6)],
                "hex": b[off : off + 8].hex(),
            }
        )
        off += 8
    return {
        "name": "horse_u16_vector",
        "insn": "0x6DDF9 / loop 0x6DE30",
        "ctx": "rdi+0x280 .. rdi+0x288 (stride 0x24 in memory)",
        "file_offset": start,
        "count": count,
        "disk_record_bytes": 8,
        "memory_record_bytes": 0x24,
        "records": records,
        "end_offset": off,
    }


def parse_std_string(b: bytes, off: int) -> tuple[dict, int]:
    """WriteStdString @ 0x6FFF0: u32 len then bytes (no NUL required on disk)."""
    if off + 4 > len(b):
        return {"error": "truncated"}, off
    n = u32(b, off)
    off += 4
    if n > 5000:
        return {"error": f"bad len {n}", "file_offset": off - 4}, off
    raw = b[off : off + n]
    off += n
    text = raw.split(b"\x00")[0].decode("utf-8", errors="replace")
    return {"file_offset": off - 4 - n, "len": n, "text": text, "hex": raw[:32].hex()}, off


def parse_inventory_strings(b: bytes, start: int, max_items: int = 200) -> dict:
    items = []
    off = start
    for _ in range(max_items):
        if off + 4 > len(b):
            break
        n = u32(b, off)
        if n == 0 or n > 200:
            break
        if off + 4 + n > len(b):
            break
        entry, off = parse_std_string(b, off)
        if "error" in entry:
            break
        items.append(entry)
        if off >= len(b) - 16:
            break
    return {
        "name": "inventory_std_strings",
        "insn": "0x6DF30 / 0x1167B0",
        "ctx": "rdi+0x270 grid",
        "file_offset": start,
        "items": items,
        "end_offset": off,
    }


def main() -> int:
    if not DUMP.is_file():
        print(f"Missing {DUMP}")
        return 1
    b = DUMP.read_bytes()
    trace = json.loads(TRACE.read_text(encoding="utf-8")) if TRACE.is_file() else {}

    trace_layout = {}
    if TRACE_LAYOUT.is_file():
        trace_layout = json.loads(TRACE_LAYOUT.read_text(encoding="utf-8"))
    vec_info = trace_layout.get("horse_u16_vector_rdi_280", {})
    vec_start = vec_info.get("file_offset")

    def horse_vector_from_events(evlist: list) -> int | None:
        for i, e in enumerate(evlist):
            if e.get("writer_rva") != "0x6FED0":
                continue
            if i + 1 < len(evlist) and evlist[i + 1].get("writer_rva") == "0x6FE50":
                return e["file_offset"]
        return None

    if vec_start is None and trace.get("events"):
        vec_start = horse_vector_from_events(trace["events"])
    if vec_start is None:
        vec_start = ROW_TABLE_END
    # Known tail fields from disasm @ 0x6DEA9 / 0x6DEB7
    f278_off = find_trace_anchor(trace, "0x6FE10", vec_start) or (vec_start + 4)
    # If trace has multiple WriteU32 after vector, pick by order
    trace_events = [e for e in trace.get("events", []) if e.get("file_offset", 0) >= ROW_TABLE_END]
    if trace_events:
        vec_ev = next((e for e in trace_events if e.get("writer_rva") == "0x6FED0"), None)
        if vec_ev:
            vec_start = vec_ev["file_offset"]
            count = vec_ev.get("value_u32", u32(b, vec_start))
        else:
            count = u32(b, vec_start)
    else:
        count = u32(b, vec_start)

    trace_count = vec_info.get("count")
    if trace_count is not None:
        off = vec_start + 4
        records = []
        for i in range(min(int(trace_count), 10000)):
            if off + 8 > len(b):
                break
            records.append(
                {
                    "index": i,
                    "file_offset": off,
                    "u16_x4": [u16(b, off), u16(b, off + 2), u16(b, off + 4), u16(b, off + 6)],
                    "hex": b[off : off + 8].hex(),
                }
            )
            off += 8
        vec = {
            "name": "horse_u16_vector",
            "insn": "0x6DDF9 / 0x6DE30",
            "ctx": "rdi+0x280 .. rdi+0x288",
            "file_offset": vec_start,
            "count": trace_count,
            "count_source": "save_trace_layout.json",
            "disk_record_bytes": 8,
            "records": records,
            "end_offset": off,
        }
    else:
        vec = parse_u16_horse_vector(b, vec_start)
        if "error" in vec and u32(b, vec_start) == 0xFFFFFFFF:
            vec = {**vec, "count": 0, "records": [], "end_offset": vec_start + 4}

    tail_start = vec.get("end_offset", vec_start + 4)
    field_278 = {"file_offset": tail_start, "u32": u32(b, tail_start), "ctx": "rdi+0x278", "insn": "0x6DEA9"}
    field_27c = {
        "file_offset": tail_start + 4,
        "u32": u32(b, tail_start + 4),
        "ctx": "rdi+0x27C",
        "insn": "0x6DEB7",
    }
    inv_start = tail_start + 8
    # Align to first plausible std string (u32 len < 128)
    for probe in range(tail_start + 4, min(tail_start + 32, len(b) - 8)):
        n = u32(b, probe)
        if 1 <= n <= 64 and b[probe + 4 + n - 1 : probe + 4 + n] == b"\x00" or all(
            32 <= c < 127 for c in b[probe + 4 : probe + 4 + min(n, 4)]
        ):
            inv_start = probe
            break
    inventory = parse_inventory_strings(b, inv_start)

    report = {
        "dump": str(DUMP),
        "dump_size": len(b),
        "row_table_end": hex(ROW_TABLE_END),
        "trace_used": TRACE.is_file(),
        "horse_u16_vector": vec,
        "fields_278_27c": [field_278, field_27c],
        "inventory_strings": inventory,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"  vector @ 0x{vec_start:X} count={vec.get('count')} end=0x{vec.get('end_offset', 0):X}")
    print(f"  inventory strings: {len(inventory.get('items', []))} @ 0x{inv_start:X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
