"""Export trace-derived inventory block table for C loader."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "scripts"))
from save_file_codec import _inventory_blocks_from_trace  # noqa: E402

OUT = ROOT / "RE_Tools" / "analysis" / "save_inventory_blocks.json"


def main() -> int:
    blocks = [{"offset": o, "size": s} for o, s in _inventory_blocks_from_trace()]
    OUT.write_text(
        json.dumps(
            {
                "source": "save_writer_trace.json WriteStdString @ 0x6E0D6",
                "count": len(blocks),
                "total_bytes": sum(b["size"] for b in blocks),
                "blocks": blocks,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {OUT} ({len(blocks)} blocks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
