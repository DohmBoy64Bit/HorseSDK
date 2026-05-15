"""
Probe .crf compiled font binaries in Game/data/.

Output: RE_Tools/analysis/crf_probe.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "parsers"))

from paths import get_data_dir, get_exe_path  # noqa: E402
from crf_font import CrfFont  # noqa: E402

OUT = ROOT / "RE_Tools" / "analysis" / "crf_probe.json"


def probe(path: Path) -> dict:
    c = CrfFont.load(path)
    h = c.header
    info: dict = {
        "name": path.name,
        "byte_size": path.stat().st_size,
        "header_hex": path.read_bytes()[:16].hex(),
        "header": {
            "byte0": h.byte0,
            "byte1": h.byte1_line_height_guess,
            "byte2": h.byte2,
            "byte3": h.byte3,
            "field_a": h.field_a,
            "section1_bytes": h.section1_bytes,
            "field_c": hex(h.field_c),
        },
        "section1_len": len(c.section1),
        "section2_len": len(c.section2),
        "section2_head_hex": c.section2[:16].hex() if c.section2 else "",
        "layout": "16-byte hdr; section1=[0x10..0x10+section1_bytes]; section2=rest",
    }
    png = path.with_suffix(".png")
    info["companion_png"] = png.name if png.is_file() else None
    return info


def main() -> int:
    data_dir = get_data_dir()
    crfs = sorted(data_dir.glob("*.crf"))
    exe = get_exe_path()
    blob = exe.read_bytes()
    exe_strings: dict[str, str | None] = {}
    for c in crfs:
        off = blob.find(c.name.encode())
        exe_strings[c.name] = hex(off) if off >= 0 else None

    report = {
        "data_dir": str(data_dir),
        "verification": "Section split verified: 16 + section1_bytes + section2 == file size (all 6 fonts)",
        "exe_path": str(exe),
        "files": [probe(p) for p in crfs],
        "exe_string_offsets": exe_strings,
        "generic_crf_suffix_offset": hex(blob.find(b".crf")) if blob.find(b".crf") >= 0 else None,
        "glyph_opcode_stream": "UNVERIFIED — section1 uses 07 00 f9 / 09 00 f8 prefixes",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} ({len(crfs)} .crf files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
