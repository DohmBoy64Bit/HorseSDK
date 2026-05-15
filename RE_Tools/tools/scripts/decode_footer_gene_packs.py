"""
Decode footer 0xF0 gene packs (was labeled 'opaque blob').

Verified Horsey.exe:
  WriteNestedSave @ 0x6D579: if [obj+0x150] -> call 0x6D2A0 (pack) -> 0x70220 writes 0xF0 bytes
  ReadNestedSave  @ 0x6D7F5: if flag -> Read 0xF0 via 0x70C20 -> unpack @ 0x6D840 (same as 0x6D3B0)

Sample save1.dat:
  settings pack @ 0x31B41 (panel_settings)
  track pack    @ 0x31CE6 (after nested name 'unknown', u32 1)
"""
from __future__ import annotations

import json
from pathlib import Path

from inventory_pack_codec import GENE_COUNT, unpack_6d3b0

ROOT = Path(__file__).resolve().parents[3]
DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
OUT = ROOT / "RE_Tools" / "analysis" / "save_footer_gene_packs.json"

PACK_OFF = 0xF0
FOOTER_GENE_PACKS = [
    {
        "id": "footer_gene_settings",
        "file_offset": 0x31B41,
        "role": "Global footer nested gene buffer (settings panel)",
    },
    {
        "id": "footer_gene_track",
        "file_offset": 0x31CE6,
        "role": "Track panel gene buffer (after name 'unknown')",
    },
]


def summarize_track(track: bytes) -> dict:
    nz = sum(1 for b in track if b != 0)
    return {
        "nonzero": nz,
        "min": min(track) if track else 0,
        "max": max(track) if track else 0,
        "sample": list(track[:8]),
    }


def main() -> int:
    if not DUMP.is_file():
        print(f"Missing {DUMP}")
        return 1
    dump = DUMP.read_bytes()
    packs: list[dict] = []
    for spec in FOOTER_GENE_PACKS:
        off = spec["file_offset"]
        packed = dump[off : off + PACK_OFF]
        unpacked = bytes(unpack_6d3b0(packed))
        packs.append(
            {
                **spec,
                "packed_bytes": PACK_OFF,
                "unpacked_bytes": len(unpacked),
                "packed_hex_prefix": packed[:16].hex(),
                "track_a": summarize_track(unpacked[:GENE_COUNT]),
                "track_b": summarize_track(unpacked[GENE_COUNT : GENE_COUNT * 2]),
                "disasm_write": "0x6D2A0 -> 0x70220 (0xF0 B, not Frida WriteU8)",
                "disasm_read": "0x6D811 Read 0xF0 + 0x6D840 unpack",
            }
        )
    report = {
        "format": "gene_pack_0xF0",
        "gene_count": GENE_COUNT,
        "note": "Same codec as inventory +0x51; values are g0..g3 indices into genes.xml",
        "ae470": "deferred — see SaveFutureWork.md (runtime only)",
        "packs": packs,
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    for p in packs:
        print(f"  {p['id']} @ 0x{p['file_offset']:X} A_nz={p['track_a']['nonzero']} B_nz={p['track_b']['nonzero']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
