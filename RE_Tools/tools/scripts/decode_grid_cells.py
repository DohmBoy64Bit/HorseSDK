"""
Decode grid bytes using Save_LoadFromBuffer grid loop @ 0x6E700 (mirror of 0x6DF30).

Reads save_buffer_dump.bin grid section and emits per-cell records.

Output: RE_Tools/analysis/save_grid_cells.json (summary + sample)
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
OUT = ROOT / "RE_Tools" / "analysis" / "save_grid_cells.json"

PREFIX_START = 0xA61
PREFIX_END = 0xD83
GRID_PREFIX_BYTES = PREFIX_END - PREFIX_START
GRID_START = 0xD83
GRID_END = 0xDEA7
GRID_STREAM_BYTES = 52664
GRID_PAD_BYTES = GRID_END - GRID_START - GRID_STREAM_BYTES
WIDTH = 400
HEIGHT = 225
# From disasm: dword ptr [rip+0x2a1c7e] used in layer decode — sample uses field_27C area
LAYER_BASE_SAMPLE = 0  # actual base read from globals at runtime


class Reader:
    def __init__(self, data: bytes, off: int = 0):
        self.data = data
        self.pos = off

    def read_u8(self) -> int | None:
        if self.pos >= len(self.data):
            return None
        b = self.data[self.pos]
        self.pos += 1
        return b

    def remaining(self) -> int:
        return len(self.data) - self.pos


def decode_cell_stream(data: bytes, max_cells: int | None = None) -> tuple[list[dict], dict]:
    r = Reader(data)
    cells: list[dict] = []
    skip_run = 0
    cell_index = 0

    while max_cells is None or cell_index < max_cells:
        file_off = GRID_START + r.pos

        if skip_run > 0:
            cells.append({"i": cell_index, "off": file_off, "type": 6, "note": "skip_run"})
            skip_run -= 1
            cell_index += 1
            continue

        b = r.read_u8()
        if b is None:
            if max_cells is not None and cell_index < max_cells:
                cells.append(
                    {"i": cell_index, "off": file_off, "type": 6, "note": "virtual_eof"}
                )
                cell_index += 1
                continue
            break

        if b == 0x3F:
            b2 = r.read_u8()
            if b2 is None:
                skip_run = 0
                cells.append(
                    {
                        "i": cell_index,
                        "off": file_off,
                        "enc": "3F",
                        "skip_after": 0,
                        "type": 6,
                        "note": "truncated_3f",
                    }
                )
                cell_index += 1
                continue
            skip_run = max(0, b2 - 1)
            cells.append(
                {
                    "i": cell_index,
                    "off": file_off,
                    "enc": "3F",
                    "skip_after": skip_run,
                    "type": 6,
                }
            )
            cell_index += 1
            continue

        enc = f"0x{b:02X}"
        rel = b - 0x3B
        if rel <= 3:
            cells.append(
                {
                    "i": cell_index,
                    "off": file_off,
                    "enc": enc,
                    "type": 0,
                    "layer": rel + LAYER_BASE_SAMPLE,
                    "bytes": 1,
                }
            )
            cell_index += 1
            continue

        ctype = b & 0x3F
        flag_c = (b >> 6) & 1
        flag_d = (b >> 7) & 1
        b2 = r.read_u8()
        if b2 is None:
            break
        layer = b2
        extra = None
        # Write path may emit second byte for +4 when lookup>0; compact saves often 2 bytes
        rec = {
            "i": cell_index,
            "off": file_off,
            "enc": f"{enc} {b2:02X}",
            "type": ctype,
            "layer": layer,
            "flag_c": flag_c,
            "flag_d": flag_d,
            "bytes": 2,
        }
        cells.append(rec)
        cell_index += 1

    stats = {
        "cells_decoded": len(cells),
        "stream_bytes": r.pos,
        "remaining_bytes": r.remaining(),
        "type_counts": {},
    }
    for c in cells:
        t = c.get("type", "?")
        stats["type_counts"][str(t)] = stats["type_counts"].get(str(t), 0) + 1
    return cells, stats


def encode_cell_stream(cells: list[dict]) -> bytes:
    """
    Re-encode grid u8 stream (inverse of decode_cell_stream).

    Uses each cell's `enc` / `skip_after` from decode — matches Horsey.exe @ 0x6DF30 / 0x6FEB0.
    """
    out = bytearray()
    for c in cells:
        if c.get("note") == "skip_run":
            continue
        enc = c.get("enc", "")
        if enc == "3F":
            out.append(0x3F)
            out.append((c.get("skip_after", 0) + 1) & 0xFF)
        elif " " in enc:
            for part in enc.split():
                out.append(int(part, 16) & 0xFF)
        elif enc.startswith("0x"):
            out.append(int(enc, 16) & 0xFF)
    return bytes(out)


def main() -> int:
    if not DUMP.is_file():
        print(f"Missing {DUMP}")
        return 1
    dump = DUMP.read_bytes()
    prefix = dump[PREFIX_START:PREFIX_END]
    grid_stream = dump[GRID_START : GRID_START + GRID_STREAM_BYTES]

    all_cells, stats = decode_cell_stream(grid_stream, max_cells=WIDTH * HEIGHT)
    nonempty = [c for c in all_cells if c.get("type") != 6]

    report = {
        "disasm_write": "0x6DF30",
        "disasm_read": "0x6E700",
        "dimensions": {"width": WIDTH, "height": HEIGHT, "expected": WIDTH * HEIGHT},
        "prefix": {"off": PREFIX_START, "size": len(prefix), "pairs_0f09": prefix.count(bytes([0x0F, 0x09])) // 2},
        "grid_main": stats,
        "encoding_rules": [
            "0x3F + N: mark next N cells as type 6 (empty)",
            "byte in [0x3B..0x3E]: type 0 + layer = byte - 0x3B + global_base",
            "else: byte0 = type|(flag_c<<6)|(flag_d<<7), byte1 = layer",
            "pair 0x0F 0x09: type 15, layer 9 (common empty-ish tile)",
        ],
        "sample_nonempty": nonempty[:40],
        "sample_tail": nonempty[-15:] if len(nonempty) > 15 else [],
    }

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"  decoded {stats['cells_decoded']} cells, stream {stats['stream_bytes']} B, types={stats['type_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
