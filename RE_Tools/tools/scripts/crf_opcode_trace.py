"""
Walk .crf section 1 glyph streams and classify record prefixes.

Verified container: crf_font.py (16-byte header + section1 + section2).
Opcode semantics: HYPOTHESIS — validated by frequency across fonts.

Output: RE_Tools/analysis/crf_opcode_trace.json
"""
from __future__ import annotations

import json
import struct
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "parsers"))

from paths import get_data_dir  # noqa: E402
from crf_font import CrfFont  # noqa: E402

OUT = ROOT / "RE_Tools" / "analysis" / "crf_opcode_trace.json"

# Record leaders observed in quip.crf / habit_* (little-endian u16 + tag byte)
RECORD_MARKERS = (
    b"\x09\x00\xf8",
    b"\x09\x00\xf9",
    b"\x07\x00\xf8",
    b"\x07\x00\xf9",
    b"\x05\x07\x00",
    b"\x06\x07\x00",
)


def find_markers(data: bytes) -> list[int]:
    hits: list[int] = []
    for i in range(len(data) - 2):
        triple = data[i : i + 3]
        if triple in RECORD_MARKERS:
            hits.append(i)
    return hits


def split_records(data: bytes) -> list[dict]:
    marks = find_markers(data)
    records: list[dict] = []
    for idx, off in enumerate(marks):
        end = marks[idx + 1] if idx + 1 < len(marks) else len(data)
        chunk = data[off:end]
        u16 = struct.unpack_from("<H", chunk, 0)[0] if len(chunk) >= 2 else 0
        tag = chunk[2] if len(chunk) >= 3 else None
        records.append(
            {
                "offset": off,
                "length": len(chunk),
                "prefix_u16": u16,
                "tag_byte": tag,
                "head_hex": chunk[: min(16, len(chunk))].hex(),
            }
        )
    return records


def analyze_font(path: Path) -> dict:
    c = CrfFont.load(path)
    s1 = c.section1
    marks = find_markers(s1)
    prefix_counts = Counter(s1[i : i + 3].hex() for i in marks)
    records = split_records(s1) if s1 else []
    return {
        "file": path.name,
        "section1_len": len(s1),
        "section2_len": len(c.section2),
        "marker_count": len(marks),
        "top_prefixes": prefix_counts.most_common(12),
        "records_sample": records[:25],
        "records_total": len(records),
        "hypothesis": (
            "Records start at u16=09/07/05/06 + 00 + tag (f8/f9). "
            "Length = distance to next marker. Full opcode map UNVERIFIED."
        ),
    }


def main() -> int:
    data_dir = get_data_dir()
    fonts = [analyze_font(p) for p in sorted(data_dir.glob("*.crf"))]
    report = {
        "verification": "Marker scan on section1 only; not executed by game",
        "fonts": fonts,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    for f in fonts:
        print(f"  {f['file']}: {f['marker_count']} markers, {f['records_total']} records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
