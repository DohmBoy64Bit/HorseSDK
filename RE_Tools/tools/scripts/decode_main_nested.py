"""
Decode main WriteNestedSave blob @ file 0xDECB (1134 bytes, caller 0x6E0A6).

Source: Horsey.exe 0x6D440 / 0x6EC40; save_buffer_dump.bin; save_writer_trace.json
Output: RE_Tools/analysis/save_main_nested_layout.json
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
TRACE = ROOT / "RE_Tools" / "analysis" / "save_writer_trace.json"
OUT = ROOT / "RE_Tools" / "analysis" / "save_main_nested_layout.json"

START = 0xDECB
END = 0xE339


def u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def u16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def f32(b: bytes, o: int) -> float:
    return struct.unpack_from("<f", b, o)[0]


def walk_fields(dump: bytes, ev: list, start: int, end: int) -> list[dict]:
    sub = sorted([e for e in ev if start <= e["file_offset"] < end], key=lambda x: x["file_offset"])
    fields: list[dict] = []
    pos = start
    for e in sub:
        fo = e["file_offset"]
        if fo > pos:
            fields.append(
                {
                    "rel": pos - start,
                    "file_offset": pos,
                    "size": fo - pos,
                    "writer": "WriteU8_gap",
                    "note": "compact trace omits WriteU8",
                    "hex": dump[pos:fo].hex()[:64],
                }
            )
        sz = e.get("size", 4)
        val: dict = {}
        if e["writer"] == "WriteStdString":
            n = u32(dump, fo)
            sz = 4 + n
            raw = dump[fo + 4 : fo + 4 + n]
            val = {"len": n, "text": raw.decode("utf-8", errors="replace")}
        elif sz == 4:
            val = {"u32": u32(dump, fo), "f32": f32(dump, fo)}
        elif sz == 8 and e["writer"] == "WriteVec2F32":
            val = {"xy": struct.unpack_from("<ff", dump, fo)}
        elif sz == 8 and e["writer"] == "WriteU64":
            val = {"u64": struct.unpack_from("<Q", dump, fo)[0]}
        elif sz == 2:
            val = {"u16": u16(dump, fo)}
        fields.append(
            {
                "rel": fo - start,
                "file_offset": fo,
                "size": sz,
                "writer": e["writer"],
                "writer_rva": e.get("writer_rva"),
                "hex": dump[fo : fo + min(sz, 16)].hex(),
                "value": val,
            }
        )
        pos = fo + sz
    if pos < end:
        fields.append(
            {
                "rel": pos - start,
                "file_offset": pos,
                "size": end - pos,
                "writer": "WriteU8_gap",
                "hex": dump[pos:end].hex()[:64],
            }
        )
    return fields


def summarize_f32_clusters(fields: list[dict]) -> list[dict]:
    clusters = []
    cur: list[dict] = []
    for f in fields:
        if f["writer"] == "WriteF32":
            cur.append(f)
        else:
            if len(cur) >= 4:
                clusters.append(
                    {
                        "rel_start": cur[0]["rel"],
                        "count": len(cur),
                        "values": [c["value"].get("f32") for c in cur],
                    }
                )
            cur = []
    if len(cur) >= 4:
        clusters.append({"rel_start": cur[0]["rel"], "count": len(cur), "values": [c["value"].get("f32") for c in cur]})
    return clusters


def main() -> int:
    if not DUMP.is_file() or not TRACE.is_file():
        print("Need dump + trace")
        return 1
    dump = DUMP.read_bytes()
    ev = json.loads(TRACE.read_text(encoding="utf-8"))["events"]
    fields = walk_fields(dump, ev, START, END)
    traced = sum(f["size"] for f in fields if f["writer"] != "WriteU8_gap")
    gaps = sum(f["size"] for f in fields if f["writer"] == "WriteU8_gap")

    nl = u32(dump, START)
    name = dump[START + 4 : START + 4 + nl].decode("utf-8", errors="replace") if nl < 64 else ""
    hdr = 4 + nl
    ptr, merge, b8c = (
        u32(dump, START + hdr),
        u32(dump, START + hdr + 4),
        u32(dump, START + hdr + 8),
    )

    report = {
        "file_offset": START,
        "file_end": END,
        "size": END - START,
        "caller_rva": "0x6E0A6",
        "insn": "0x6D440 WriteNestedSave on ctx nested object",
        "name": name or None,
        "semantic": "world_placed_entities_container",
        "d440_header": {
            "name_std_string": {"len": nl, "text": name},
            "ptr_item_count": ptr,
            "merge_index": merge,
            "b8_vector_count": b8c,
            "note": "b8 loop: per entry WriteU32([obj+8]) + vcall [obj+0]+0x48 (variable bytes; compact trace gaps)",
        },
        "entity_f32_clusters": summarize_f32_clusters(fields),
        "coverage": {
            "traced_bytes": traced,
            "gap_bytes": gaps,
            "pct_traced": round(100 * traced / (END - START), 1),
            "gap_encoding": "vtable+0x48 serialized blobs (WriteU8 omitted in compact trace)",
        },
        "f32_clusters": summarize_f32_clusters(fields),
        "fields": fields,
    }
    for f in fields:
        if f["writer"] == "WriteStdString" and f.get("value", {}).get("text"):
            report["name"] = f["value"]["text"]
            break

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} name={report.get('name')!r} traced={traced} gap={gaps}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
