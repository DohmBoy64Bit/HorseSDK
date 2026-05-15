"""
Re-encode save from parsed structure (structural round-trip).

Mirrors Save_Write @ 0x6DAB0 (SaveGhidraCrossref.md):
  globals @ 0x6DCC0, nested @ 0x6D440, inventory @ 0x6E0D6.
Grid/ctx use parsed raw bytes until cell writer exists.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "scripts"))

from save_file_codec import parse_save_bytes, write_save_bytes  # noqa: E402

DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
OUT = ROOT / "RE_Tools" / "analysis" / "save_roundtrip.bin"


def main() -> int:
    data = DUMP.read_bytes()
    parsed = parse_save_bytes(data, path=str(DUMP))
    out_data = write_save_bytes(parsed)

    OUT.write_bytes(out_data)
    print(f"Wrote {OUT} size={len(out_data)} (orig {len(data)})")
    match = out_data == data
    print(f"match={match}")
    if not match:
        for i, (a, b) in enumerate(zip(out_data, data)):
            if a != b:
                print(f"first diff @ {i:#x} got {a:02x} want {b:02x}")
                break
        if len(out_data) != len(data):
            print(f"length diff {len(out_data)} vs {len(data)}")
    return 0 if match else 1


if __name__ == "__main__":
    raise SystemExit(main())
