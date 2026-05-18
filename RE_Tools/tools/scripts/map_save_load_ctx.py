"""
Save_Load @ 0x6E2B0 — mirror ctx row/slot reads (pairs with Save_Write loops).

Verified Capstone Horsey.exe:
  Write 0x6DD80 / 0x6DDB0 — save_field_layout.json
  Read  0x6E470 / 0x6E4A0 — ReadU8/ReadU32 @ 0x70620/0x70320

Output: RE_Tools/analysis/save_ctx_load_semantics.json
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_64, Cs

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
from paths import get_exe_path  # noqa: E402

OUT = ROOT / "RE_Tools" / "analysis" / "save_ctx_load_semantics.json"
LAYOUT = ROOT / "RE_Tools" / "analysis" / "save_field_layout.json"
DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
IMAGE_BASE = 0x140000000


def disasm_range(pe, raw: bytes, rva: int, size: int) -> list[str]:
    off = pe.get_offset_from_rva(rva)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    return [
        f"{i.address - IMAGE_BASE:06X}: {i.mnemonic} {i.op_str}"
        for i in md.disasm(raw[off : off + size], IMAGE_BASE + rva)
    ]


def load_disk_rows() -> list[dict]:
    layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
    dump = DUMP.read_bytes()
    rows: list[dict] = []
    for f in layout["fields"]:
        note = f.get("note") or ""
        if "row" not in note:
            continue
        idx = int(note.split("row")[1].split()[0])
        while len(rows) <= idx:
            rows.append({"index": idx})
        fo = f["file_offset"]
        if "field-0x34" in note:
            rows[idx]["field_m34_u32"] = struct.unpack_from("<I", dump, fo)[0]
            rows[idx]["ctx_m34"] = hex(0x298 + idx * 4)
        elif "field+0" in note:
            rows[idx]["field_0_u32"] = struct.unpack_from("<I", dump, fo)[0]
            rows[idx]["ctx_0"] = hex(0x2CC + idx * 4)
    return rows


def row_role(r: dict) -> dict:
    a, b = r.get("field_m34_u32"), r.get("field_0_u32")
    role = "opaque"
    if a in (0xFFFFFFFF, 0xFFFFFF01) and b in (0xFFFFFFFF, 0):
        role = "sentinel_padding"
    elif a == 0xFF and b == 0:
        role = "byte_ff_prefix"
    elif b and b < 0x10000:
        role = "small_scalar_b"
    elif a == 0xFFFFFF:
        role = "rgb_mask"
    return {
        **r,
        "load_read": "ReadU32 @ [rbx-0x34] then [rbx] (0x6E4A0)",
        "disk_role": role,
    }


def main() -> int:
    pe = pefile.PE(str(get_exe_path()))
    raw = get_exe_path().read_bytes()
    rows = [row_role(r) for r in load_disk_rows()]

    report = {
        "save_load_entry": "0x6E2B0",
        "ctx_register": "rsi",
        "slot_read_loop": {
            "rva": "0x6E470",
            "count": 6,
            "pattern": "ReadU8/+5, ReadU32/+0, ReadU8/+4; rbx+=8",
            "disasm": disasm_range(pe, raw, 0x6E470, 0x30),
        },
        "row_read_loop": {
            "rva": "0x6E4A0",
            "count": 13,
            "pattern": "ReadU32 [rbx-0x34], ReadU32 [rbx]; rbx+=4",
            "disasm": disasm_range(pe, raw, 0x6E4A0, 0x28),
        },
        "post_footer_load_uses": {
            "0x6EA57": "movss [rsi+0x394] — camera/world vec from loaded footer panel",
            "0x6EA74": "mov [rsi+0x25c], 0x10 — runtime default after footer read (not disk u32)",
            "0x6EA16": "uses [rsi+0x300] active UI/world object ptr",
        },
        "rows13_disk": rows,
        "note": "Rows are read back on load before grid/nested; gameplay may only use subset (footer path touches 0x394/0x398).",
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
