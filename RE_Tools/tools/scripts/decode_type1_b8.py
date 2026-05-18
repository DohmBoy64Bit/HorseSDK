"""
Decode main-nested b8 type-1 wire blob (vtable+0x48 @ Horsey.exe+0x102DC0 / +0x102E20).

Verified Capstone on Game/Horsey.exe:
  Write @ 0x102DC0: packed u8 (0x6D8C0), WriteU32 x3 @ +0xA0/+0xA4/+0xA8,
                   WriteU8 @ +0xAD, +0xAC
  Read  @ 0x102E20: inverse via 0x6D960 / ReadU32 / ReadU8

Sample payload @ save_buffer_dump.bin file 0xDEE6 (57 B after u32 type tag).

Output: RE_Tools/analysis/save_type1_b8.json
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "scripts"))

from nested_b8_codec import unpack_type0_packed  # noqa: E402

OUT = ROOT / "RE_Tools" / "analysis" / "save_type1_b8.json"
DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
TYPE1_FILE_OFF = 0xDEE6
TYPE1_WIRE_LEN = 57


def decode_type1_payload(payload: bytes) -> dict:
    if len(payload) < 15:
        return {"error": "too_short", "len": len(payload)}
    packed = payload[0]
    flags = unpack_type0_packed(packed)
    u_a0, u_a4, u_a8 = struct.unpack_from("<III", payload, 1)
    b_ad, b_ac = payload[13], payload[14]
    tail = payload[15:]
    return {
        "wire_bytes": len(payload),
        "active_bytes": 15,
        "tail_zero_pad": len(tail),
        "packed_u8": packed,
        "packed_flags": flags,
        "object_offsets": {
            "+0xA0_u32": u_a0,
            "+0xA4_u32": u_a4,
            "+0xA8_u32": u_a8,
            "+0xAD_u8": b_ad,
            "+0xAC_u8": b_ac,
        },
        "interpretation": {
            "+0xA0": "linear_tile_index (7936 = row 19 col 336 on 400-wide horsey.tmx)",
            "+0xA4": "secondary dword (0 in sample)",
            "+0xA8": "tertiary dword (0 in sample)",
            "+0xAD": "byte flag A",
            "+0xAC": "byte flag B",
            "packed": "shared type-0 bitfield header (dword_38, flag_10, flag_11)",
        },
        "disasm": {
            "write": "0x102DC0",
            "read": "0x102E20",
            "ctor_alloc": "0x101850 (0xB0 bytes) when type tag==1 @ 0x6D75D",
        },
    }


def main() -> int:
    dump = DUMP.read_bytes()
    payload = dump[TYPE1_FILE_OFF : TYPE1_FILE_OFF + TYPE1_WIRE_LEN]
    report = {
        "file_offset": TYPE1_FILE_OFF,
        "hex": payload.hex(),
        "decoded": decode_type1_payload(payload),
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} a0={report['decoded']['object_offsets']['+0xA0_u32']:#x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
