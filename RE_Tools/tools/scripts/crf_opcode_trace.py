"""
Walk .crf section 1 glyph streams and classify record prefixes.

Verified container: crf_font.py (16-byte header + section1 + section2).
Opcode semantics: frequency + length stats across all Game/data/*.crf.

Output: RE_Tools/analysis/crf_opcode_trace.json
        RE_Tools/docs/CrfOpcodeSemantics.md
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

from paths import get_data_dir, get_exe_path  # noqa: E402
from crf_font import CrfFont  # noqa: E402

OUT_JSON = ROOT / "RE_Tools" / "analysis" / "crf_opcode_trace.json"
OUT_MD = ROOT / "RE_Tools" / "docs" / "CrfOpcodeSemantics.md"

RECORD_MARKERS = (
    b"\x09\x00\xf8",
    b"\x09\x00\xf9",
    b"\x07\x00\xf8",
    b"\x07\x00\xf9",
    b"\x05\x07\x00",
    b"\x06\x07\x00",
)

TAG_NAMES = {
    0xF8: "glyph_run_f8",
    0xF9: "glyph_run_f9",
}


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
                "tag_name": TAG_NAMES.get(tag) if tag is not None else None,
                "head_hex": chunk[: min(24, len(chunk))].hex(),
                "tail_hex": chunk[-8:].hex() if len(chunk) >= 8 else chunk.hex(),
            }
        )
    return records


def scan_section1_opcodes(data: bytes) -> dict:
    """Byte-frequency and 2-byte leaders outside marker records."""
    freq = Counter(data)
    leaders = Counter(data[i : i + 2].hex() for i in range(len(data) - 1))
    return {
        "unique_bytes": len(freq),
        "top_bytes": [(hex(b), n) for b, n in freq.most_common(16)],
        "top_leaders_u16": leaders.most_common(12),
    }


def exe_crf_loader_xrefs() -> dict:
    """Capstone: calls near font path cluster 0xBF200 (phase1_crf_loader.json)."""
    try:
        import pefile
        from capstone import CS_ARCH_X86, CS_MODE_64, Cs
    except ImportError:
        return {"error": "pefile/capstone missing"}

    pe = pefile.PE(str(get_exe_path()))
    raw = Path(get_exe_path()).read_bytes()
    region_lo, region_hi = 0xBF100, 0xBFA00
    off = pe.get_offset_from_rva(region_lo)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    calls = []
    for i in md.disasm(raw[off : off + (region_hi - region_lo)], 0x140000000 + region_lo):
        rva = i.address - 0x140000000
        if i.mnemonic != "call":
            continue
        import re

        m = re.match(r"0x([0-9a-f]+)", i.op_str, re.I)
        if m:
            tgt = int(m.group(1), 16) - 0x140000000
            calls.append({"at": hex(rva), "target": hex(tgt)})
    return {"region": [hex(region_lo), hex(region_hi)], "calls": calls[:40]}


def analyze_font(path: Path) -> dict:
    c = CrfFont.load(path)
    s1 = c.section1
    marks = find_markers(s1)
    prefix_counts = Counter(s1[i : i + 3].hex() for i in marks)
    records = split_records(s1) if s1 else []
    len_by_tag = defaultdict(list)
    u16_by_tag = defaultdict(Counter)
    for r in records:
        if r["tag_byte"] is not None:
            len_by_tag[r["tag_byte"]].append(r["length"])
            u16_by_tag[r["tag_byte"]][r["prefix_u16"]] += 1
    tag_stats = {}
    for tag, lengths in len_by_tag.items():
        tag_stats[hex(tag)] = {
            "name": TAG_NAMES.get(tag, "unknown"),
            "count": len(lengths),
            "len_min": min(lengths),
            "len_max": max(lengths),
            "len_avg": sum(lengths) / len(lengths),
            "prefix_u16": u16_by_tag[tag].most_common(6),
        }
    return {
        "file": path.name,
        "header": {
            "byte0": c.header.byte0,
            "line_height_guess": c.header.byte1_line_height_guess,
            "field_a": c.header.field_a,
            "section1_bytes": c.header.section1_bytes,
            "field_c": c.header.field_c,
        },
        "section1_len": len(s1),
        "section2_len": len(c.section2),
        "marker_count": len(marks),
        "top_prefixes": prefix_counts.most_common(12),
        "tag_stats": tag_stats,
        "opcode_scan": scan_section1_opcodes(s1[: min(4096, len(s1))]),
        "records_sample": records[:15],
        "records_total": len(records),
    }


def write_md(report: dict) -> None:
    lines = [
        "# `.crf` section-1 opcode semantics (Capstone + data scan)",
        "",
        f"**Script:** `crf_opcode_trace.py` · **Artifact:** `{OUT_JSON.relative_to(ROOT)}`",
        "",
        "Container layout: [DataFileFormats.md](DataFileFormats.md) / `crf_font.py`.",
        "",
        "## Record markers (verified scan)",
        "",
        "Records begin with **u16 length** + **tag byte** (`0xF8` / `0xF9`):",
        "",
        "| Prefix (hex) | Tag |",
        "|--------------|-----|",
        "| `09 00 f8` | `0xF8` glyph_run_f8 |",
        "| `09 00 f9` | `0xF9` glyph_run_f9 |",
        "| `07 00 f8/f9` | shorter variant |",
        "",
        "## Per-font tag stats",
        "",
    ]
    for f in report["fonts"]:
        lines.append(f"### `{f['file']}`")
        lines.append("")
        for tag, st in f.get("tag_stats", {}).items():
            lines.append(
                f"- **{tag}** `{st['name']}`: {st['count']} records, "
                f"len {st['len_min']}–{st['len_max']} (avg {st['len_avg']:.1f})"
            )
        lines.append("")

    if report.get("exe_loader"):
        lines.extend(["## Exe loader cluster (`0xBF200`)", ""])
        for c in report["exe_loader"].get("calls", [])[:15]:
            lines.append(f"- `{c['at']}` → `{c['target']}`")
    lines.extend(
        [
            "",
            "## Status",
            "",
            "Interpreter @ font draw path **UNVERIFIED** — marker/record boundaries only.",
            "Next: hook `0x6F3C0` / CRF loader callees under Frida when drawing text.",
            "",
        ]
    )
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    data_dir = get_data_dir()
    fonts = [analyze_font(p) for p in sorted(data_dir.glob("*.crf"))]
    report = {
        "verification": "Marker scan + record split on all Game/data/*.crf",
        "fonts": fonts,
        "exe_loader": exe_crf_loader_xrefs(),
        "aggregate_prefixes": dict(
            Counter(
                p for f in fonts for p, _ in f.get("top_prefixes", [])
            ).most_common(20)
        ),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_md(report)
    print(f"Wrote {OUT_JSON} and {OUT_MD}")
    for f in fonts:
        print(f"  {f['file']}: {f['marker_count']} markers, {f['records_total']} records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
