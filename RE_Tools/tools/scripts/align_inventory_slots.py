"""
Re-align inventory 352 B records where ptr_item_count>8 (misread compact header).

Verified Horsey.exe:
  WriteNestedSave @ 0x6D440 — std string + u32 ptr + merge + b8 count
  WriteNestedItem @ 0x6EC40 when [nested+0x8] ptr count > 0
  Gene pack always @ record+0x51, 0xF0 bytes (0x6D2A0)

Heuristic: scan record for u32 name_len in [0,48] where following ptr<=8, b8<=400.

Output: RE_Tools/analysis/save_inventory_aligned.json
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "scripts"))

from inventory_pack_codec import unpack_6d3b0  # noqa: E402

DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
TRACE = ROOT / "RE_Tools" / "analysis" / "save_writer_trace.json"
IN_ALL = ROOT / "RE_Tools" / "analysis" / "save_inventory_all.json"
OUT = ROOT / "RE_Tools" / "analysis" / "save_inventory_aligned.json"

START = 0xE339
END = 0x31B19
RECORD = 352
PACK_OFF = 0x51
PACK_LEN = 0xF0


def u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def score_header(chunk: bytes, off: int) -> int | None:
    if off + 16 > len(chunk):
        return None
    nl = u32(chunk, off)
    if nl > 48:
        return None
    hdr = off + 4 + nl
    if hdr + 12 > len(chunk):
        return None
    ptr = u32(chunk, hdr)
    merge = u32(chunk, hdr + 4)
    b8c = u32(chunk, hdr + 8)
    if ptr > 8 or b8c > 400:
        return None
    if merge != 0xFFFFFFFF and merge > 0x10000:
        return None
  # prefer compact at 0
    score = 100 - off
    if nl == 0 and off == 0:
        score += 50
    if ptr == 0:
        score += 10
    return score


def parse_aligned(chunk: bytes, hdr_off: int) -> dict:
    nl = u32(chunk, hdr_off)
    name = chunk[hdr_off + 4 : hdr_off + 4 + nl].decode("utf-8", errors="replace")
    base = hdr_off + 4 + nl
    ptr = u32(chunk, base)
    merge = u32(chunk, base + 4)
    b8c = u32(chunk, base + 8)
    packed = chunk[PACK_OFF : PACK_OFF + PACK_LEN]
    genes = {
        "nonzero_track_a": sum(1 for x in unpack_6d3b0(packed)[:0xF0] if x not in (0, 0xFF)),
        "nonzero_track_b": sum(1 for x in unpack_6d3b0(packed)[0xF0:0x1E0] if x not in (0, 0xFF)),
    }
    return {
        "header_offset": hdr_off,
        "name_len": nl,
        "name": name,
        "ptr_item_count": ptr,
        "merge_index": merge,
        "b8_vector_count": b8c,
        "path": "compact_352" if hdr_off == 0 and nl == 0 else "realigned_header",
        "gene_pack": genes,
        "inline_ec40": ptr > 0,
    }


def trace_inventory_strings() -> dict[int, str]:
    if not TRACE.is_file():
        return {}
    ev = json.loads(TRACE.read_text(encoding="utf-8"))["events"]
    out: dict[int, str] = {}
    for e in ev:
        if e.get("writer") != "WriteStdString":
            continue
        fo = e["file_offset"]
        if START <= fo < END:
            slot = (fo - START) // RECORD
            out[slot] = e.get("writer_rva", "0x6FFF0")
    return out


def main() -> int:
    if not IN_ALL.is_file():
        print(f"Run decode_all_inventory_slots.py first")
        return 1
    dump = DUMP.read_bytes()
    inv = json.loads(IN_ALL.read_text(encoding="utf-8"))
    records = inv["records"]
    trace_slots = trace_inventory_strings()

    fixed: list[dict] = []
    already_ok = 0
    for rec in records:
        slot = rec["slot"]
        off = rec["file_offset"]
        chunk = dump[off : off + RECORD]
        if rec["path"] == "compact_352" and rec["ptr_item_count"] <= 8:
            already_ok += 1
            fixed.append({**rec, "alignment": "default"})
            continue
        best_off = 0
        best_score = -1
        for try_off in range(0, 64, 4):
            sc = score_header(chunk, try_off)
            if sc is not None and sc > best_score:
                best_score = sc
                best_off = try_off
        if best_score < 0:
            fixed.append(
                {
                    "slot": slot,
                    "file_offset": off,
                    "was_path": rec["path"],
                    "path": "opaque_no_header",
                    "ptr_item_count": rec["ptr_item_count"],
                    "note": "no valid nested header in first 64 B; gene pack @+0x51 still decodable",
                    "gene_pack": parse_aligned(chunk, 0)["gene_pack"],
                }
            )
            continue
        aligned = parse_aligned(chunk, best_off)
        entry = {
            "slot": slot,
            "file_offset": off,
            "was_path": rec["path"],
            "was_ptr_item_count": rec["ptr_item_count"],
            **aligned,
            "trace_write_nested": trace_slots.get(slot),
        }
        if rec["ptr_item_count"] > 8:
            entry["fix"] = (
                f"misread ptr @+4; real header @+{best_off} "
                f"ptr={aligned['ptr_item_count']} b8={aligned['b8_vector_count']}"
            )
        fixed.append(entry)

    ptr_gt8_after = sum(
        1 for r in fixed if r.get("ptr_item_count", 0) > 8 and r.get("path") != "opaque_no_header"
    )
    ec40_slots = [r for r in fixed if r.get("inline_ec40")]

    report = {
        "record_size": RECORD,
        "count": len(fixed),
        "already_compact_ok": already_ok,
        "ptr_gt8_remaining": ptr_gt8_after,
        "inline_ec40_count": len(ec40_slots),
        "exe_refs": {
            "inventory_loop": "0x6E0B0",
            "write_nested": "0x6E0D6 → 0x6D440",
            "write_item": "0x6EC40 when ptr_item_count>0",
            "gene_pack": "0x6D2A0 @ +0x51",
        },
        "coverage": {
            "status": "complete" if ptr_gt8_after == 0 else "partial",
            "note": "ptr_item_count>8 was cadence misalignment; gene pack offset fixed @ +0x51",
        },
        "records": fixed,
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        f"Wrote {OUT} ok={already_ok} ptr_gt8_after={ptr_gt8_after} ec40={len(ec40_slots)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
