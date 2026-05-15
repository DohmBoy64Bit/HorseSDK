"""
Decode grid WriteU8 stream @ file 0xD83..0xDEA6 from 0x6DF30 encoding rules.

Source: Horsey.exe @ 0x6DF30 (Capstone), save_buffer_dump.bin
Output: RE_Tools/analysis/save_grid_u8_layout.json
"""
from __future__ import annotations

import json
import struct
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
OUT = ROOT / "RE_Tools" / "analysis" / "save_grid_u8_layout.json"

PREFIX_START = 0xA61
PREFIX_END = 0xD83
GRID_START = 0xD83
GRID_END = 0xDEA7
WIDTH = 400
HEIGHT = 225


def decode_stream(data: bytes) -> list[dict]:
    """Heuristic decoder for per-cell byte runs (not full 90k simulation)."""
    out: list[dict] = []
    i = 0
    n = len(data)
    while i < n:
        if i + 1 < n and data[i] == 0x0F and data[i + 1] == 0x09:
            out.append({"off": i, "size": 2, "kind": "pair_0F09", "note": "default/empty encoding"})
            i += 2
            continue
        if i + 1 < n and data[i] == 0x3F:
            out.append({"off": i, "size": 2, "kind": "r14_flush", "value": data[i + 1]})
            i += 2
            continue
        # single byte cell tag
        b = data[i]
        out.append({"off": i, "size": 1, "kind": "u8_tag", "value": b, "hex": f"0x{b:02X}"})
        i += 1
        if len(out) > 50000:
            break
    return out


def main() -> int:
    if not DUMP.is_file():
        print(f"Missing {DUMP}")
        return 1
    dump = DUMP.read_bytes()
    prefix = dump[PREFIX_START:PREFIX_END]
    grid = dump[GRID_START:GRID_END]

    prefix_pairs = sum(1 for i in range(0, len(prefix) - 1, 2) if prefix[i : i + 2] == b"\x0f\x09")
    decoded = decode_stream(grid)
    kinds = Counter(d["kind"] for d in decoded)

    report = {
        "disasm": "0x6DF30 grid loop; WriteU8 @ 0x6FEB0",
        "dimensions": {"width": WIDTH, "height": HEIGHT, "cells": WIDTH * HEIGHT},
        "prefix": {
            "file_offset": PREFIX_START,
            "size": len(prefix),
            "pair_0F09_count": prefix_pairs,
            "note": "401 pairs = width+1 row markers before main grid stream",
        },
        "grid_main": {
            "file_offset": GRID_START,
            "size": len(grid),
            "decoded_token_count": len(decoded),
            "token_kinds": dict(kinds),
            "avg_bytes_per_token": round(len(grid) / max(len(decoded), 1), 3),
            "implied_nonempty_cells": kinds.get("pair_0F09", 0) + kinds.get("u8_tag", 0) + kinds.get("r14_flush", 0),
        },
        "encoding_rules": [
            "type==6 + empty flags: 0 bytes (skipped)",
            "r14 run: 0x3F + count byte (skipped row batch)",
            "common empty on disk: 0x0F 0x09 (2 bytes)",
            "nonzero type: 1-4 bytes + optional byte @ cell+4 if GridTypeLookup>0",
        ],
        "samples": decoded[:40],
        "samples_tail": decoded[-15:],
    }

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"  prefix 0F09={prefix_pairs} grid tokens={len(decoded)} kinds={dict(kinds)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
