"""
Decode save tail grid + post-grid sections from aligned dump.

Source (Horsey.exe, verified via Capstone):
  Grid loop @ 0x6DF30 — cells at [rdi+0x270], stride 0x28, count = [0x27C]*[0x278]
  Type lookup @ 0x1167B0 (NOT a writer — returns u32 from table; test eax after call)
  Pairs @ 0x6E043 — (u32,u32) x N from [rdi+0x420..0x428), stride 8
  Nested @ 0x6D440 — WriteNestedSave (std::string + vectors + 0x6EC40 items)

Input:
  RE_Tools/analysis/save_buffer_dump.bin

Output:
  RE_Tools/analysis/save_grid_layout.json
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
TRACE = ROOT / "RE_Tools" / "analysis" / "save_writer_trace.json"
OUT = ROOT / "RE_Tools" / "analysis" / "save_grid_layout.json"

# File offsets from map_save_full_layout.py (aligned 204386 B run)
TAIL_START = 0xA61  # after fields 0x278 / 0x27C


def u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def scan_0f09_run(data: bytes, start: int) -> tuple[int, int]:
    """Return (run_end_offset, pair_count) for leading 0x0F 0x09 pairs."""
    i = start
    pairs = 0
    while i + 1 < len(data) and data[i] == 0x0F and data[i + 1] == 0x09:
        pairs += 1
        i += 2
    return i, pairs


def first_trace_offset_in_tail(min_off: int) -> int | None:
    if not TRACE.is_file():
        return None
    trace = json.loads(TRACE.read_text(encoding="utf-8"))
    tail_events = [e["file_offset"] for e in trace["events"] if e["file_offset"] >= min_off]
    return min(tail_events) if tail_events else None


def byte_histogram(data: bytes, top_n: int = 8) -> list[dict]:
    from collections import Counter

    c = Counter(data)
    return [{"byte": f"0x{k:02X}", "count": v} for k, v in c.most_common(top_n)]


def main() -> int:
    if not DUMP.is_file():
        print(f"Missing {DUMP}")
        return 1

    dump = DUMP.read_bytes()
    if len(dump) < TAIL_START + 8:
        print("Dump too small")
        return 1

    width = u32(dump, TAIL_START - 8)  # ctx+0x278 @ file 0xA59
    height = u32(dump, TAIL_START - 4)  # ctx+0x27C @ file 0xA5D
    expected_cells = width * height

    prefix_end, prefix_pairs = scan_0f09_run(dump, TAIL_START)
    trace_start = first_trace_offset_in_tail(TAIL_START)
    grid_main_end = trace_start if trace_start and trace_start > prefix_end else len(dump)

    grid_prefix = dump[TAIL_START:prefix_end]
    grid_main = dump[prefix_end:grid_main_end]
    traced_tail = dump[grid_main_end:] if grid_main_end < len(dump) else b""

    report = {
        "source": {
            "dump": str(DUMP),
            "dump_size": len(dump),
            "disasm_refs": {
                "grid_loop": "0x6DF30",
                "cell_stride_mem": "0x28",
                "grid_ptr": "rdi+0x270",
                "dimensions": "imul [rdi+0x27C], [rdi+0x278] @ 0x6DF18",
                "type_lookup": "0x1167B0 (returns u32; test eax @ 0x6DFF3)",
                "pair_loop": "0x6E043",
                "nested_save": "0x6D440",
                "nested_item": "0x6EC40",
            },
        },
        "dimensions": {
            "width_ctx_278": width,
            "height_ctx_27C": height,
            "expected_cell_count": expected_cells,
            "note": "Empty cells (type==6) write 0 bytes; disk size << count*stride",
        },
        "save_grid_cell_mem": {
            "size": 0x28,
            "fields": [
                {"offset": 0x00, "type": "u32", "role": "cell type; 6 = skip write"},
                {"offset": 0x04, "type": "u8", "role": "extra byte if 0x1167B0 lookup > 0"},
                {"offset": 0x08, "type": "u32", "role": "layer / height index vs globals"},
                {"offset": 0x0C, "type": "u8", "role": "flag (encoding OR 0x40 path)"},
                {"offset": 0x0D, "type": "u8", "role": "flag (encoding OR 0x80 path)"},
            ],
        },
        "on_disk_encoding": {
            "common_pair": "0x0F 0x09",
            "note": "WriteU8 @ 0x6FEB0; compact Frida trace omits these bytes",
        },
        "sections": [
            {
                "name": "grid_prefix_0f09",
                "file_offset": TAIL_START,
                "file_end": prefix_end,
                "size": len(grid_prefix),
                "pair_count": prefix_pairs,
                "note": f"Leading {prefix_pairs} x (0x0F,0x09); often width+1 ({width+1}) pairs",
            },
            {
                "name": "grid_main_u8",
                "file_offset": prefix_end,
                "file_end": grid_main_end,
                "size": len(grid_main),
                "histogram": byte_histogram(grid_main),
                "bytes_per_cell_if_uniform": round(len(grid_main) / expected_cells, 4)
                if expected_cells
                else None,
            },
            {
                "name": "inventory_nested_traced",
                "file_offset": grid_main_end,
                "file_end": len(dump),
                "size": len(traced_tail),
                "note": "WriteU32/WriteStdString visible in compact trace; includes 0x6D440 blobs",
            },
        ],
        "milestones": {
            "tail_start": TAIL_START,
            "grid_prefix_end": prefix_end,
            "first_compact_trace_offset": trace_start,
            "tail_total": len(dump) - TAIL_START,
        },
        "write_nested_save_6D440": {
            "order": [
                "std::string @ object+0x18 (0x6FFF0 via 0x279E0)",
                "u32 count: (end+0x138 - begin+0x130) >> 3; per ptr call 0x6EC40",
                "u32 merged index (0x6FE10)",
                "u32 count: (end+0xC0 - begin+0xB8) >> 3; per entry u32 + vcall [+0x48]",
                "Vec2F32 @ object+0x0C (0x6FF30)",
                "u32 flag if object+0x150 non-null; optional 0x6D2A0",
            ],
        },
        "write_nested_item_6EC40": {
            "writers": [
                "0x6FE70 @ object+0x2A8",
                "0x6FE10 @ object+0x1F8",
                "0x6FE50 @ object+0x220",
                "0x6FE30 bytes @ +0x1C, +0x1FC, +0x21C, +0x284, +0x214, ...",
                "0x6D2A0 @ object+0x2B8",
            ],
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    print(
        f"  dims={width}x{height} cells={expected_cells} "
        f"prefix={len(grid_prefix)}B main={len(grid_main)}B traced={len(traced_tail)}B"
    )
    if trace_start:
        print(f"  first compact trace @ 0x{trace_start:X} (grid U8 gap {trace_start - TAIL_START} B)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
