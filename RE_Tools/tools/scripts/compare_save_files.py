"""
Compare two on-disk saves: ctx rows, footer extra, main nested header.

Default: RE_Tools/analysis/save_buffer_dump.bin vs Game/save/save1.dat.prev

Uses save_field_layout.json offsets (works even when format version / size differs).

Output: RE_Tools/analysis/save_compare.json
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "scripts"))
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))

from paths import get_game_dir  # noqa: E402

OUT = ROOT / "RE_Tools" / "analysis" / "save_compare.json"
LAYOUT = ROOT / "RE_Tools" / "analysis" / "save_field_layout.json"
FOOTER_OFF = 0x31B19
FOOTER_BYTES = 841
FOOTER_EXTRA_REL = 833
MAIN_OFF = 0xDECB
DUMP_A = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
SAVE_B = get_game_dir() / "save" / "save1.dat.prev"


def read_u32(d: bytes, off: int) -> int | None:
    if off + 4 > len(d):
        return None
    return struct.unpack_from("<I", d, off)[0]


def footer_extra(blob: bytes, base: int) -> dict | None:
    if base + FOOTER_EXTRA_REL + 7 > len(blob):
        return None
    ex = blob[base + FOOTER_EXTRA_REL : base + FOOTER_EXTRA_REL + 7]
    return {
        "dword_25c": struct.unpack_from("<I", ex, 0)[0],
        "byte_261": ex[4],
        "byte_262": ex[5],
        "byte_263": ex[6],
        "hex": ex.hex(),
    }


def ctx_rows_from_layout(dump: bytes) -> list[dict]:
    layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
    rows: list[dict] = []
    for f in layout["fields"]:
        note = f.get("note") or ""
        if "row" not in note:
            continue
        idx = int(note.split("row")[1].split()[0])
        while len(rows) <= idx:
            rows.append({"index": idx})
        fo = f["file_offset"]
        if fo + 4 > len(dump):
            rows[idx]["missing"] = True
            continue
        if "field-0x34" in note:
            rows[idx]["field_m34_u32"] = read_u32(dump, fo)
        elif "field+0" in note:
            rows[idx]["field_0_u32"] = read_u32(dump, fo)
    return rows


def main_nested_header(dump: bytes) -> dict:
    if MAIN_OFF + 32 > len(dump):
        return {"error": "truncated"}
    nl = read_u32(dump, MAIN_OFF) or 0
    name = dump[MAIN_OFF + 4 : MAIN_OFF + 4 + nl].decode("utf-8", errors="replace")
    base = MAIN_OFF + 4 + nl
    return {
        "name": name,
        "ptr_item_count": read_u32(dump, base),
        "merge_index": read_u32(dump, base + 4),
        "b8_vector_count": read_u32(dump, base + 8),
    }


def summarize(path: Path) -> dict:
    data = path.read_bytes()
    ver = read_u32(data, 0)
    return {
        "path": str(path),
        "size": len(data),
        "format_version": ver,
        "main_nested": main_nested_header(data),
        "footer_extra": footer_extra(data, FOOTER_OFF) if len(data) >= FOOTER_OFF + FOOTER_BYTES else None,
        "ctx_rows": ctx_rows_from_layout(data),
    }


def diff_rows(a: list[dict], b: list[dict]) -> list[dict]:
    out = []
    n = max(len(a), len(b))
    for i in range(n):
        ra = a[i] if i < len(a) else {}
        rb = b[i] if i < len(b) else {}
        if ra.get("missing") or rb.get("missing"):
            out.append({"row": i, "note": "offset past EOF on one file", "a": ra, "b": rb})
            continue
        if ra.get("field_m34_u32") != rb.get("field_m34_u32") or ra.get("field_0_u32") != rb.get(
            "field_0_u32"
        ):
            out.append({"row": i, "a": ra, "b": rb})
    return out


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--a", type=Path, default=DUMP_A)
    ap.add_argument("--b", type=Path, default=SAVE_B)
    args = ap.parse_args()
    if not args.a.is_file():
        print(f"Missing {args.a}")
        return 1
    if not args.b.is_file():
        print(f"Missing second save {args.b}")
        return 1

    sa = summarize(args.a)
    sb = summarize(args.b)
    report = {
        "a": sa,
        "b": sb,
        "size_delta": sb["size"] - sa["size"],
        "format_version_match": sa.get("format_version") == sb.get("format_version"),
        "ctx_row_diffs": diff_rows(sa["ctx_rows"], sb["ctx_rows"]),
        "footer_extra_match": sa.get("footer_extra") == sb.get("footer_extra"),
        "main_nested_match": sa.get("main_nested") == sb.get("main_nested"),
        "note": "Layout offsets from save_field_layout.json (capture A); B may differ size",
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        f"Wrote {OUT} sizes {sa['size']} vs {sb['size']} "
        f"ctx_diffs={len(report['ctx_row_diffs'])} footer_match={report['footer_extra_match']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
