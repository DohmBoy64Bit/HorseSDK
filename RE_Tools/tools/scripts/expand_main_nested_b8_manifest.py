"""
Build per-slot manifest for main nested b8 vector (343 in-memory slots).

Verified: Horsey.exe ReadNestedSave @ 0x6D6F5 — ReadU32 type then vcall +0x50;
EOF returns 0 without advancing (implicit empty slots).

Source: save_buffer_dump.bin via save_file_codec + nested_b8_codec.py
Output: RE_Tools/analysis/save_main_nested_b8_manifest.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "scripts"))

from nested_b8_codec import parse_b8_blob, summarize_b8_blob  # noqa: E402
from save_file_codec import parse_save_bytes  # noqa: E402

OUT = ROOT / "RE_Tools" / "analysis" / "save_main_nested_b8_manifest.json"
DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"


def expand_slots(entries: list, header_count: int) -> list[dict]:
    """Flatten parsed blob entries into logical slot indices (0..header_count-1)."""
    slots: list[dict] = []
    idx = 0

    def add(slot: dict) -> None:
        nonlocal idx
        slot["slot"] = idx
        slots.append(slot)
        idx += 1

    for ent in entries:
        if ent.type_id == 1:
            add(
                {
                    "kind": "type1",
                    "wire_bytes": len(ent.payload),
                    "disasm": "0x102E20 / vtable+0x48",
                    "note": ent.decoded.get("note"),
                }
            )
        elif ent.type_id == 2:
            for inner_i, inner in enumerate(ent.decoded.get("inners", [])):
                add(
                    {
                        "kind": "type2_inner",
                        "block_inner": inner_i,
                        "grid_cell_type_id": inner.get("grid_cell_type_id"),
                        "cell_flag_c": inner.get("cell_flag_c"),
                        "coord8_hex": inner.get("coord8_hex"),
                        "link_u32": inner.get("link_u32"),
                        "disasm": "0x0A30F0 component, 164 B block",
                    }
                )
        elif ent.type_id == 0:
            for row in ent.decoded.get("type0_entries", []):
                add(
                    {
                        "kind": "type0_packed",
                        "packed": row.get("packed"),
                        "dword_38": row.get("dword_38"),
                        "flag_10": row.get("flag_10"),
                        "flag_11": row.get("flag_11"),
                        "disasm": "0x6D8C0 / 0x6FEB0",
                    }
                )

    while idx < header_count:
        add(
            {
                "kind": "implicit_eof",
                "on_disk": False,
                "disasm": "ReadU32 @ 0x70540 returns 0 at EOF — slot skipped in file",
            }
        )
    return slots


def main() -> int:
    if not DUMP.is_file():
        print(f"Missing {DUMP}")
        return 1
    parsed = parse_save_bytes(DUMP.read_bytes())
    mn = parsed.main_nested
    if not mn:
        print("no main_nested")
        return 1
    entries = parse_b8_blob(mn.b8_blob, mn.b8_count)
    summary = summarize_b8_blob(mn.b8_blob, mn.b8_count)
    slots = expand_slots(entries, mn.b8_count)
    hist: dict[str, int] = {}
    for s in slots:
        hist[s["kind"]] = hist.get(s["kind"], 0) + 1

    report = {
        "name": mn.name,
        "header_count": mn.b8_count,
        **summary,
        "slot_histogram": hist,
        "slots": slots,
        "exe_refs": {
            "write_nested": "0x6D440",
            "read_nested": "0x6D5C0",
            "b8_write_vcall": "0x6D530 vtable+0x48",
            "b8_read_vcall": "0x6D6F5 vtable+0x50",
        },
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} slots={len(slots)} hist={hist}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
