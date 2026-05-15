"""
Build file layout table from compact save_writer_trace.json.

Output: RE_Tools/analysis/save_trace_layout.json
        updates section anchors for parse_save_sections.py
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TRACE = ROOT / "RE_Tools" / "analysis" / "save_writer_trace.json"
DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
OUT = ROOT / "RE_Tools" / "analysis" / "save_trace_layout.json"


def main() -> int:
    trace = json.loads(TRACE.read_text(encoding="utf-8"))
    ev = trace["events"]
    dump = DUMP.read_bytes() if DUMP.is_file() else b""

    # Section boundaries from trace + disasm
    fed0 = [e for e in ev if e.get("writer_rva") == "0x6FED0"]

    def horse_u16_vector_count(evlist: list) -> dict | None:
        for i, e in enumerate(evlist):
            if e.get("writer_rva") != "0x6FED0":
                continue
            if i + 1 < len(evlist) and evlist[i + 1].get("writer_rva") == "0x6FE50":
                return e
        return None

    vec_horse = horse_u16_vector_count(ev)

    layout = {
        "source": str(TRACE),
        "event_count": len(ev),
        "final_size": trace.get("save_completions", [{}])[-1].get("final_size"),
        "file_header_from_C3100": {
            "note": "0xC3100 @ 0x6DCC0 runs BEFORE ctx fields; was wrongly skipped as empty",
            "fields": ev[: min(30, len(ev))],
        },
        "global_name_table": {
            "file_offset": 0x10,
            "count_insn": "0xC314D WriteU32 count",
            "count_value_hex": ev[3]["hex"] if len(ev) > 3 else None,
            "first_string_at": 0x14,
        },
        "ctx_block_estimate": {
            "note": "ctx[rdi+…] writes from 0x6DCCA start after C3100 block ends",
            "search": "first WriteU32 @ 0x6DCFE region — use trace offset ~0x900+",
        },
        "horse_u16_vector_rdi_280": {
            "file_offset": vec_horse["file_offset"] if vec_horse else None,
            "count_hex": vec_horse.get("hex") if vec_horse else None,
            "count": int.from_bytes(bytes.fromhex(vec_horse["hex"]), "little")
            if vec_horse and vec_horse.get("hex")
            else None,
            "records": vec_horse["file_offset"] + 4 if vec_horse else None,
            "disk_bytes_per_record": 8,
            "insn": "0x6DDF9 / 0x6DE30",
        },
        "all_write_u32_count_calls": [
            {"off": e["file_offset"], "hex": e.get("hex"), "val": int(e["hex"], 16) if e.get("hex") else None}
            for e in fed0[:25]
        ],
        "milestones": _milestones(ev),
    }

    if dump and vec_horse:
        off = vec_horse["file_offset"]
        n = struct.unpack_from("<I", dump, off)[0] if off + 4 <= len(dump) else 0
        layout["horse_u16_vector_rdi_280"]["dump_count_at_offset"] = n

    OUT.write_text(json.dumps(layout, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    if vec_horse:
        v = vec_horse
        print(f"  horse u16 vector @ 0x{v['file_offset']:X} count={layout['horse_u16_vector_rdi_280'].get('count')}")
    return 0


def _milestones(ev: list) -> list:
    """Key offsets: version, end of C3100 (~first F32 from 6DCF3), vector, last write."""
    out = []
    for e in ev:
        if e["writer_rva"] == "0x6FE10" and e["file_offset"] == 0:
            out.append({"name": "format_version", **e})
            break
    f32 = [e for e in ev if e.get("writer_rva") == "0x6FF10"]
    if f32:
        out.append({"name": "first_WriteF32_ctx", **f32[0]})
    fed0 = [e for e in ev if e.get("writer_rva") == "0x6FED0" and e["file_offset"] > 0x500]
    if fed0:
        out.append({"name": "horse_u16_vector_count", **fed0[0]})
    if ev:
        out.append({"name": "last_event", **ev[-1]})
    return out


if __name__ == "__main__":
    raise SystemExit(main())
