"""Generate horse_save_inventory_blocks.inc for C loader."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "scripts"))
from save_file_codec import _inventory_blocks_from_trace  # noqa: E402

OUT = ROOT / "RE_Tools" / "src" / "horse_save" / "horse_save_inventory_blocks.inc"


def main() -> int:
    blocks = _inventory_blocks_from_trace()
    lines = [
        "/* Auto-generated from save_writer_trace.json — do not edit */",
        f"#define HORSE_SAVE_INVENTORY_BLOCK_COUNT {len(blocks)}",
        "static const struct { uint32_t off; uint32_t size; } g_inv_blocks[] = {",
    ]
    for o, s in blocks:
        lines.append(f"    {{ 0x{o:X}u, {s}u }},")
    lines.append("};")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} ({len(blocks)} blocks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
