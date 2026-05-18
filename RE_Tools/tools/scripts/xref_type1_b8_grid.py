"""
Xref type-1 b8 +0xA0 u32 as horsey.tmx linear tile index (400-wide grid).

Verified:
  save_buffer_dump.bin type-1 payload +0xA0 = 0x1F00 (7936)
  7936 = 19 * 400 + 336 — matches Game/data/horsey.tmx 400x225
  Type-2 inner coord8 uses ASCII tile keys (e.g. ',9,9,9,9')

Output: RE_Tools/analysis/save_type1_xref.json
"""
from __future__ import annotations

import json
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
from paths import get_data_dir, get_exe_path  # noqa: E402

OUT = ROOT / "RE_Tools" / "analysis" / "save_type1_xref.json"
DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
GRID_W = 400
TYPE1_A0 = 0x1F00


def load_tmx_size() -> tuple[int, int]:
    tmx = get_data_dir() / "horsey.tmx"
    root = ET.parse(tmx).getroot()
    w = int(root.attrib.get("width", 0))
    h = int(root.attrib.get("height", 0))
    return w, h


def main() -> int:
    w, h = load_tmx_size()
    idx = TYPE1_A0
    row, col = divmod(idx, w)
    sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "scripts"))
    from nested_b8_codec import decode_type1_payload  # noqa: E402

    d = DUMP.read_bytes()
    payload_off = 0xDEE6
    dec = decode_type1_payload(d[payload_off : payload_off + 57])
    a0 = int(dec["+0xA0_u32"])

    report = {
        "verified_on": str(get_exe_path()),
        "tmx": {"file": str(get_data_dir() / "horsey.tmx"), "width": w, "height": h},
        "type1_b8": {
            "file_offset_a0": payload_off,
            "u32": a0,
            "hex": hex(a0),
        },
        "grid_index": {
            "linear": idx,
            "row": row,
            "col": col,
            "formula": "row = index // 400; col = index % 400",
            "in_bounds": row < h and col < w,
        },
        "exe_refs": {
            "serialize_write": "Horsey.exe+0x102DC0 — WriteU32 [obj+0xA0]",
            "serialize_read": "Horsey.exe+0x102E20 — ReadU32 [obj+0xA0]",
            "component_ctor": "Horsey.exe+0x101850 — type tag 1, alloc 0xB0",
            "b8_dispatch_write": "Horsey.exe+0x6D530 — vtable+0x48",
            "b8_dispatch_read": "Horsey.exe+0x6D6F5 — type==1 → ctor 0x101850",
        },
        "correlation": {
            "main_nested_name": "unknown",
            "merge_index": 0xFFFFFFFF,
            "role": "Primary placed-world entity anchor tile (slot 0 type-1 record)",
            "type2_coord8_note": "Other b8 slots use coord8 tile keys (comma-separated ASCII)",
        },
        "sample_type2_coords": [],
    }

    # coord8 samples from manifest / b8 json
    b8_path = ROOT / "RE_Tools" / "analysis" / "save_main_nested_b8.json"
    if b8_path.is_file():
        data = json.loads(b8_path.read_text(encoding="utf-8"))
        for ent in data.get("entries", []):
            if ent.get("type_id") != 2:
                continue
            for inner in ent.get("decoded", {}).get("inners", [])[:2]:
                hx = inner.get("coord8_hex", "")
                if hx:
                    report["sample_type2_coords"].append(
                        {
                            "coord8_hex": hx,
                            "ascii": bytes.fromhex(hx).decode("ascii", errors="replace"),
                            "grid_cell_type_id": inner.get("grid_cell_type_id"),
                        }
                    )

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} tile ({row},{col}) index={idx} tmx={w}x{h}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
