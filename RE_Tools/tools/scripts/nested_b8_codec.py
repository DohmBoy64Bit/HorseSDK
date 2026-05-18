"""
b8 component serialize @ vtable+0x48 / +0x50 (Horsey.exe).

Verified:
  WriteNestedSave @ 0x6D530 — WriteU32 [obj+8] then vcall +0x48
  ReadNestedSave @ 0x6D6F5 — ReadU32 type; FUN_140070540 returns 0 without advancing when EOF
  Type 0 pack: FUN_14006d8c0 / FUN_14006d960 @ 0x6FEB0 (single u8 header)
  Type 1: FUN_140102dc0 / FUN_140102e20 (vtable @ 0x26B3D0, ctor @ 0x101850)
  Type 2: FUN_1400a30f0 sets [obj+8]=edx; blocks 164 B @ save_buffer_dump 0xDF30+
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Any

from save_stream import SaveStream

TYPE2_BLOCK_BYTES = 164
TYPE2_INNER_BYTES = 40
MAIN_NESTED_B8_BYTES = 1079


@dataclass
class B8Entry:
    type_id: int
    payload: bytes
    decoded: dict[str, Any] = field(default_factory=dict)


def unpack_type0_packed(packed: int) -> dict[str, int]:
    """FUN_14006d960 @ 0x6D973 — unpack first ReadU8."""
    b = packed & 0xFF
    return {
        "packed": b,
        "dword_38": (b & 7) - 1,
        "flag_10": (b >> 3) & 1,
        "flag_11": (b >> 4) & 1,
    }


def pack_type0_packed(dword_38: int, flag_10: int, flag_11: int) -> int:
    """Inverse of FUN_14006d8c0 packed byte before FUN_14006feb0."""
    b = (dword_38 + 1) & 7
    b |= (flag_10 & 1) << 3
    b |= (flag_11 & 1) << 4
    return b & 0xFF


def read_type2_inner(stream: SaveStream) -> dict[str, Any]:
    """
    40 B inner prop inside a type-2 block.

    Layout (sample @ 0xDF30, Horsey.exe type-2 write path):
      +0x00  packed_u8       — type-0 header byte (FUN_14006d8c0)
      +0x01  cell_flag_c     — [obj+0x0C] u8 wire @ 0x6D8EF (same offset as SaveGridCell.flag_c)
      +0x02  grid_cell_type_id — [obj+0x48] @ 0x6D8F8; ctor default 0x17 (23 = GrassLand @ 0x1167B0)
      +0x03  ext_pad_u8      — reserved (full write also has word @ [obj+0x44] @ 0x6D901)
      +0x04  pad8[8]         — zero fill
      +0x0C  coord8[8]       — u8[8] tile key (0x392c… placeholders, not IEEE vec2)
      +0x14  f32[4]          — [obj+0x28..0x34] (FUN_14006ff10)
      +0x24  link_u32        — often 2 (next inner / type tag)
    """
    raw = stream.read_bytes(TYPE2_INNER_BYTES)
    link = struct.unpack_from("<I", raw, 36)[0] if len(raw) >= 40 else 0
    out = unpack_type0_packed(raw[0])
    out.update(
        {
            "cell_flag_c": raw[1],
            "grid_cell_type_id": raw[2],
            "ext_pad_u8": raw[3],
            "byte_obj_0x0C": raw[1],
            "byte_obj_0x48": raw[2],
            "ext_c_u8": raw[1],
            "ext_48_u8": raw[2],
            "pad8_hex": raw[4:12].hex(),
            "coord8_hex": raw[12:20].hex(),
            "f32": list(struct.unpack_from("<ffff", raw, 20)) if len(raw) >= 36 else [],
            "link_u32": link,
            "raw": raw.hex(),
        }
    )
    return out


def write_type2_inner(stream: SaveStream, inner: dict[str, Any]) -> None:
    raw = bytearray(TYPE2_INNER_BYTES)
    packed = inner.get("packed")
    if packed is None:
        packed = pack_type0_packed(
            inner.get("dword_38", 0),
            inner.get("flag_10", 0),
            inner.get("flag_11", 0),
        )
    raw[0] = packed & 0xFF
    raw[1] = inner.get("cell_flag_c", inner.get("byte_obj_0x0C", inner.get("ext_c_u8", 0))) & 0xFF
    raw[2] = (
        inner.get("grid_cell_type_id", inner.get("byte_obj_0x48", inner.get("ext_48_u8", 0)))
        & 0xFF
    )
    raw[3] = inner.get("ext_pad_u8", 0) & 0xFF
    if inner.get("pad8_hex"):
        raw[4:12] = bytes.fromhex(inner["pad8_hex"])[:8].ljust(8, b"\x00")
    if inner.get("coord8_hex"):
        raw[12:20] = bytes.fromhex(inner["coord8_hex"])[:8].ljust(8, b"\x00")
    floats = inner.get("f32", [0.0, 0.0, 0.0, 0.0])
    for i, f in enumerate(floats[:4]):
        struct.pack_into("<f", raw, 20 + i * 4, float(f))
    struct.pack_into("<I", raw, 36, inner.get("link_u32", 2) & 0xFFFFFFFF)
    stream.write_bytes(bytes(raw))


def read_type2_block_at(blob: bytes, offset: int) -> dict[str, Any]:
    stream = SaveStream(blob, offset)
    tag = stream.read_u32()
    inners = [read_type2_inner(stream) for _ in range(4)]
    return {"tag": tag, "inners": inners}


def parse_type0_tail(blob: bytes) -> list[dict[str, Any]]:
    """Each tail byte is one on-disk type-0 packed prop (FUN_14006d8c0 / 0x6FEB0)."""
    return [{"type_id": 0, **unpack_type0_packed(b)} for b in blob]


def decode_type1_payload(payload: bytes) -> dict:
    """
    Type-1 component wire @ 0x102DC0 (15 active bytes + zero pad in sample).

    Layout: packed_u8 | u32@+0xA0 | u32@+0xA4 | u32@+0xA8 | u8@+0xAD | u8@+0xAC
    """
    if len(payload) < 15:
        return {"error": "short", "len": len(payload)}
    import struct

    out = unpack_type0_packed(payload[0])
    u_a0, u_a4, u_a8 = struct.unpack_from("<III", payload, 1)
    out.update(
        {
            "wire_bytes": len(payload),
            "active_bytes": 15,
            "+0xA0_u32": u_a0,
            "+0xA4_u32": u_a4,
            "+0xA8_u32": u_a8,
            "+0xAD_u8": payload[13],
            "+0xAC_u8": payload[14],
            "disasm_write": "0x102DC0",
            "disasm_read": "0x102E20",
        }
    )
    return out


def _type1_payload_end(blob: bytes) -> int:
    for pos in range(4, min(len(blob), 256)):
        if pos + TYPE2_BLOCK_BYTES <= len(blob) and struct.unpack_from("<I", blob, pos)[0] == 2:
            return pos
    return min(61, len(blob))


def parse_b8_blob(blob: bytes, count: int) -> list[B8Entry]:
    stream = SaveStream(blob)
    entries: list[B8Entry] = []

    if stream.remaining() >= 4:
        type_id = stream.read_u32()
        if type_id == 1:
            end = _type1_payload_end(blob)
            payload = blob[4:end]
            entries.append(
                B8Entry(
                    type_id=1,
                    payload=payload,
                    decoded=decode_type1_payload(payload),
                )
            )
            stream.seek(end)
        else:
            stream.seek(0)

    while stream.remaining() >= 4:
        pos = stream.tell()
        tag = struct.unpack_from("<I", blob, pos)[0]
        if tag == 2 and stream.remaining() >= TYPE2_BLOCK_BYTES:
            decoded = read_type2_block_at(blob, pos)
            entries.append(
                B8Entry(
                    type_id=2,
                    payload=blob[pos : pos + TYPE2_BLOCK_BYTES],
                    decoded=decoded,
                )
            )
            stream.seek(pos + TYPE2_BLOCK_BYTES)
            continue
        break

    if stream.tell() < len(blob):
        tail = blob[stream.tell() :]
        t0 = parse_type0_tail(tail)
        entries.append(
            B8Entry(
                type_id=0,
                payload=tail,
                decoded={"type0_entries": t0, "tail_bytes": len(tail)},
            )
        )

    return entries


def summarize_b8_blob(blob: bytes, header_count: int) -> dict[str, Any]:
    """Map in-memory b8 count (343) to on-disk representation."""
    entries = parse_b8_blob(blob, header_count)
    type2_inners = sum(
        len(e.decoded.get("inners", [])) for e in entries if e.type_id == 2
    )
    type0_tail = sum(
        len(e.decoded.get("type0_entries", []))
        for e in entries
        if e.type_id == 0 and "type0_entries" in e.decoded
    )
    on_disk_slots = (
        sum(1 for e in entries if e.type_id == 1)
        + type2_inners
        + type0_tail
    )
    return {
        "header_count": header_count,
        "blob_bytes": len(blob),
        "entries": len(entries),
        "type1_records": sum(1 for e in entries if e.type_id == 1),
        "type2_blocks": sum(1 for e in entries if e.type_id == 2),
        "type2_inners": type2_inners,
        "type0_tail_bytes": type0_tail,
        "on_disk_slots": on_disk_slots,
        "implicit_eof_slots": max(0, header_count - on_disk_slots),
        "disasm": {
            "read_loop": "0x6D6F5",
            "type0_pack": "0x6D8C0",
            "type0_unpack": "0x6D960",
            "type2_ctor": "0x0A30F0",
        },
    }


def encode_b8_blob(entries: list[B8Entry]) -> bytes:
    out = bytearray()
    for ent in entries:
        if ent.type_id == 1:
            out.extend(struct.pack("<I", 1))
            out.extend(ent.payload)
        elif ent.type_id == 2:
            out.extend(ent.payload)
        elif ent.type_id == 0:
            for row in ent.decoded.get("type0_entries", []):
                out.append(row.get("packed", 0) & 0xFF)
            if not ent.decoded.get("type0_entries"):
                out.extend(ent.payload)
    return bytes(out)
