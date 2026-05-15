"""
Grid cell type table used by FUN_1401167B0 @ 0x1167B0 (Horsey.exe).

Each entry is 0x1C bytes; index = grid cell / b8 component [obj+0x48] (default 0x17 = 23).
Verified: Capstone @ 0x1167BE imul rax, 0x1c; entry 23 contains ASCII 'terrain.GrassLand'.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[3]
EXE = ROOT / "Game" / "Horsey.exe"
OUT = ROOT / "RE_Tools" / "analysis" / "grid_type_lookup.json"

TABLE_RVA = 0x26B678
ENTRY_BYTES = 0x1C
IMAGE_BASE = 0x140000000


def _ascii_label(raw: bytes) -> str:
    parts: list[str] = []
    cur: list[int] = []
    for b in raw:
        if 32 <= b < 127:
            cur.append(b)
        elif cur:
            if len(cur) >= 3:
                parts.append(bytes(cur).decode("ascii"))
            cur = []
    if len(cur) >= 3:
        parts.append(bytes(cur).decode("ascii"))
    return ".".join(parts) if parts else ""


def load_grid_type_table(exe_path: Path | None = None) -> list[dict]:
    path = exe_path or EXE
    pe = pefile.PE(str(path))
    blob = path.read_bytes()
    fo = pe.get_offset_from_rva(TABLE_RVA)
    entries: list[dict] = []
    for idx in range(64):
        off = fo + idx * ENTRY_BYTES
        raw = blob[off : off + ENTRY_BYTES]
        if not raw:
            break
        dword0 = struct.unpack_from("<I", raw, 0)[0]
        label = _ascii_label(raw)
        entries.append(
            {
                "id": idx,
                "dword0": dword0,
                "label": label,
                "hex": raw.hex(),
            }
        )
    return entries


def label_for_type_id(type_id: int, table: list[dict] | None = None) -> str:
    table = table or load_grid_type_table()
    if 0 <= type_id < len(table):
        lab = table[type_id].get("label") or ""
        if lab:
            return lab
    return f"type_{type_id}"


def main() -> int:
    if not EXE.is_file():
        print(f"Missing {EXE}")
        return 1
    entries = load_grid_type_table()
    report = {
        "disasm": "FUN_1401167B0 @ 0x1167B0",
        "table_rva": f"0x{TABLE_RVA:X}",
        "entry_bytes": ENTRY_BYTES,
        "b8_default": {
            "object_offset": "0x48",
            "ctor_rva": "0xA3148",
            "value": 0x17,
            "id": 23,
            "label": label_for_type_id(23, entries),
        },
        "entries": [e for e in entries if e["label"] or e["dword0"] or e["id"] < 32],
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} ({len(entries)} slots)")
    print(f"  type 23 = {report['b8_default']['label']!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
