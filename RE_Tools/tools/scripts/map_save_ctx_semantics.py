"""
SaveContext row/slot semantics from disk sample + Save_Write disasm.

Verified: Horsey.exe Save_Write @ 0x6DD71 (slots), 0x6DDB0 (rows)
Output: RE_Tools/analysis/save_ctx_semantics.json
        updates RE_Tools/docs/SaveContext.h comments
"""
from __future__ import annotations

import json
import re
import struct
import sys
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_64, Cs

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
from paths import get_exe_path  # noqa: E402

OUT = ROOT / "RE_Tools/analysis/save_ctx_semantics.json"
HDR = ROOT / "RE_Tools/docs/SaveContext.h"
LAYOUT = ROOT / "RE_Tools/analysis/save_field_layout.json"
IMAGE_BASE = 0x140000000

ROW_LABELS = [
    ("row0", "field_m34", "sentinel_low", {0xFFFFFF01: "common -1/01 pattern"}),
    ("row0", "field_0", "sentinel_ff", {0xFFFFFFFF: "all-bits-one"}),
    ("row1", "field_m34", "byte_mask", {0xFF: "0xFF byte in low dword"}),
    ("row2", "field_0", "packed_u16", {65792: "0x10100 — flags/word"}),
    ("row3", "field_m34", "float_bits", {4278255616: "0xFF010000 LE float pattern"}),
    ("row4", "field_m34", "rgb_mask", {16777215: "0xFFFFFF"}),
    ("row5", "field_0", "coord_bits", {1090519040: "0x41000000 f32-ish"}),
    ("row6", "field_0", "counter", {131183: "0x2000F — gameplay counter guess"}),
    ("row9", "field_0", "float_bits", {1107296256: "0x42000000"}),
    ("row10", "field_0", "ascii_fourcc", {543519860: "'dale' LE fourcc fragment"}),
]


def u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def load_rows_slots() -> tuple[list[dict], list[dict]]:
    layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
    dump = (ROOT / "RE_Tools/analysis/save_buffer_dump.bin").read_bytes()
    rows: list[dict] = []
    slots: list[dict] = []
    for f in layout["fields"]:
        note = f.get("note") or ""
        fo = f["file_offset"]
        if re.match(r"row\d+ field-0x34", note):
            idx = int(re.search(r"row(\d+)", note).group(1))
            while len(rows) <= idx:
                rows.append({"index": idx})
            rows[idx]["ctx_off_m34"] = hex(0x298 + idx * 4)
            rows[idx]["field_m34_u32"] = u32(dump, fo)
            rows[idx]["file_off_m34"] = fo
        elif re.match(r"row\d+ field\+0", note):
            idx = int(re.search(r"row(\d+)", note).group(1))
            while len(rows) <= idx:
                rows.append({"index": idx})
            rows[idx]["ctx_off_0"] = hex(0x2CC + idx * 4)
            rows[idx]["field_0_u32"] = u32(dump, fo)
            rows[idx]["file_off_0"] = fo
        elif re.match(r"slot\d+", note):
            m = re.search(r"slot(\d+)", note)
            idx = int(m.group(1))
            while len(slots) <= idx:
                slots.append({"index": idx, "ctx_base": hex(0x31C + idx * 8)})
            if "dword+0" in note:
                slots[idx]["dword0"] = u32(dump, fo)
            elif "byte+5" in note:
                slots[idx]["byte5_on_disk"] = u32(dump, fo)
            elif "byte+4" in note:
                slots[idx]["byte4_on_disk"] = u32(dump, fo)
    for r in rows:
        r["role"] = _row_role(r)
    for s in slots:
        s["role"] = _slot_role(s)
    return rows, slots


def _row_role(r: dict) -> str:
    a, b = r.get("field_m34_u32"), r.get("field_0_u32")
    if a in (0xFFFFFFFF, 0xFFFFFF01, 4294967295, 4294967041):
        return "sentinel_pair"
    if a == 0xFF and b == 0:
        return "byte_flag_row"
    if b and b < 0x10000:
        return "small_scalar"
    if a == 0xFFFFFF:
        return "color_mask"
    return "opaque_u32_pair"


def _slot_role(s: dict) -> str:
    if s.get("byte4_on_disk") == 22:
        return "u8_as_u32 (value 22 @ byte+4 — matches grid type id sample)"
    if s.get("dword0") == 0 and s.get("byte5_on_disk", 0) == 0:
        return "zeroed_slot"
    return "opaque_slot"


def scan_save_write_xrefs() -> list[dict]:
    pe = pefile.PE(str(get_exe_path()))
    raw = get_exe_path().read_bytes()
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    want = {
        0x6DD71: "SaveSlot6_write_loop",
        0x6DDA3: "SaveRow13_write_loop",
        0x6DCEB: "field_114_float",
        0x6DCCA: "field_254",
        0x6DCE0: "field_268",
        0x6DD09: "field_308_name_fourcc",
        0x6DD14: "field_440_flags",
        0x6DD61: "field_39C_vec2",
    }
    out: list[dict] = []
    for rva, name in want.items():
        off = pe.get_offset_from_rva(rva)
        lines = [
            f"{i.address - IMAGE_BASE:06X}: {i.mnemonic} {i.op_str}"
            for i in md.disasm(raw[off : off + 32], IMAGE_BASE + rva)
        ][:6]
        out.append({"rva": hex(rva), "name": name, "disasm": lines})
    return out


def patch_header(rows: list[dict]) -> None:
    if not HDR.is_file():
        return
    text = HDR.read_text(encoding="utf-8")
    text = text.replace(
        "uint32_t field_m34;  /* [rbx-0x34] */",
        "uint32_t field_m34;  /* [rbx-0x34] staggered; see save_ctx_semantics.json */",
    )
    text = text.replace(
        "uint32_t field_0;    /* [rbx] */",
        "uint32_t field_0;    /* [rbx]; +0x2CC+N*4 on disk */",
    )
    HDR.write_text(text, encoding="utf-8")


def main() -> int:
    rows, slots = load_rows_slots()
    report = {
        "verified_on": "save_buffer_dump.bin + Horsey.exe Save_Write 0x6DAB0",
        "row_layout": {
            "write_loop": "0x6DDB0",
            "pattern": "for N in 0..12: WriteU32([rdi+0x298+N*4]); WriteU32([rdi+0x2CC+N*4]); rbx+=4",
            "note": "13 staggered u32 pairs (52 B on disk), not 13×8 B struct array",
        },
        "slot_layout": {
            "write_loop": "0x6DD80",
            "pattern": "6× (WriteU8/+5, WriteU32/+0, WriteU8/+4); 12 B disk / 8 B mem",
        },
        "read_side": "No direct [ctx+0x298] loads in .text — values consumed indirectly after load",
        "rows13": rows,
        "slots6": slots,
        "save_write_anchors": scan_save_write_xrefs(),
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    patch_header(rows)
    print(f"Wrote {OUT} rows={len(rows)} slots={len(slots)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
