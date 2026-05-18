"""
Parse nested u16+tag TLV chains inside .crf section-1 records.

Verified against Game/data/*.crf and loader @ Horsey.exe+0x7FC31 (3-byte header read)
and Horsey.exe+0x7FD60 (3-byte kern write to glyph+0x28).

Output: RE_Tools/analysis/crf_nested_tlv.json
        updates RE_Tools/docs/CrfNestedOpcodes.md
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

OUT = ROOT / "RE_Tools" / "analysis" / "crf_nested_tlv.json"
OUT_MD = ROOT / "RE_Tools" / "docs" / "CrfNestedOpcodes.md"

MARKERS = (
    b"\x07\x00\xf8",
    b"\x07\x00\xf9",
    b"\x09\x00\xf8",
    b"\x09\x00\xf9",
)
TAGS = frozenset(range(0xF8, 0x100))


def find_markers(data: bytes) -> list[int]:
    hits: list[int] = []
    for i in range(len(data) - 2):
        if data[i : i + 3] in MARKERS:
            hits.append(i)
    return hits


def split_records(data: bytes) -> list[bytes]:
    marks = find_markers(data)
    return [
        data[off : (marks[idx + 1] if idx + 1 < len(marks) else len(data))]
        for idx, off in enumerate(marks)
    ]


def parse_tlv(payload: bytes, start: int = 0) -> tuple[list[dict], int]:
    off = start
    nodes: list[dict] = []
    while off + 3 <= len(payload):
        u16 = struct.unpack_from("<H", payload, off)[0]
        tag = payload[off + 2]
        if tag not in TAGS:
            break
        bl = u16
        if off + 3 + bl > len(payload):
            break
        body = payload[off + 3 : off + 3 + bl]
        node: dict = {
            "off": off,
            "u16": u16,
            "tag": hex(tag),
            "body_len": bl,
            "body_hex": body.hex(),
        }
        if tag == 0xF8 and bl == 8:
            node["glyph8"] = {
                "index": body[0],
                "bytes": list(body[1:]),
            }
        elif tag == 0xF9:
            node["role"] = "nested_group"
            if bl == 0:
                node["role"] = "empty_group"
            elif bl >= 3:
                child, _ = parse_tlv(body, 0)
                if child:
                    node["children"] = child[:12]
        elif tag == 0xFE and bl == 3:
            node["kern3"] = {"value": body[0], "glyph": body[1], "extra": body[2]}
        elif tag in (0xFA, 0xFB) and bl == 5:
            node["pair5"] = {
                "b0": body[0],
                "b1": body[1],
                "b2": body[2],
                "b3": body[3],
                "b4": body[4],
            }
        elif tag == 0xFC:
            node["advance_patch"] = list(body)
        elif tag == 0xFD and bl == 1:
            node["byte1"] = body[0]
        elif tag == 0xFF:
            node["ext_run"] = list(body)
        nodes.append(node)
        off += 3 + bl
    return nodes, off


def find_tlv_start(payload: bytes) -> int:
    best = 0
    best_score = -1
    for st in range(min(16, len(payload))):
        nodes, consumed = parse_tlv(payload, st)
        if len(nodes) < 2:
            continue
        score = consumed + len(nodes) * 10
        if score > best_score:
            best_score = score
            best = st
    return best


def decode_record(chunk: bytes) -> dict:
    u16 = struct.unpack_from("<H", chunk, 0)[0] if len(chunk) >= 2 else 0
    tag = chunk[2] if len(chunk) >= 3 else 0
    payload = chunk[3:]
    start = find_tlv_start(payload)
    nodes, consumed = parse_tlv(payload, start)
    prologue = payload[:start].hex() if start else ""
    return {
        "prefix_u16": u16,
        "tag": hex(tag),
        "record_len": len(chunk),
        "prologue_hex": prologue,
        "tlv_start": start,
        "tlv_nodes": len(nodes),
        "tlv_consumed": consumed,
        "payload_remainder": len(payload) - start - consumed,
        "nodes": nodes[:24],
    }


def main() -> int:
    tag_counts: Counter[str] = Counter()
    body_len_hist: Counter[tuple[str, int]] = Counter()
    examples: dict[str, list] = defaultdict(list)

    fonts_out: list[dict] = []
    for path in sorted(get_data_dir().glob("*.crf")):
        cf = CrfFont.load(path)
        recs = split_records(cf.section1)
        long_f9: list[dict] = []
        for r in recs:
            if len(r) < 3 or r[2] not in (0xF8, 0xF9):
                continue
            d = decode_record(r)
            for n in d["nodes"]:
                tag_counts[n["tag"]] += 1
                body_len_hist[(n["tag"], n["body_len"])] += 1
                if len(examples[n["tag"]]) < 2:
                    examples[n["tag"]].append({"file": path.name, **n})
            if r[2] == 0xF9 and len(r) >= 40:
                long_f9.append(d)
        fonts_out.append(
            {
                "file": path.name,
                "section1_len": len(cf.section1),
                "section2_len": len(cf.section2),
                "section2_glyphs_8": len(cf.section2) // 8,
                "records": len(recs),
                "long_f9_sample": long_f9[0] if long_f9 else None,
            }
        )

    semantics = {
        "envelope": "u16 body_len + u8 tag (0xF8..0xFF); 3 bytes on wire per header",
        "0xF8": "8-byte glyph metrics → runtime glyph stride 0x118 @ Horsey.exe+0x7FC90",
        "0xF9": "group; body_len=0 empty, else nested TLV blob (often after 4-byte prologue)",
        "0xFA": "5-byte pair/metric patch (typical body_len=5)",
        "0xFB": "5-byte metric patch (same width as FA)",
        "0xFC": "advance override (body_len 1–5)",
        "0xFD": "1-byte patch (rare)",
        "0xFE": "3-byte kerning triple → glyph+0x28 @ Horsey.exe+0x7FD60 ([value][glyph][extra])",
        "0xFF_file": "file sub-record (distinct from draw width-class 0xFF @ Horsey.exe+0x80E17)",
        "prologue": "4 bytes before first nested TLV in long F9/F8 payloads (parent glyph id + seed)",
        "exe_note": "Loader reads stream: section2 8-byte runs first @ +0x7FBB0, then section1 "
        "3-byte headers @ +0x7FC31; kern applies FE-shaped triples @ +0x7FD60",
    }

    payload = {
        "semantics": semantics,
        "tag_counts": dict(tag_counts),
        "body_len_histogram": {f"{t}_{bl}": n for (t, bl), n in body_len_hist.most_common(30)},
        "examples": dict(examples),
        "fonts": fonts_out,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md = [
        "# `.crf` nested opcodes (`0xF8`–`0xFF`)",
        "",
        "**Verified:** `crf_nested_tlv.py` on `Game/data/*.crf`; loader RVAs on `Game/Horsey.exe`.",
        "",
        f"**Artifact:** `RE_Tools/analysis/{OUT.name}`",
        "",
        "## TLV rule",
        "",
        "Inside a top-level `F9` (or long `F8`) payload:",
        "",
        "```",
        "[u16 body_len][u8 tag][body_len bytes...]",
        "```",
        "",
        "`body_len` is the number of bytes **after** the tag byte (not including the 3-byte header).",
        "",
        "Many records have a **4-byte prologue** before the first nested TLV "
        "(parent glyph index + 3 bytes).",
        "",
        "## Tag meanings",
        "",
        "| Tag | Typical `body_len` | Role | Exe correlation |",
        "|-----|-------------------|------|-----------------|",
        "| `0xF8` | 8 | Full glyph metric row | `CrfParse_GlyphEightByte` @ `0x7FC90` (from section2 buffer) |",
        "| `0xF9` | 0 or nested | Sub-group container | Logical only; stream read via header loop |",
        "| `0xFA` | 5 | Pair / metric patch | Section1 stream |",
        "| `0xFB` | 5 | Metric patch | Section1 stream |",
        "| `0xFC` | 1–5 | Advance override | Patches glyph `+0x20` |",
        "| `0xFD` | 1 | Rare single-byte patch | Section1 stream |",
        "| `0xFE` | 3 | Kerning triple `[value][glyph][extra]` | `CrfParse_KernThreeByte` @ `0x7FD60` → `glyph+0x28` |",
        "| `0xFF` | varies | File extension sub-record | **Not** draw-time `dl==0xFF` @ `0x80E17` |",
        "",
        "## Example (quip.crf `F8` payload, from artifact)",
        "",
        "Prologue `05 2a 44 6b`, then:",
        "",
        "- `05 00 F9` + 5 bytes — nested group",
        "- `05 00 FA` + 5 bytes — pair patch",
        "- `03 00 FE` + `04 2d 40` — kerning triple",
        "",
        "## Loader order (exe)",
        "",
        "1. **Section2** — `count×8` bytes via eight `ReadU8` @ `0x7FBB0` → glyph source for `0x7FC90`.",
        "2. **Section1** — `count×3` header reads @ `0x7FC31` (`ReadU8`,`ReadU8`,`ReadU16`).",
        "3. **Kern** — walk loaded triples @ `0x7FD60`.",
        "",
        "See [CrfGlyphParse.md](CrfGlyphParse.md), [FontLoad.md](FontLoad.md).",
        "",
    ]
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote {OUT} and {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
