"""
Decode inventory opaque blob: 0x6D2A0 pack / 0x6D3B0 unpack (Horsey.exe).

Verified:
  pack   @ 0x6D2A0 — WriteNestedItem @ 0x6EC64, rcx = rbp+0x2B8
  unpack @ 0x6D3B0 — ReadNestedItem  @ 0x6EF91, rcx = rdi+0x2B8
  disasm: RE_Tools/analysis/disasm_inventory_pack.txt

Output:
  RE_Tools/analysis/save_inventory_opaque.json
  RE_Tools/analysis/save_inventory_genes.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "scripts"))
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "parsers"))
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))

from inventory_pack_codec import (  # noqa: E402
    GENE_COUNT,
    decode_genes,
    pack_byte,
    split_tracks,
    unpack_6d3b0,
)
from genes_dat import GeneDatFile  # noqa: E402

DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
OUT = ROOT / "RE_Tools" / "analysis" / "save_inventory_opaque.json"
OUT_GENES = ROOT / "RE_Tools" / "analysis" / "save_inventory_genes.json"
GENES_DAT = ROOT / "Game" / "data" / "genes.dat"

SAMPLE_OFF = 0xE339
OPAQUE_REL = 0x51
OPAQUE_LEN = 0xF0


def pack_from_unpacked(unpacked: bytes) -> bytes:
    """Inverse of 0x6D3B0 (verified round-trip on save1 sample)."""
    u = unpack_6d3b0(unpacked) if len(unpacked) == OPAQUE_LEN else unpacked
    if len(u) < GENE_COUNT * 2:
        u = bytes(u) + bytes(GENE_COUNT * 2 - len(u))
    out = bytearray(OPAQUE_LEN)
    for k in range(0x78):
        out[2 * k] = pack_byte(u[2 * k + 0xF0], u[2 * k])
        out[2 * k + 1] = pack_byte(u[2 * k + 1 + 0xF0], u[2 * k + 1])
    return bytes(out)


def _hist(b: bytes) -> list[dict]:
    from collections import Counter

    return [{"byte": f"0x{k:02X}", "n": v} for k, v in Counter(b).most_common(12)]


def _load_gene_names() -> list[str]:
    gdf = GeneDatFile.load(GENES_DAT)
    return [e.name for e in gdf.entries]


def main() -> int:
    if not DUMP.is_file():
        print(f"Missing {DUMP}")
        return 1

    dump = DUMP.read_bytes()
    packed = dump[SAMPLE_OFF + OPAQUE_REL : SAMPLE_OFF + OPAQUE_REL + OPAQUE_LEN]
    unpacked = unpack_6d3b0(packed)
    roundtrip = pack_from_unpacked(unpacked)

    gene_names = _load_gene_names()
    genes = decode_genes(unpacked, gene_names)
    track_a, track_b = split_tracks(unpacked)

    # Attach resolved g0/g1 values from genes.xml when available
    genes_xml_path = ROOT / "Game" / "data" / "genes.xml"
    if genes_xml_path.is_file():
        import xml.etree.ElementTree as ET

        root = ET.parse(genes_xml_path).getroot()
        by_name = {g.attrib["name"]: g.attrib for g in root.findall("gene")}
        for row in genes:
            attrs = by_name.get(row["name"])
            if attrs:
                keys = ("g0", "g1", "g2", "g3")
                row["value_a"] = int(attrs[keys[row["allele_a"]]])
                row["value_b"] = int(attrs[keys[row["allele_b"]]])
            else:
                row["value_a"] = row["value_b"] = None

    report = {
        "disasm_pack": "0x6D2A0 @ WriteNestedItem +0x2B8",
        "disasm_unpack": "0x6D3B0 @ ReadNestedItem +0x2B8",
        "codec": {
            "packed_size": OPAQUE_LEN,
            "unpacked_size": 0x1E0,
            "genes_per_track": GENE_COUNT,
            "nibble_encode": "packed = ((hi+1)&7)<<3 | ((lo+1)&7); hi/lo in 0..3",
            "unpack_loop": "0x78 iterations, 2 packed bytes -> 4 track bytes",
            "tracks": {
                "A": "unpacked[0..0xEF] -> allele index for g0 slot (0..3)",
                "B": "unpacked[0xF0..0x1DF] -> allele index for g1 slot (0..3)",
            },
            "roundtrip_verified": roundtrip == packed,
        },
        "sample_record_off": SAMPLE_OFF,
        "opaque_rel": OPAQUE_REL,
        "opaque_len": OPAQUE_LEN,
        "packed_hex": packed.hex(),
        "unpacked_hex": unpacked.hex(),
        "packed_histogram": _hist(packed),
        "track_a_nonzero": sum(1 for x in track_a if x),
        "track_b_nonzero": sum(1 for x in track_b if x),
        "note": (
            "Packed blob is NOT the +0xCC u32 gene_slots array. "
            "Those are ReadU32 (index,value) pairs after unpack in 0x6EF80 when ptr-vector count>0. "
            "This blob is the 240-gene diploid allele-index table at object+0x2B8."
        ),
        "read_order_after_unpack_6EF80": [
            "ReadU64 +0x2A8",
            "ReadU32 +0x1F8",
            "ReadU16 +0x220",
            "ReadU8 flags +0x1C,+0x1FC,+0x21C,+0x284,+0x214,+0x234,+0x210,+0x1CC",
            "ReadU8 bitfield -> +0x1A,+0x204..+0x206,+0x160,+0x22,+0x23",
            "ReadVec2 +0x1D4",
            "ReadStdString +0x168",
            "ReadF32 +0xC0",
            "ReadU32 pairs -> +0xCC..+0x118 (sparse gene slot overrides)",
            "call 0xADB30 -> 0xAE470 applies genetics from +0x40 vector",
        ],
    }

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    OUT_GENES.write_text(
        json.dumps(
            {
                "source": str(DUMP),
                "file_offset": SAMPLE_OFF + OPAQUE_REL,
                "gene_count": len(genes),
                "genes": genes,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {OUT} roundtrip={roundtrip == packed}")
    print(f"Wrote {OUT_GENES} genes={len(genes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
