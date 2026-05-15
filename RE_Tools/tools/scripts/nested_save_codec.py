"""
ReadNestedSave @ 0x6D5C0 / WriteNestedSave @ 0x6D440 (Horsey.exe).

Verified: Game/Horsey.exe disasm 0x6D440/0x6D5C0, save_buffer_dump.bin
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Any

from nested_b8_codec import parse_b8_blob
from save_stream import SaveStream

INVENTORY_GENE_OFF = 0x51
MAIN_NESTED_B8_BYTES = 1079
MAIN_NESTED_TAIL_BYTES = 32
TYPE1_FIRST_SIZE = 61
TYPE1_REPEAT_SIZE = 41


@dataclass
class NestedB8Entry:
    type_id: int
    payload: bytes


@dataclass
class NestedSave:
    file_offset: int
    block_size: int | None
    name: str
    ptr_item_count: int
    merge_index: int
    b8_count: int
    raw_block: bytes = b""
    b8_blob: bytes = b""
    b8_entries: list[NestedB8Entry] = field(default_factory=list)
    vec2: tuple[float, float] = (0.0, 0.0)
    gene_flag: int = 0
    gene_packed: bytes = b""
    items: list[dict[str, Any]] = field(default_factory=list)
    tail_hex: str = ""


def _split_b8_blob(blob: bytes, count: int) -> list[NestedB8Entry]:
    parsed = parse_b8_blob(blob, count)
    return [NestedB8Entry(type_id=e.type_id, payload=e.payload) for e in parsed]


def read_nested_item(stream: SaveStream) -> dict[str, Any]:
    """ReadNestedItem @ 0x6EF80 — skip when ptr_count > 0 (layout from disasm)."""
    start = stream.tell()
    stream.read_u64()
    stream.read_u32()
    stream.read_u16()
    for _ in range(5):
        stream.read_u8()
    for _ in range(3):
        stream.read_u32()
    stream.read_vec2()
    stream.read_string()
    stream.read_f32()
    for _ in range(20):
        stream.read_u32()
    for _ in range(6):
        stream.read_u8()
    stream.read_u64()
    packed = stream.read_bytes(0xF0)
    return {"offset": start, "gene_packed": packed}


def _parse_nested_header(raw: bytes) -> tuple[str, int, int, int, int]:
    """Parse name/ptr/merge/b8 from block prefix (best-effort for trace-sized spans)."""
    if len(raw) < 4:
        return "", 0, 0, 0, len(raw)
    sub = SaveStream(raw)
    try:
        name = sub.read_string()
    except EOFError:
        return "", 0, 0, 0, 0
    ptr = merge = b8 = 0
    if sub.remaining() >= 4:
        ptr = sub.read_u32()
    if sub.remaining() >= 4:
        merge = sub.read_u32()
    if sub.remaining() >= 4:
        b8 = sub.read_u32()
    return name, ptr, merge, b8, sub.tell()


def read_nested_save(
    stream: SaveStream,
    *,
    block_size: int | None = None,
    file_offset: int | None = None,
) -> NestedSave:
    start = file_offset if file_offset is not None else stream.tell()
    if file_offset is not None:
        stream.seek(file_offset)

    if block_size is not None:
        raw_block = stream.read_bytes(block_size)
        name, ptr_count, merge_index, b8_count, hdr_end = _parse_nested_header(raw_block)
        b8_blob = raw_block[hdr_end:]
        tail = b""
        vec2 = (0.0, 0.0)
        gene_flag = 0
        gene_packed = b""
        if block_size == 1134 and len(b8_blob) >= MAIN_NESTED_B8_BYTES:
            b8_only = b8_blob[:MAIN_NESTED_B8_BYTES]
            tail = b8_blob[MAIN_NESTED_B8_BYTES:]
            b8_blob = b8_only
            if len(tail) >= 8:
                vec2 = struct.unpack_from("<ff", tail, 0)
            if len(tail) >= 12:
                gene_flag = struct.unpack_from("<I", tail, 8)[0]
        elif len(raw_block) >= INVENTORY_GENE_OFF + 0xF0:
            gene_packed = raw_block[INVENTORY_GENE_OFF : INVENTORY_GENE_OFF + 0xF0]
        ns = NestedSave(
            file_offset=start,
            block_size=block_size,
            name=name,
            ptr_item_count=ptr_count,
            merge_index=merge_index,
            b8_count=b8_count,
            raw_block=raw_block,
            b8_blob=b8_blob,
            vec2=vec2,
            gene_flag=gene_flag,
            gene_packed=gene_packed,
            tail_hex=tail.hex(),
        )
        if block_size == 1134 and b8_only:
            ns.b8_entries = _split_b8_blob(b8_only, b8_count)
        return ns

    name = stream.read_string()
    ptr_count = stream.read_u32()
    items: list[dict[str, Any]] = []
    merge_index = stream.read_u32()
    b8_count = stream.read_u32()
    if block_size is None and 0 < ptr_count <= 64:
        for _ in range(ptr_count):
            items.append(read_nested_item(stream))
    elif block_size is None and ptr_count > 0:
        raise ValueError(f"implausible ptr_count {ptr_count} at {start:#x}")

    vec2 = (0.0, 0.0)
    gene_flag = 0
    gene_packed = b""
    b8_blob = b""
    tail = b""

    if block_size is not None:
        consumed = stream.tell() - start
        body = stream.read_bytes(block_size - consumed)
        if block_size == 1134:
            b8_blob = body[:MAIN_NESTED_B8_BYTES]
            tail = body[MAIN_NESTED_B8_BYTES:]
            if len(tail) >= 8:
                vec2 = struct.unpack_from("<ff", tail, 0)
            if len(tail) >= 12:
                gene_flag = struct.unpack_from("<I", tail, 8)[0]
        else:
            b8_blob = body
            if len(body) >= INVENTORY_GENE_OFF + 0xF0:
                gene_packed = body[INVENTORY_GENE_OFF : INVENTORY_GENE_OFF + 0xF0]
    elif stream.remaining() >= 12:
        b8_blob = stream.read_bytes(max(0, stream.remaining() - 12 - 0xF0))
        vec2 = stream.read_vec2()
        gene_flag = stream.read_u32()
        if gene_flag and stream.remaining() >= 0xF0:
            gene_packed = stream.read_bytes(0xF0)
        if stream.remaining():
            tail = stream.read_bytes(stream.remaining())

    ns = NestedSave(
        file_offset=start,
        block_size=block_size,
        name=name,
        ptr_item_count=ptr_count,
        merge_index=merge_index,
        b8_count=b8_count,
        b8_blob=b8_blob,
        vec2=vec2,
        gene_flag=gene_flag,
        gene_packed=gene_packed,
        items=items,
        tail_hex=tail.hex(),
    )
    if block_size == 1134 and b8_blob:
        ns.b8_entries = _split_b8_blob(b8_blob, b8_count)
    return ns


def write_nested_save(stream: SaveStream, ns: NestedSave) -> None:
    """WriteNestedSave @ 0x6D440 — preserve block layout for round-trip."""
    if ns.raw_block:
        stream.write_bytes(ns.raw_block)
        return
    start = stream.tell()
    stream.write_string(ns.name)
    stream.write_u32(ns.ptr_item_count)
    for item in ns.items:
        if item.get("gene_packed"):
            stream.write_bytes(item["gene_packed"])
    stream.write_u32(ns.merge_index)
    stream.write_u32(ns.b8_count)

    if ns.block_size == 1134:
        stream.write_bytes(ns.b8_blob[:MAIN_NESTED_B8_BYTES].ljust(MAIN_NESTED_B8_BYTES, b"\x00"))
        if ns.tail_hex and len(ns.tail_hex) >= MAIN_NESTED_TAIL_BYTES * 2:
            stream.write_bytes(bytes.fromhex(ns.tail_hex)[:MAIN_NESTED_TAIL_BYTES])
        else:
            tail = bytearray(MAIN_NESTED_TAIL_BYTES)
            struct.pack_into("<ff", tail, 0, *ns.vec2)
            struct.pack_into("<I", tail, 8, ns.gene_flag)
            stream.write_bytes(bytes(tail))
    elif ns.block_size is not None:
        need = ns.block_size - (stream.tell() - start)
        body = ns.b8_blob[:need]
        if len(body) < need:
            body = body.ljust(need, b"\x00")
        stream.write_bytes(body[:need])
    else:
        for ent in ns.b8_entries:
            stream.write_u32(ent.type_id)
            stream.write_bytes(ent.payload)
        stream.write_vec2(ns.vec2[0], ns.vec2[1])
        stream.write_u32(ns.gene_flag)
        if ns.gene_flag:
            stream.write_bytes(ns.gene_packed[:0xF0].ljust(0xF0, b"\x00"))
