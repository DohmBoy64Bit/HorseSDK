"""
Parse save_buffer_dump.bin and re-encode; compare size and inventory genes.

  python RE_Tools/tools/scripts/verify_save_roundtrip.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "scripts"))

from inventory_pack_codec import unpack_6d3b0  # noqa: E402
from save_file_codec import parse_save_bytes  # noqa: E402
from save_stream import SaveStream  # noqa: E402
from nested_save_codec import write_nested_save  # noqa: E402

DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"


def main() -> int:
    data = DUMP.read_bytes()
    parsed = parse_save_bytes(data, path=str(DUMP))
    out = SaveStream(b"")
    out.write_u32(parsed.format_version)
    out.write_bytes(data[4:20])
    for name in parsed.global_names:
        out.write_string(name)
        out.write_u32(0x00010000)
        out.write_u32(0x00010000)
        out.write_u32(0xFFFFFFFF)
        out.write_u32(0xFFFFFFFF)
        out.write_u32(0)
        out.write_bytes(b"\x00\x00")
    out.seek(parsed.milestones["globals_end"])
    out.write_bytes(data[out.pos : parsed.milestones["pairs_end"]])
    if parsed.main_nested:
        write_nested_save(out, parsed.main_nested)
    for inv in parsed.inventory:
        write_nested_save(out, inv)
    for foot in parsed.footer_chunks:
        write_nested_save(out, foot)

    print(f"original {len(data)} rebuilt {len(out.data)} parsed_eof {parsed.milestones.get('eof')}")
    if parsed.inventory:
        g0 = parsed.inventory[0].gene_packed
        print(f"slot0 gene nz={sum(1 for x in unpack_6d3b0(g0)[:0xF0] if x)}")
    return 0 if parsed.milestones.get("eof") == len(data) else 1


if __name__ == "__main__":
    raise SystemExit(main())
