"""
Decode .crf section-1 record payloads (extends crf_opcode_trace.py).

Verified container: RE_Tools/tools/parsers/crf_font.py (16-byte header).

Record boundary: u16 + u8 tag (0xF8 / 0xF9) per crf_opcode_trace markers.

Output:
  RE_Tools/analysis/crf_record_decode.json
  updates RE_Tools/docs/CrfOpcodeSemantics.md (payload section)
"""
from __future__ import annotations

import json
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "parsers"))

from paths import get_data_dir  # noqa: E402
from crf_font import CrfFont  # noqa: E402

OUT = ROOT / "RE_Tools" / "analysis" / "crf_record_decode.json"
OUT_MD = ROOT / "RE_Tools" / "docs" / "CrfOpcodeSemantics.md"

MARKERS = (
    b"\x09\x00\xf8",
    b"\x09\x00\xf9",
    b"\x07\x00\xf8",
    b"\x07\x00\xf9",
    b"\x06\x07\x00",
    b"\x05\x07\x00",
)

TAG_NAMES = {0xF8: "glyph_run_f8", 0xF9: "glyph_run_f9"}


def find_markers(data: bytes) -> list[int]:
    hits: list[int] = []
    for i in range(len(data) - 2):
        if data[i : i + 3] in MARKERS:
            hits.append(i)
    return hits


def split_records(data: bytes) -> list[bytes]:
    marks = find_markers(data)
    out: list[bytes] = []
    for idx, off in enumerate(marks):
        end = marks[idx + 1] if idx + 1 < len(marks) else len(data)
        out.append(data[off:end])
    return out


def scan_sub_tags(payload: bytes) -> list[dict]:
    """Find embedded u16+tag triples (e.g. 03 00 f9, 05 00 fa) inside a record."""
    subs: list[dict] = []
    for i in range(len(payload) - 2):
        u16 = struct.unpack_from("<H", payload, i)[0]
        if u16 > 512:
            continue
        tag = payload[i + 2]
        if tag in (0xF8, 0xF9, 0xFA, 0xFB, 0xFC, 0xFD, 0xFE, 0xFF):
            subs.append({"off": i, "u16": u16, "tag": hex(tag)})
    return subs[:40]


def decode_record(chunk: bytes) -> dict:
    u16 = struct.unpack_from("<H", chunk, 0)[0] if len(chunk) >= 2 else 0
    tag = chunk[2] if len(chunk) >= 3 else 0
    payload = chunk[3:]
    subs = scan_sub_tags(payload)
    sub_tag_counts = Counter(s["tag"] for s in subs)
    return {
        "prefix_u16": u16,
        "tag": hex(tag),
        "tag_name": TAG_NAMES.get(tag),
        "length": len(chunk),
        "payload_len": len(payload),
        "payload_head_hex": payload[:32].hex(),
        "embedded_subtags": subs[:12],
        "embedded_tag_counts": dict(sub_tag_counts),
    }


def main() -> int:
    fonts: list[dict] = []
    global_sub_tags: Counter[str] = Counter()

    for path in sorted(get_data_dir().glob("*.crf")):
        cf = CrfFont.load(path)
        recs = split_records(cf.section1)
        decoded = [decode_record(r) for r in recs]
        for d in decoded:
            for t, n in d.get("embedded_tag_counts", {}).items():
                global_sub_tags[t] += n
        fonts.append(
            {
                "file": path.name,
                "section1_len": len(cf.section1),
                "record_count": len(decoded),
                "records_sample": decoded[:6],
                "tag_stats": dict(Counter(d["tag_name"] for d in decoded if d.get("tag_name"))),
            }
        )

    payload = {
        "hypothesis": {
            "record_header": "u16 prefix (7|9) + u8 tag (F8|F9)",
            "payload": "opaque; often contains nested u16+tag runs (FA/FB/FC…)",
            "exe_parse": "Font load @ 0x7F8A0 uses shared stream readers @ 0x705D0/0x70670 (see FontLoad.md)",
        },
        "global_embedded_subtags": dict(global_sub_tags.most_common(20)),
        "fonts": fonts,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md_lines = [
        "# `.crf` section-1 opcode semantics",
        "",
        "**Scripts:** `crf_opcode_trace.py`, `crf_record_decode.py`",
        f"**Artifacts:** `crf_opcode_trace.json`, `{OUT.name}`",
        "",
        "Container: [DataFileFormats.md](DataFileFormats.md) / `crf_font.py`.",
        "",
        "## Record envelope (verified scan)",
        "",
        "| Field | Size | Notes |",
        "|-------|------|-------|",
        "| `prefix_u16` | 2 | Usually `7` or `9` (variant / BMFont-like size class) |",
        "| `tag_byte` | 1 | `0xF8` = `glyph_run_f8`, `0xF9` = `glyph_run_f9` |",
        "| `payload` | rest | Nested `u16` + tag bytes (`0xFA`–`0xFF` observed inside `F9` runs) |",
        "",
        "## Embedded sub-tags (inside `F9` payloads, `quip.crf` sample)",
        "",
    ]
    for tag, count in global_sub_tags.most_common(12):
        md_lines.append(f"- `{tag}`: {count} hits in scanned records")
    md_lines.extend(
        [
            "",
            "## Exe: not a separate VM",
            "",
            "`.crf` files are read via **`Font_LoadOrInit` @ `0x7F8A0`** using the **same binary stream layer** as saves",
            "(`ReadU8` @ `0x705D0`, `ReadU32` @ `0x70320`, `ReadF32` @ `0x70670` — [SaveGhidraCrossref.md](SaveGhidraCrossref.md)).",
            "Section-1 **glyph records are not interpreted in a second pass** at load time in the traced path;",
            "the game loads the file into a ~`0x11810`-byte heap object and consumes the **16-byte header** via stream readers @ `0x7FA90`–`0x7FC44`.",
            "",
            "See [FontLoad.md](FontLoad.md) for path build + Frida hooks.",
            "",
        ]
    )
    OUT_MD.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
