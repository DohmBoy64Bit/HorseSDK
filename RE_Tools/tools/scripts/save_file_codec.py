"""
Full save%d.dat parser — no fixed section anchors (format v12).

Verified against Game/Horsey.exe Save_Load @ 0x6E2B0 and save_buffer_dump.bin.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from decode_grid_cells import GRID_PREFIX_BYTES, decode_cell_stream, encode_cell_stream
from nested_save_codec import NestedSave, read_nested_save, write_nested_save
from save_stream import SaveStream

ROOT = Path(__file__).resolve().parents[3]
DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
OUT = ROOT / "RE_Tools" / "analysis" / "save_parsed.json"

SAVE_FORMAT_VERSION = 12
CTX_DISK_BYTES = 228
MAIN_NESTED_BYTES = 1134
INVENTORY_RECORD_BYTES = 352
INVENTORY_END = 0x31B19
INVENTORY_GENE_OFF = 0x51
FOOTER_SIZES = [303, 421, 117]


@dataclass
class SaveFileParsed:
    path: str = ""
    size: int = 0
    format_version: int = 0
    global_names: list[str] = field(default_factory=list)
    grid_width: int = 0
    grid_height: int = 0
    pair_count: int = 0
    main_nested: NestedSave | None = None
    inventory: list[NestedSave] = field(default_factory=list)
    footer_chunks: list[dict] = field(default_factory=list)
    milestones: dict = field(default_factory=dict)
    raw: dict[str, bytes] = field(default_factory=dict)


def _inventory_blocks_from_trace(*, min_size: int = 0) -> list[tuple[int, int]]:
    """
    (file_offset, byte_size) per WriteStdString anchor @ Save_Write caller 0x6E0D6.

    Trace has **410** contiguous blocks (sum 145376 B). **413** = region/352 math only.
    """
    trace = ROOT / "RE_Tools" / "analysis" / "save_writer_trace.json"
    if not trace.is_file():
        return []
    import json

    ev = json.loads(trace.read_text(encoding="utf-8"))["events"]
    strs = [
        e
        for e in ev
        if e.get("writer") == "WriteStdString"
        and 58169 <= e.get("file_offset", 0) < INVENTORY_END
    ]
    blocks: list[tuple[int, int]] = []
    for i, e in enumerate(strs):
        start = e["file_offset"]
        end = strs[i + 1]["file_offset"] if i + 1 < len(strs) else INVENTORY_END
        size = end - start
        if size >= min_size:
            blocks.append((start, size))
    return blocks


def _global_entry_sizes() -> list[int]:
    """Per-entry byte sizes from save_writer_trace.json (0xC3100 loop)."""
    trace = ROOT / "RE_Tools" / "analysis" / "save_writer_trace.json"
    if not trace.is_file():
        return []
    import json

    ev = json.loads(trace.read_text(encoding="utf-8"))["events"]
    strs = [e for e in ev if e.get("writer") == "WriteStdString" and e.get("file_offset", 0) < 2393]
    sizes = [strs[i + 1]["file_offset"] - strs[i]["file_offset"] for i in range(len(strs) - 1)]
    sizes.append(2393 - strs[-1]["file_offset"])
    return sizes


def read_global_registry(stream: SaveStream, count: int) -> list[dict]:
    """0xC3100 @ 0x6DCC0 — variable-size entries (trace-sized)."""
    sizes = _global_entry_sizes()
    entries: list[dict] = []
    if len(sizes) != count:
        stream.seek(2393)
        return entries
    for idx, sz in enumerate(sizes):
        entry = stream.read_bytes(sz)
        n = int.from_bytes(entry[:4], "little")
        name = entry[4 : 4 + n].decode("utf-8", errors="replace")
        tail = entry[4 + n :]
        entries.append(
            {
                "index": idx,
                "size": sz,
                "name": name,
                "raw": entry,
                "tail_hex": tail.hex(),
                "tail_u32": [
                    int.from_bytes(tail[i : i + 4], "little")
                    for i in range(0, len(tail) - 3, 4)
                ],
            }
        )
    return entries


def write_global_registry(stream: SaveStream, entries: list[dict]) -> None:
    """0xC3100 @ 0x6DCC0 — write trace-sized entries (uses `raw` when present)."""
    for ent in entries:
        if ent.get("raw"):
            stream.write_bytes(ent["raw"])
            continue
        name = ent.get("name", "")
        raw_name = name.encode("utf-8")
        stream.write_u32(len(raw_name))
        stream.write_bytes(raw_name)
        tail = bytes.fromhex(ent.get("tail_hex", ""))
        stream.write_bytes(tail)


def export_global_registry_json(path: Path | None = None) -> Path:
    """Write per-entry trace layout to analysis/save_global_registry.json."""
    out = path or (ROOT / "RE_Tools" / "analysis" / "save_global_registry.json")
    data = DUMP.read_bytes()
    stream = SaveStream(data)
    stream.read_u32()
    stream.read_u64()
    stream.read_u32()
    count = stream.read_u32()
    entries = read_global_registry(stream, count)
    out.write_text(json.dumps({"count": count, "entries": entries}, indent=2), encoding="utf-8")
    return out


def skip_grid_region(stream: SaveStream, width: int, height: int) -> dict:
    stream.read_bytes(GRID_PREFIX_BYTES)
    grid_slice = stream.data[stream.pos :]
    cells, stats = decode_cell_stream(grid_slice, width * height)
    stream.seek(stream.tell() + stats["stream_bytes"])
    remain = 0xDEA7 - stream.tell()
    if remain > 0:
        stream.read_bytes(remain)
    return {"cells": stats["cells_decoded"], "stream_bytes": stats["stream_bytes"], "pad": remain}


def parse_save_bytes(data: bytes, *, path: str = "") -> SaveFileParsed:
    stream = SaveStream(data)
    out = SaveFileParsed(path=path, size=len(data))

    out.format_version = stream.read_u32()
    if out.format_version != SAVE_FORMAT_VERSION:
        raise ValueError(f"bad version {out.format_version}")

    out.raw["header_after_version"] = stream.read_bytes(12)
    gcount = stream.read_u32()
    globals_reg = read_global_registry(stream, gcount)
    out.global_names = [e["name"] for e in globals_reg]
    out.milestones["global_registry"] = globals_reg
    out.milestones["globals_end"] = stream.tell()

    ctx_off = stream.tell()
    out.raw["ctx"] = stream.read_bytes(CTX_DISK_BYTES)
    out.milestones["ctx_end"] = stream.tell()

    horse_count = stream.read_u32()
    out.raw["horses"] = stream.read_bytes(horse_count * 8)
    out.milestones["horse_count"] = horse_count
    out.grid_width = stream.read_u32()
    out.grid_height = stream.read_u32()
    out.milestones["grid_start"] = stream.tell()
    grid_stats = skip_grid_region(stream, out.grid_width, out.grid_height)
    out.milestones["grid_end"] = stream.tell()
    out.milestones["grid_stats"] = grid_stats
    gs = out.milestones["grid_start"]
    ge = out.milestones["grid_end"]
    out.raw["grid_prefix"] = data[gs : gs + GRID_PREFIX_BYTES]
    grid_main = data[gs + GRID_PREFIX_BYTES : ge]
    stream_bytes = int(grid_stats.get("stream_bytes", 0))
    out.raw["grid_pad"] = grid_main[stream_bytes:]
    cells, _ = decode_cell_stream(grid_main, out.grid_width * out.grid_height)
    out.milestones["grid_cells"] = cells
    out.raw["grid"] = data[gs:ge]

    out.pair_count = stream.read_u32()
    out.raw["pairs"] = stream.read_bytes(out.pair_count * 8)
    out.milestones["pairs_end"] = stream.tell()

    out.main_nested = read_nested_save(
        stream,
        block_size=MAIN_NESTED_BYTES,
        file_offset=stream.tell(),
    )

    inv_blocks = _inventory_blocks_from_trace()
    out.milestones["inventory_block_count"] = len(inv_blocks)
    for start, sz in inv_blocks:
        if stream.tell() != start:
            stream.seek(start)
        inv = read_nested_save(stream, block_size=sz, file_offset=start)
        out.inventory.append(inv)

    out.milestones["inventory_end"] = stream.tell()

    for sz in FOOTER_SIZES:
        if sz <= 0 or stream.tell() + sz > len(data):
            break
        raw = stream.read_bytes(sz)
        out.footer_chunks.append(
            {
                "file_offset": stream.tell() - sz,
                "bytes": sz,
                "raw": raw,
                "hex_prefix": raw[:48].hex(),
                "note": "footer @ 0x6E103 — see SaveFooterFormat.md / save_footer_layout.json",
            }
        )

    out.milestones["eof"] = stream.tell()
    out.raw["footer"] = b"".join(c["raw"] for c in out.footer_chunks)
    return out


def write_save_bytes(parsed: SaveFileParsed) -> bytes:
    """
    Re-encode save @ Save_Write 0x6DAB0 section order.

    Globals, main nested, and inventory are written structurally; grid re-encoded from
    decoded cells @ 0x6DF30 when `grid_cells` present (else raw slice).
    """
    out = SaveStream(b"")
    out.write_u32(parsed.format_version)
    out.write_bytes(parsed.raw.get("header_after_version", b"\x00" * 12))
    gentries = parsed.milestones.get("global_registry", [])
    out.write_u32(len(gentries))
    write_global_registry(out, gentries)

    out.write_bytes(parsed.raw.get("ctx", b"\x00" * CTX_DISK_BYTES))
    horse_count = int(parsed.milestones.get("horse_count", 0))
    out.write_u32(horse_count)
    out.write_bytes(parsed.raw.get("horses", b""))
    out.write_u32(parsed.grid_width)
    out.write_u32(parsed.grid_height)
    cells = parsed.milestones.get("grid_cells")
    if cells:
        out.write_bytes(parsed.raw.get("grid_prefix", b"\x00" * GRID_PREFIX_BYTES))
        out.write_bytes(encode_cell_stream(cells))
        out.write_bytes(parsed.raw.get("grid_pad", b""))
    else:
        out.write_bytes(parsed.raw.get("grid", b""))

    out.write_u32(parsed.pair_count)
    out.write_bytes(parsed.raw.get("pairs", b""))

    if parsed.main_nested:
        write_nested_save(out, parsed.main_nested)

    for inv in parsed.inventory:
        if out.tell() != inv.file_offset:
            raise ValueError(
                f"inventory gap at {out.tell():#x} expected {inv.file_offset:#x}"
            )
        write_nested_save(out, inv)

    out.write_bytes(parsed.raw.get("footer", b""))
    return bytes(out.data)


def main() -> int:
    if not DUMP.is_file():
        print(f"Missing {DUMP}")
        return 1
    export_global_registry_json()
    data = DUMP.read_bytes()
    parsed = parse_save_bytes(data, path=str(DUMP))

    ms = {
        k: v
        for k, v in parsed.milestones.items()
        if k not in ("global_registry", "grid_cells")
    }
    summary = {
        "size": parsed.size,
        "version": parsed.format_version,
        "globals": len(parsed.global_names),
        "milestones": ms,
        "main_nested": {
            "name": parsed.main_nested.name if parsed.main_nested else None,
            "b8_count": parsed.main_nested.b8_count if parsed.main_nested else 0,
            "b8_blob_len": len(parsed.main_nested.b8_blob) if parsed.main_nested else 0,
        },
        "inventory_count": len(parsed.inventory),
        "footer_chunks": len(parsed.footer_chunks),
        "eof": parsed.milestones.get("eof"),
    }
    OUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    ok = parsed.milestones.get("eof") == len(data)
    print("EOF OK" if ok else f"EOF mismatch {parsed.milestones.get('eof')} vs {len(data)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
