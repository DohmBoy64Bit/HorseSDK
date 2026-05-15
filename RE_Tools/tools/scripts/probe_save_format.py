"""
Probe Game/save/save1.dat layout (header + strings only — no field guessing beyond u32 scan).

Output: RE_Tools/analysis/save_format_probe.json
"""
from __future__ import annotations

import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
from paths import get_save_dir  # noqa: E402

OUT = ROOT / "RE_Tools" / "analysis" / "save_format_probe.json"


def probe(path: Path) -> dict:
    b = path.read_bytes()
    header_u32 = [struct.unpack_from("<I", b, i)[0] for i in range(0, min(64, len(b)), 4)]
    strings = [
        {"offset": m.start(), "text": m.group().decode("ascii", errors="replace")}
        for m in re.finditer(rb"[\x20-\x7e]{4,}", b)
    ]
    return {
        "file": path.name,
        "byte_size": len(b),
        "header_hex_64": b[:64].hex(),
        "first_16_u32": [hex(x) for x in header_u32[:16]],
        "first_ascii_strings": strings[:30],
        "string_count_4plus": len(strings),
        "note": "Full schema needs Ghidra on Save @ 0x6DAB0",
    }


def main() -> int:
    save_dir = get_save_dir()
    files = sorted(save_dir.glob("*.dat"))
    report = {
        "save_dir": str(save_dir),
        "files": [probe(p) for p in files],
        "exe_save_string": "save1.dat not found as literal in Horsey.exe (see phase1_string_xrefs.json)",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} ({len(files)} .dat)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
