"""
Capstone: CRF section1→glyph table parse inside Font_LoadOrInit tail @ 0x7FA90+.

Outputs:
  RE_Tools/analysis/crf_glyph_parse.json
  RE_Tools/docs/CrfGlyphParse.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "scripts"))

from re_pe_util import disasm_range, load_pe, scan_e8_callers  # noqa: E402

PARSE_REGION = (0x7FAB0, 0x7FE00)
FONT_DRAW = 0x80D10


def main() -> int:
    pe, raw = load_pe()
    lo, hi = PARSE_REGION
    insns = disasm_range(raw, pe, lo, hi - lo)
    payload = {
        "function": "Font_LoadOrInit (CRF parse tail)",
        "parent_rva": "0x7F8A0",
        "parse_region": f"0x{lo:X}-0x{hi:X}",
        "glyph_stride": "0x118",
        "glyph_heap_reserve": "0x11800",
        "loops": [
            {
                "rva": "0x7FBB0",
                "name": "CrfParse_Section2_EightByte",
                "step_bytes": 8,
                "count": "(section2_end - section2_buf) / 8",
                "reads": "8x ReadU8 @ 0x705D0 per entry (offsets 0..7)",
            },
            {
                "rva": "0x7FC31",
                "name": "CrfParse_Section1_ThreeByte",
                "step_bytes": 3,
                "count": "(s1_end - s1_buf) / 3 (rounded)",
                "reads": "ReadU8 + ReadU8 + ReadU16 @ 0x70450",
            },
            {
                "rva": "0x7FC90",
                "name": "CrfParse_GlyphEightByte",
                "step_bytes": 8,
                "maps_to": "font_object + glyph_index * 0x118",
                "field_map": {
                    "byte0": "glyph_index → imul index, 0x118",
                    "byte1": "÷ line_height → float @ glyph+0x10",
                    "byte2": "÷ field → float @ glyph+0x18",
                    "byte1+byte3": "sum ÷ line_height → float @ glyph+0x14",
                    "byte2+byte4": "sum ÷ field → float @ glyph+0x1c",
                    "byte3": "stored @ glyph+0x24",
                    "byte4": "stored @ glyph+0x25",
                    "byte5": "stored @ glyph+0x26",
                    "byte6": "stored @ glyph+0x27",
                    "byte7": "+ header_byte → dword @ glyph+0x20 (advance)",
                },
            },
            {
                "rva": "0x7FD60",
                "name": "CrfParse_KernThreeByte",
                "step_bytes": 3,
                "writes": "byte @ glyph+0x28 for glyph index",
            },
        ],
        "font_draw": {
            "rva": hex(FONT_DRAW),
            "name": "Font_DrawString",
            "callers": len(scan_e8_callers(raw, pe, FONT_DRAW)),
            "notes": "Walks UTF-8/byte string; lookup @ rip+0x262e50; width table @ rip+0x310620; dl==0x20 space",
        },
        "file_record_envelope": {
            "on_disk": "u16 prefix (7|9) + tag F8/F9 + payload (see crf_record_decode.json)",
            "in_exe": "stream reader consumes bytes; 8-byte payload → glyph struct (markers not compared as immediates)",
        },
        "disasm_sample": [
            f"{hex(r)}: {m} {o}" for r, m, o in insns if 0x7FC80 <= r <= 0x7FD90
        ][:35],
    }
    out = ROOT / "RE_Tools" / "analysis" / "crf_glyph_parse.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md = [
        "# CRF glyph parse (inside `Font_LoadOrInit` @ `0x7F8A0`)",
        "",
        "**Verified:** Capstone on `Game/Horsey.exe` — `disasm_crf_glyph_parse.py`",
        "",
        f"**Artifact:** `{out.relative_to(ROOT)}`",
        "",
        "## On-disk vs in-memory",
        "",
        "| Stage | Format |",
        "|-------|--------|",
        "| **File** section1 | Records: `u16` + `0xF8`/`0xF9` + payload ([CrfOpcodeSemantics.md](CrfOpcodeSemantics.md)) |",
        "| **Loader** | Sequential stream read; **8-byte payload** → `0x118`-byte runtime glyph |",
        "",
        "There is **no** `cmp al, 0xF8` in `.text` — tags are consumed as length-prefixed stream bytes, not immediate compares.",
        "",
        "## Parse loops (RVA)",
        "",
        "### 1. Section2 — `0x7FBB0` (8 bytes × N)",
        "",
        "Alloc `count×8` buffer; each entry = eight `ReadU8` calls. Source: section2 blob after header.",
        "",
        "### 2. Section1 — `0x7FC31` (3 bytes × M)",
        "",
        "Triples via `ReadU8`,`ReadU8`,`ReadU16` — auxiliary table (kerning index / char map).",
        "",
        "### 3. Glyphs — `0x7FC90` (8 bytes × G) ← **maps `F9` payload**",
        "",
        "For each 8-byte run at stream cursor `r8`:",
        "",
        "| Byte(s) | → `glyph + 0x118 * index` |",
        "|---------|---------------------------|",
        "| `[0]` | glyph index |",
        "| `[1]` | float @ `+0x10` (÷ line height from header) |",
        "| `[2]` | float @ `+0x18` |",
        "| `[1]+[3]` | float @ `+0x14` |",
        "| `[2]+[4]` | float @ `+0x1c` |",
        "| `[3..6]` | bytes @ `+0x24`..`+0x27` |",
        "| `[7]` + header | dword advance @ `+0x20` |",
        "",
        "**Example** (`quip.crf` record @ +8): `07 00 f9 03 22 17 35 05 …` → eight payload bytes after tag align with this layout (`03` index, metrics follow).",
        "",
        "### 4. Kern — `0x7FD60` (3 bytes × K)",
        "",
        "`[0]` = glyph index, `[1]` → byte @ `glyph+0x28`.",
        "",
        "## Draw — `Font_DrawString` @ `0x80D10`",
        "",
        "- `rcx` = font object (`g_font_*` @ `0x313538`..`0x313548`)",
        "- `r12` = text bytes",
        "- Charset / width: `rip+0x262e50`, `rip+0x310620`",
        "- `dl==0x20` → space (`font+0x2320`); `dl==0xFF` → extended layout path",
        "- Per-glyph advance: `dword [glyph+0x20]`; optional `byte [glyph+0x28]` kerning",
        "",
        "Frida: `frida_font_draw.py`",
        "",
        "See also: [FontLoad.md](FontLoad.md), [FontDraw.md](FontDraw.md)",
        "",
    ]
    doc = ROOT / "RE_Tools" / "docs" / "CrfGlyphParse.md"
    doc.write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
