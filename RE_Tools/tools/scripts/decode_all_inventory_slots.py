"""
Decode all inventory nested saves (352 B cadence @ 0xE339..0x31B19).

Verified: Horsey.exe loop @ 0x6E0B0 (48 slots) + 410× WriteStdString in trace;
on-disk cadence 352 B (0x160) per inventory nested @ 0x6E0D6.

Output:
  RE_Tools/analysis/save_inventory_all.json
  RE_Tools/analysis/save_inventory_summary.json
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "scripts"))
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "parsers"))

from inventory_pack_codec import decode_genes, unpack_6d3b0  # noqa: E402
from genes_dat import GeneDatFile  # noqa: E402

DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
OUT_ALL = ROOT / "RE_Tools" / "analysis" / "save_inventory_all.json"
OUT_SUM = ROOT / "RE_Tools" / "analysis" / "save_inventory_summary.json"
GENES_DAT = ROOT / "Game" / "data" / "genes.dat"

START = 0xE339
END = 0x31B19
RECORD = 352
PACK_OFF = 0x51
PACK_LEN = 0xF0


def u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def u16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def f32(b: bytes, o: int) -> float:
    return struct.unpack_from("<f", b, o)[0]


def parse_record(chunk: bytes, slot: int, file_off: int) -> dict:
    nl = u32(chunk, 0)
    name = chunk[4 : 4 + nl].decode("utf-8", errors="replace") if nl else ""
    hdr_end = 4 + nl
    # Fixed 352 B layout when name_len=0 (verified slot 0 @ 0xE339, Horsey.exe 0x6D440)
    ptr = merge = b8c = 0
    if nl == 0 and hdr_end + 16 <= len(chunk):
        ptr = u32(chunk, 4)
        merge = u32(chunk, 8)
        b8c = u32(chunk, 12)
    elif hdr_end + 16 <= len(chunk):
        ptr = u32(chunk, hdr_end)
        merge = u32(chunk, hdr_end + 4)
        b8c = u32(chunk, hdr_end + 8)

    path = "compact_352"
    if ptr > 8 or b8c > 400:
        path = "inline_ec40_header"  # +4 is first inline field, not ptr count

    packed = chunk[PACK_OFF : PACK_OFF + PACK_LEN]
    genes = None
    try:
        unpacked = unpack_6d3b0(packed)
        genes = {
            "nonzero_track_a": sum(1 for x in unpacked[:0xF0] if x),
            "nonzero_track_b": sum(1 for x in unpacked[0xF0:0x1E0] if x),
        }
    except Exception as exc:
        genes = {"error": str(exc)}

    return {
        "slot": slot,
        "file_offset": file_off,
        "path": path,
        "name_len": nl,
        "name": name,
        "ptr_item_count": ptr,
        "merge_index": merge,
        "b8_vector_count": b8c,
        "inline": {
            "word_220": u16(chunk, 0x1A),
            "dword_1F8": u32(chunk, 0x20),
            "vec2_1D4": struct.unpack_from("<ff", chunk, 0x39),
            "f32_C0": f32(chunk, 0x41),
            "qword_2A8": struct.unpack_from("<Q", chunk, 0x141)[0],
        },
        "gene_pack": genes,
    }


def main() -> int:
    if not DUMP.is_file():
        print(f"Missing {DUMP}")
        return 1
    dump = DUMP.read_bytes()
    n = (END - START) // RECORD
    records = []
    for i in range(n):
        off = START + i * RECORD
        records.append(parse_record(dump[off : off + RECORD], i, off))

    gene_names = [e.name for e in GeneDatFile.load(GENES_DAT).entries]
    # Full gene decode for slot 0 only in ALL file (large); summary stats for all
    records[0]["genes_full"] = decode_genes(
        unpack_6d3b0(dump[START + PACK_OFF : START + PACK_OFF + PACK_LEN]), gene_names
    )

    from collections import Counter

    summary = {
        "record_size": RECORD,
        "count": n,
        "path_counts": dict(Counter(r["path"] for r in records)),
        "ptr_item_count_histogram": dict(Counter(r["ptr_item_count"] for r in records)),
        "ptr_zero_slots": sum(1 for r in records if r["ptr_item_count"] == 0),
        "ptr_small_slots": sum(1 for r in records if 0 < r["ptr_item_count"] <= 8),
        "note": (
            "352 B cadence from trace (WriteStdString every 0x160 bytes). "
            "ptr_item_count>8 usually means header misaligned or nonstandard slot; "
            "gene pack @ +0x51 is 0xF0 bytes (0x6D2A0)."
        ),
        "disasm": {
            "loop": "0x6E0B0 rsi+=8 while rsi<0x180 (48 in-memory inventory pointers)",
            "write": "0x6E0D6 call 0x6D440 per non-null pointer",
            "item": "0x6EC40 when ptr_item_count>0",
        },
    }

    OUT_SUM.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    OUT_ALL.write_text(json.dumps({"summary": summary, "records": records}, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_SUM} slots={n}")
    print(f"Wrote {OUT_ALL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
