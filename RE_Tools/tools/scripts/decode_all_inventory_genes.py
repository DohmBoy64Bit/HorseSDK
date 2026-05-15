"""
Decode diploid gene packs for inventory nested records (trace block table).

Verified:
  Horsey.exe unpack @ 0x6D3B0 / pack @ 0x6D2A0 @ item+0x2B8 (0xF0 packed bytes)
  save_buffer_dump.bin inventory @ 0xE339..0x31B19 — **410** WriteStdString anchors (not 413×352)
  Gene offset within each record: +0x51 (see save_file_codec._inventory_blocks_from_trace)

Output:
  RE_Tools/analysis/save_inventory_genes_all.json
  RE_Tools/analysis/save_inventory_genes_summary.json
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "scripts"))
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "parsers"))

from inventory_pack_codec import GENE_COUNT, decode_genes, unpack_6d3b0  # noqa: E402
from genes_dat import GeneDatFile  # noqa: E402
from save_file_codec import _inventory_blocks_from_trace  # noqa: E402

DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
OUT_ALL = ROOT / "RE_Tools" / "analysis" / "save_inventory_genes_all.json"
OUT_SUM = ROOT / "RE_Tools" / "analysis" / "save_inventory_genes_summary.json"
GENES_DAT = ROOT / "Game" / "data" / "genes.dat"

PACK_OFF = 0x51
PACK_LEN = 0xF0


def u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def tracks_compact(track: bytes) -> str:
    return "".join(str(x & 3) for x in track)


def decode_slot(chunk: bytes, slot: int, file_off: int, block_size: int, gene_names: list[str], full: bool) -> dict:
    packed = chunk[PACK_OFF : PACK_OFF + PACK_LEN] if len(chunk) >= PACK_OFF + PACK_LEN else b""
    row: dict = {
        "slot": slot,
        "file_offset": file_off,
        "block_size": block_size,
        "name_len": u32(chunk, 0) if len(chunk) >= 4 else 0,
        "ptr_item_count": u32(chunk, 4) if len(chunk) >= 8 else 0,
        "merge_index": u32(chunk, 8) if len(chunk) >= 12 else 0,
        "b8_vector_count": u32(chunk, 12) if len(chunk) >= 16 else 0,
    }
    if len(chunk) < PACK_OFF + PACK_LEN:
        row["gene_status"] = "no_gene_region"
        return row
    try:
        unpacked = bytes(unpack_6d3b0(packed))
        ta, tb = unpacked[:GENE_COUNT], unpacked[GENE_COUNT : GENE_COUNT * 2]
        row["nonzero_track_a"] = sum(1 for x in ta if x)
        row["nonzero_track_b"] = sum(1 for x in tb if x)
        row["track_a_compact"] = tracks_compact(ta)
        row["track_b_compact"] = tracks_compact(tb)
        row["packed_sha256"] = __import__("hashlib").sha256(packed).hexdigest()[:16]
        if full:
            row["genes"] = decode_genes(unpacked, gene_names)
        else:
            nz = [(i, ta[i], tb[i]) for i in range(GENE_COUNT) if ta[i] or tb[i]]
            row["nonzero_genes"] = [
                {"index": i, "name": gene_names[i], "allele_a": a, "allele_b": b} for i, a, b in nz[:64]
            ]
            if len(nz) > 64:
                row["nonzero_genes_truncated"] = len(nz) - 64
    except Exception as exc:
        row["error"] = str(exc)
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="Include all 240 genes per slot (large JSON)")
    args = ap.parse_args()

    if not DUMP.is_file():
        print(f"Missing {DUMP}")
        return 1
    if not GENES_DAT.is_file():
        print(f"Missing {GENES_DAT}")
        return 1

    dump = DUMP.read_bytes()
    blocks = _inventory_blocks_from_trace()
    gene_names = [e.name for e in GeneDatFile.load(GENES_DAT).entries]
    slots = []
    for i, (off, sz) in enumerate(blocks):
        chunk = dump[off : off + sz]
        slots.append(decode_slot(chunk, i, off, sz, gene_names, args.full))

    unique_packs = len({s.get("packed_sha256") for s in slots if "packed_sha256" in s})
    err = sum(1 for s in slots if "error" in s)
    nz_a = [s.get("nonzero_track_a", 0) for s in slots if "error" not in s]
    nz_b = [s.get("nonzero_track_b", 0) for s in slots if "error" not in s]

    summary = {
        "source": str(DUMP),
        "genes_dat": str(GENES_DAT),
        "gene_count": len(gene_names),
        "inventory_blocks": len(blocks),
        "inventory_bytes": sum(sz for _, sz in blocks),
        "note": "413 = 145376/352; on-disk layout uses 410 trace anchors",
        "gene_pack_offset": PACK_OFF,
        "gene_pack_bytes": PACK_LEN,
        "slot_count": len(slots),
        "decode_errors": err,
        "unique_packed_hashes": unique_packs,
        "nonzero_track_a": {
            "min": min(nz_a) if nz_a else 0,
            "max": max(nz_a) if nz_a else 0,
            "mean": round(sum(nz_a) / len(nz_a), 2) if nz_a else 0,
        },
        "nonzero_track_b": {
            "min": min(nz_b) if nz_b else 0,
            "max": max(nz_b) if nz_b else 0,
            "mean": round(sum(nz_b) / len(nz_b), 2) if nz_b else 0,
        },
        "ptr_item_count": dict(Counter(s.get("ptr_item_count") for s in slots)),
        "disasm": {
            "unpack": "0x6D3B0",
            "pack": "0x6D2A0",
            "item_offset": "+0x2B8",
            "write_nested": "0x6E0D6",
        },
    }

    OUT_SUM.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    OUT_ALL.write_text(
        json.dumps({"summary": summary, "slots": slots}, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {OUT_SUM} ({len(slots)} blocks, {unique_packs} unique packs, {err} errors)")
    print(f"Wrote {OUT_ALL} (full={args.full})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
