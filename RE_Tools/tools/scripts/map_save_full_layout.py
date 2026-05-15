"""
Build complete save file section map from aligned dump + compact writer trace.

Requires:
  save_buffer_dump.bin
  save_writer_trace.json  (frida_trace_save_writers.py --compact)

Output:
  RE_Tools/analysis/save_full_layout.json
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
TRACE = ROOT / "RE_Tools" / "analysis" / "save_writer_trace.json"
GRID = ROOT / "RE_Tools" / "analysis" / "save_grid_layout.json"
BLOCKS = ROOT / "RE_Tools" / "analysis" / "save_block_trace.json"
CORR = ROOT / "RE_Tools" / "analysis" / "save_block_correlation.json"
OUT = ROOT / "RE_Tools" / "analysis" / "save_full_layout.json"

# Insn RVAs for section boundaries (Horsey.exe)
RVA_CTX_FIRST_U32 = 0x6DCCA  # [rdi+0x254] — first ctx field after C3100
RVA_CTX_F32_114 = 0x6DCEB
RVA_CTX_NAME_308 = 0x6DD09
RVA_HORSE_VEC_COUNT = 0x6DDF9
RVA_FIELD_278 = 0x6DEA9
RVA_FIELD_27C = 0x6DEB7
RVA_GRID_LOOP = 0x6DF30
RVA_PAIR_COUNT = 0x6E043
RVA_NESTED_SAVE = 0x6D440


def u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def le_count(hex_str: str | None) -> int | None:
    if not hex_str or len(hex_str) < 8:
        return None
    return struct.unpack("<I", bytes.fromhex(hex_str[:8]))[0]


def decode_std_string_at(b: bytes, off: int) -> dict | None:
    if off + 4 > len(b):
        return None
    n = u32(b, off)
    if n == 0 or n > 512:
        return None
    if off + 4 + n > len(b):
        return None
    raw = b[off + 4 : off + 4 + n]
    return {
        "file_offset": off,
        "len": n,
        "text": raw.split(b"\x00")[0].decode("utf-8", errors="replace"),
        "hex": raw[:48].hex(),
    }


def horse_vector_event(ev: list) -> dict | None:
    for i, e in enumerate(ev):
        if e.get("writer_rva") != "0x6FED0":
            continue
        if i + 1 < len(ev) and ev[i + 1].get("writer_rva") == "0x6FE50":
            return e
    return None


def first_fed0_after(ev: list, min_off: int) -> dict | None:
    for e in ev:
        if e.get("writer_rva") == "0x6FED0" and e["file_offset"] >= min_off:
            if e is horse_vector_event(ev):
                return e
    return None


def global_table_end(ev: list, ctx_start: int) -> int:
    """Last event before ctx block file offset."""
    end = 0x14
    for e in ev:
        if e["file_offset"] < ctx_start:
            end = max(end, e["file_offset"] + max(e.get("size", 4), 0))
    return end


def ctx_header_fields(ev: list, ctx_start: int, vec_start: int) -> list[dict]:
    """Map known ctx writes between ctx_start and horse vector (from static insn order)."""
    # Match by searching dump-aligned progression in trace
    region = [e for e in ev if ctx_start <= e["file_offset"] < vec_start]
    # Group by offset
    by_off: dict[int, list] = {}
    for e in region:
        by_off.setdefault(e["file_offset"], []).append(e)
    rows = []
    for off in sorted(by_off):
        writers = by_off[off]
        rows.append(
            {
                "file_offset": off,
                "writers": [{"writer": w["writer"], "rva": w.get("writer_rva"), "hex": w.get("hex")} for w in writers],
            }
        )
    return rows


def std_string_clusters(ev: list, min_off: int, max_off: int) -> list[dict]:
    out = []
    for e in ev:
        if e.get("writer") != "WriteStdString":
            continue
        if not (min_off <= e["file_offset"] < max_off):
            continue
        out.append(
            {
                "file_offset": e["file_offset"],
                "after_offset": e.get("after_offset"),
                "hex_prefix": (e.get("hex") or "")[:16],
            }
        )
    return out


def find_ctx_block_start(ev: list, dump: bytes) -> int:
    """
    C3100 ends before first ctx serialization @ 0x6DCCA.
    Heuristic: first WriteF32 in trace (ctx+0x114 @ 0x6DCEB) OR first u32 fourcc name.
    """
    for e in ev:
        if e.get("writer") == "WriteF32":
            return e["file_offset"]
    # Dale fourcc in dump
    if dump:
        idx = dump.find(b"Dale")
        if idx >= 0x18:
            # walk back to start of ctx u32 block (~0x04 is C3100, ctx name ~0x18)
            return 0x04  # fallback: after minimal header if no f32 in trace
    for e in ev:
        if e.get("writer") == "WriteU32" and e["file_offset"] > 0x100:
            return e["file_offset"]
    return 0x14


def global_names_from_trace(ev: list, end_off: int) -> list[dict]:
    """Use WriteStdString trace events in C3100 region (file 0x14 .. ctx_start)."""
    items = []
    for e in ev:
        if e.get("writer") != "WriteStdString":
            continue
        o = e["file_offset"]
        if o < 0x14 or o >= end_off:
            continue
        items.append(
            {
                "file_offset": o,
                "after_offset": e.get("after_offset"),
                "hex_prefix": e.get("hex"),
            }
        )
    return items


def _summarize_block_trace(block_trace: dict | None) -> dict | None:
    if not block_trace:
        return None
    ev = block_trace.get("events") or []
    grid = [e for e in ev if e.get("kind") == "grid_dims"]
    pairs = [e for e in ev if e.get("kind") == "pair_count"]
    nested = [e for e in ev if e.get("block") == "WriteNestedSave"]
    items = [e for e in ev if e.get("block") == "WriteNestedItem"]
    return {
        "event_count": len(ev),
        "grid_dims": grid[:3],
        "pair_count_writes": pairs[:3],
        "nested_save_blocks": nested[:20],
        "nested_item_blocks": len(items),
        "nested_item_bytes_total": sum(x.get("bytes", 0) for x in items if x.get("bytes", 0) > 0),
    }


def scan_std_strings_in_dump(dump: bytes, start: int, end: int, min_len: int = 2) -> list[dict]:
    """Find u32-len + ASCII runs (inventory / nested blobs)."""
    out = []
    off = start
    while off + 8 < end:
        n = u32(dump, off)
        if not (min_len <= n <= 120):
            off += 1
            continue
        if off + 4 + n > len(dump):
            off += 1
            continue
        raw = dump[off + 4 : off + 4 + n]
        if not raw:
            off += 1
            continue
        text = raw.split(b"\x00")[0].decode("utf-8", errors="replace")
        if len(text) < min_len or not all(c.isprintable() or c in "\r\n\t" for c in text):
            off += 1
            continue
        out.append(
            {
                "file_offset": off,
                "len": n,
                "text": text,
                "hex": raw[:40].hex(),
            }
        )
        off += 4 + n
    return out


def main() -> int:
    if not TRACE.is_file() or not DUMP.is_file():
        print("Need save_writer_trace.json and save_buffer_dump.bin")
        return 1

    trace = json.loads(TRACE.read_text(encoding="utf-8"))
    ev = trace["events"]
    dump = DUMP.read_bytes()
    dump_size = len(dump)
    trace_final = trace.get("save_completions", [{}])[-1].get("final_size")

    # --- header 0x00-0x13 ---
    version_ev = next(e for e in ev if e["file_offset"] == 0)
    global_count_ev = next((e for e in ev if e["file_offset"] == 16), None)
    global_count = le_count(global_count_ev.get("hex") if global_count_ev else None) or 0

    vec_ev = horse_vector_event(ev)
    vec_start = vec_ev["file_offset"] if vec_ev else 0
    vec_count = le_count(vec_ev.get("hex") if vec_ev else None) or 0

    ctx_start = find_ctx_block_start(ev, dump)
    if global_count_ev and ctx_start < global_count_ev["after_offset"] or 0:
        # ctx starts after global table: find first WriteF32 after last string cluster before vec
        f32s = [e for e in ev if e.get("writer") == "WriteF32"]
        if f32s:
            ctx_start = f32s[0]["file_offset"]

    # ctx block begins at first WriteF32 @ 0x6DCEB (ctx+0x114); C3100 may extend to ~0x950+
    f32_ctx = next((e for e in ev if e.get("writer") == "WriteF32"), None)
    ctx_start = f32_ctx["file_offset"] if f32_ctx else 0x14

    global_str_trace = global_names_from_trace(ev, ctx_start)
    global_strings_dump = scan_std_strings_in_dump(dump, 0x14, ctx_start, min_len=3)

    vec_end = vec_start + 4 + vec_count * 8 if vec_ev else vec_start
    f278 = next((e for e in ev if e["file_offset"] == vec_end), None)
    if not f278:
        for e in ev:
            if e["file_offset"] >= vec_end and e.get("writer") == "WriteU32":
                f278 = e
                vec_end = e["file_offset"]
                break
    tail_after_27c = (f278["file_offset"] + 8) if f278 else vec_end + 8

    str_events = std_string_clusters(ev, tail_after_27c, dump_size)
    grid_strings = scan_std_strings_in_dump(dump, tail_after_27c, dump_size, min_len=2)

    grid_layout = json.loads(GRID.read_text(encoding="utf-8")) if GRID.is_file() else None
    block_trace = json.loads(BLOCKS.read_text(encoding="utf-8")) if BLOCKS.is_file() else None
    block_corr = json.loads(CORR.read_text(encoding="utf-8")) if CORR.is_file() else None

    report = {
        "dump": str(DUMP),
        "dump_size": dump_size,
        "trace_final_size": trace_final,
        "sizes_match": dump_size == trace_final,
        "sections": [
            {
                "name": "format_version",
                "file_offset": 0,
                "size": 4,
                "insn": "0x6DCBB",
                "value": le_count(version_ev.get("hex")),
            },
            {
                "name": "C3100_global_header",
                "file_offset": 4,
                "size": 12,
                "insn": "0xC3100 @ 0x6DCC0",
                "fields": [
                    {"offset": 4, "type": "u64", "hex": dump[4:12].hex() if len(dump) >= 12 else ""},
                    {"offset": 12, "type": "u32", "value": u32(dump, 12) if len(dump) >= 16 else None},
                    {"offset": 16, "type": "u32_count", "value": global_count},
                ],
            },
            {
                "name": "C3100_global_horse_names",
                "file_offset": 0x14,
                "file_end": ctx_start,
                "size": ctx_start - 0x14,
                "count": global_count,
                "trace_std_string_events": len(global_str_trace),
                "dump_strings_sample": global_strings_dump[:25],
                "dump_strings_total": len(global_strings_dump),
                "note": "Per-entry: WriteStdString + u32 flags (0xC325F loop)",
            },
            {
                "name": "ctx_main_block",
                "file_offset": ctx_start,
                "file_end": vec_start,
                "insn": "0x6DCCA .. 0x6DDC9",
                "ctx_rva_refs": {
                    "0x254": "0x6DCCA",
                    "0x314": "0x6DCD5",
                    "0x268": "0x6DCE0",
                    "0x114": "0x6DCEB",
                    "0x318": "0x6DCFE",
                    "0x308": "0x6DD09",
                    "0x440": "0x6DD14",
                    "slots6": "0x6DD71",
                    "rows13": "0x6DDA3",
                },
                "events_by_offset": ctx_header_fields(ev, ctx_start, vec_start)[:60],
            },
            {
                "name": "horse_u16_vector",
                "file_offset": vec_start,
                "file_end": vec_end,
                "count": vec_count,
                "insn": "0x6DDF9 / 0x6DE30",
                "ctx": "rdi+0x280",
            },
            {
                "name": "fields_278_27c",
                "file_offset": vec_end,
                "size": 8,
                "insn": "0x6DEA9 / 0x6DEB7",
                "values": {
                    "0x278": u32(dump, vec_end) if vec_end + 4 <= dump_size else None,
                    "0x27C": u32(dump, vec_end + 4) if vec_end + 8 <= dump_size else None,
                },
            },
            {
                "name": "grid_and_inventory",
                "file_offset": tail_after_27c,
                "file_end": dump_size,
                "insn": "0x6DF30 (WriteU8) + 0x1167B0 lookup + 0x6E043 pairs + 0x6D440 nested",
                "std_string_events_in_trace": len(str_events),
                "parsed_strings_total": len(grid_strings),
                "parsed_strings_sample": grid_strings[:30],
                "parsed_strings_tail": grid_strings[-10:] if len(grid_strings) > 10 else [],
                "grid_layout": grid_layout,
                "block_trace_summary": _summarize_block_trace(block_trace),
                "block_correlation": block_corr,
            },
        ],
        "milestones": {
            "ctx_block_start": ctx_start,
            "horse_vector_start": vec_start,
            "tail_start": tail_after_27c,
        },
    }

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"  dump={dump_size} trace_final={trace_final} match={dump_size == trace_final}")
    print(f"  global_names={global_count} ctx_start=0x{ctx_start:X} vec=0x{vec_start:X} n={vec_count}")
    print(f"  grid_strings_parsed={len(grid_strings)} (trace std events={len(str_events)})")
    # Sidecar for tools
    names_out = ROOT / "RE_Tools" / "analysis" / "save_global_names.json"
    grid_out = ROOT / "RE_Tools" / "analysis" / "save_grid_strings.json"
    names_out.write_text(json.dumps(global_strings_dump, indent=2), encoding="utf-8")
    grid_out.write_text(json.dumps(grid_strings, indent=2), encoding="utf-8")
    print(f"  wrote {names_out.name} ({len(global_strings_dump)}), {grid_out.name} ({len(grid_strings)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
