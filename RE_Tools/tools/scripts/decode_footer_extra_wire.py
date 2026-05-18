"""
Locate FooterExtra_Write 7-byte tail in save1.dat footer blob.

Verified Horsey.exe+0x1017C0:
  WriteU32 [obj+0x25C]; WriteU8 [obj+0x261..0x263]
Called after WriteNestedSave @ 0x6E103.

Sample: footer blob rel 833 = 01 00 00 00 00 00 00 (u32=1 + 3 zero u8)

Output: RE_Tools/analysis/save_footer_extra_wire.json
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "RE_Tools" / "analysis" / "save_footer_extra_wire.json"
DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
FOOTER_OFF = 0x31B19
FOOTER_BYTES = 841
EXTRA_REL = 833


def main() -> int:
    d = DUMP.read_bytes()
    blob = d[FOOTER_OFF : FOOTER_OFF + FOOTER_BYTES]
    extra = blob[EXTRA_REL : EXTRA_REL + 7]
    u32 = struct.unpack_from("<I", extra, 0)[0]
    report = {
        "footer_file_offset": FOOTER_OFF,
        "extra_rel_in_footer": EXTRA_REL,
        "extra_file_offset": FOOTER_OFF + EXTRA_REL,
        "bytes_hex": extra.hex(),
        "decoded": {
            "dword_25c": u32,
            "byte_261": extra[4],
            "byte_262": extra[5],
            "byte_263": extra[6],
        },
        "exe": {
            "write": "Horsey.exe+0x1017C0",
            "read": "Horsey.exe+0x101810",
            "call_after": "Horsey.exe+0x6E112 vtable+0xB0",
        },
        "load_runtime": {
            "note": "After load, game sets [ctx+0x25C]=0x10 @ 0x6EA74 — session default, may differ from disk u32=1",
        },
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} extra={extra.hex()} dword_25c={u32}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
