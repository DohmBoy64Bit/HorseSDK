"""
Field-level footer decode @ 0x31B19..EOF (841 B).

Verified: Horsey.exe
  - Save_Write @ 0x6E103: WriteNestedSave(DAT_14031a660)
  - @ 0x6E112: vcall [obj+0xB0] (extra serializer on same global object)
  - Stream flush @ 0x6E11C: FUN_14006fd90 (no further file bytes)

Output: RE_Tools/analysis/save_footer_layout.json
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
TRACE = ROOT / "RE_Tools" / "analysis" / "save_writer_trace.json"
OUT = ROOT / "RE_Tools" / "analysis" / "save_footer_layout.json"

FOOTER_START = 0x31B19
FOOTER_GENE_PACK_BYTES = 0xF0
FOOTER_GENE_PACK_OFFSETS = [
    (0x31B41, "footer_gene_settings"),
    (0x31CE6, "footer_gene_track"),
]
FOOTER_BYTES = 841

# Second traced panel begins at this file offset (rel 303 from footer start).
PANEL_B_START = 0x31C48


def u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def read_string(dump: bytes, off: int) -> tuple[dict, int] | None:
    if off + 4 > len(dump):
        return None
    n = u32(dump, off)
    if n > 128:
        return None
    end = off + 4 + n
    if end > len(dump):
        return None
    text = dump[off + 4 : end].split(b"\x00")[0].decode("utf-8", errors="replace")
    return {"len": n, "text": text, "file_offset": off}, end


def _gene_pack_spans() -> list[tuple[int, int, str]]:
    return [(off, off + FOOTER_GENE_PACK_BYTES, name) for off, name in FOOTER_GENE_PACK_OFFSETS]


def walk_trace_fields(dump: bytes, ev: list, start: int, end: int) -> list[dict]:
    sub = sorted([e for e in ev if start <= e["file_offset"] < end], key=lambda x: x["file_offset"])
    out: list[dict] = []
    pos = start
    for e in sub:
        fo = e["file_offset"]
        if fo > pos:
            gap_size = fo - pos
            labeled = False
            for g_off, g_end, g_name in _gene_pack_spans():
                if pos == g_off and gap_size == FOOTER_GENE_PACK_BYTES:
                    out.append(
                        {
                            "file_offset": pos,
                            "size": gap_size,
                            "writer": "GenePack_0xF0",
                            "role": g_name,
                            "disasm": "0x6D2A0 pack -> 0x70220 bulk (not Frida WriteU8)",
                            "hex": dump[pos:fo].hex()[:64],
                        }
                    )
                    labeled = True
                    break
            if not labeled:
                out.append(
                    {
                        "file_offset": pos,
                        "size": gap_size,
                        "writer": "untraced_gap",
                        "hex": dump[pos:fo].hex()[:64],
                    }
                )
        sz = e.get("size", 4)
        if e["writer"] == "WriteStdString":
            s, nxt = read_string(dump, fo)
            sz = (nxt - fo) if s else 4
            val = s
        elif sz == 8 and e["writer"] == "WriteVec2F32":
            val = struct.unpack_from("<ff", dump, fo)
        elif sz == 4 and e["writer"] == "WriteF32":
            val = struct.unpack_from("<f", dump, fo)[0]
        elif sz == 4:
            val = u32(dump, fo)
        else:
            val = dump[fo : fo + sz].hex()
        out.append(
            {
                "file_offset": fo,
                "rel": fo - start,
                "size": sz,
                "writer": e["writer"],
                "value": val,
            }
        )
        pos = fo + sz
    if pos < end:
        gap_size = end - pos
        labeled = False
        for g_off, g_end, g_name in _gene_pack_spans():
            if pos == g_off and gap_size == FOOTER_GENE_PACK_BYTES:
                out.append(
                    {
                        "file_offset": pos,
                        "rel": pos - start,
                        "size": gap_size,
                        "writer": "GenePack_0xF0",
                        "role": g_name,
                        "disasm": "0x6D2A0 pack -> 0x70220 bulk",
                        "hex": dump[pos:end].hex()[:64],
                    }
                )
                labeled = True
                break
        if not labeled:
            out.append(
                {
                    "file_offset": pos,
                    "rel": pos - start,
                    "size": gap_size,
                    "writer": "untraced_gap",
                    "hex": dump[pos:end].hex()[:96],
                }
            )
    return out


def _first(fields: list[dict], writer: str, index: int = 0) -> dict | None:
    hits = [f for f in fields if f.get("writer") == writer]
    return hits[index] if index < len(hits) else None


def _vec2(fields: list[dict], index: int = 0) -> list[float] | None:
    f = _first(fields, "WriteVec2F32", index)
    if f and isinstance(f.get("value"), tuple):
        return [float(f["value"][0]), float(f["value"][1])]
    return None


def _string(fields: list[dict], index: int = 0) -> str | None:
    f = _first(fields, "WriteStdString", index)
    if f and isinstance(f.get("value"), dict):
        return f["value"].get("text") or ""
    return None


def build_panels(fields: list[dict], dump: bytes) -> list[dict]:
    panel_a: list[dict] = []
    panel_b: list[dict] = []
    for f in fields:
        if f["file_offset"] < PANEL_B_START:
            panel_a.append(f)
        else:
            panel_b.append(f)

    prefix = dump[FOOTER_START:PANEL_B_START]
    track_name = _string(panel_b, 1)
    world_xy = _vec2(panel_b, 2)
    camera_xy = _vec2(panel_b, 3)
    epilogue_xy = _vec2(panel_b, -1)

    return [
        {
            "id": "prefix_gap",
            "file_offset": FOOTER_START,
            "size": len(prefix),
            "role": "8 B before first traced WriteVec2F32 (not hooked as stream writer)",
            "hex": prefix.hex(),
        },
        {
            "id": "panel_settings",
            "file_offset": panel_a[0]["file_offset"] if panel_a else FOOTER_START,
            "size": PANEL_B_START - (panel_a[0]["file_offset"] if panel_a else FOOTER_START),
            "role": "Global save settings stub (empty name, vec2 @ +0x0C path)",
            "name": _string(panel_a, 0) or "",
            "vec2_0c": _vec2(panel_a, 0),
            "vec2_extra": _vec2(panel_a, 1),
            "gene_pack_settings": {
                "file_offset": 0x31B41,
                "bytes": FOOTER_GENE_PACK_BYTES,
                "codec": "0x6D2A0/0x6D3B0",
            },
            "fields": panel_a,
        },
        {
            "id": "panel_world_track",
            "file_offset": PANEL_B_START,
            "size": FOOTER_START + FOOTER_BYTES - PANEL_B_START,
            "role": "Active track / world footer (display name + tile coords + byte flags)",
            "name_empty": _string(panel_b, 0) or "",
            "track_display_name": track_name,
            "track_name_note": "Exe string @ 0x25B1F8; locs.xml sprite LocAbandoned",
            "world_vec2": world_xy,
            "world_vec2_note": "Sample (176, 7056) — world/tile space (FUN_140107650 grid context)",
            "camera_vec2": camera_xy,
            "nested_name_unknown": _string(panel_b, 2),
            "gene_pack_track": {
                "file_offset": 0x31CE6,
                "bytes": FOOTER_GENE_PACK_BYTES,
                "codec": "0x6D2A0/0x6D3B0 (240 diploid gene indices)",
            },
            "fields": panel_b,
        },
        {
            "id": "epilogue_state",
            "role": "Trailing WriteF32×4 + vec2 + WriteU32FromU8×3 (session tail @ ~0x31DED)",
            "vec2": epilogue_xy,
            "floats": [
                f["value"]
                for f in panel_b
                if f.get("writer") == "WriteF32" and isinstance(f.get("value"), float)
            ],
            "u8_expanded": [
                f["value"] for f in panel_b if f.get("writer") == "WriteU32FromU8"
            ][-3:],
        },
    ]


def main() -> int:
    if not DUMP.is_file() or not TRACE.is_file():
        print("Need dump + trace")
        return 1
    dump = DUMP.read_bytes()
    end = FOOTER_START + FOOTER_BYTES
    ev = json.loads(TRACE.read_text(encoding="utf-8"))["events"]

    fields = walk_trace_fields(dump, ev, FOOTER_START, end)
    traced = sum(f["size"] for f in fields if f.get("writer") != "untraced_gap")

    panels = build_panels(fields, dump)

    report = {
        "file_offset": FOOTER_START,
        "file_end": end,
        "size": FOOTER_BYTES,
        "disasm": {
            "write_nested": "0x6E103 call FUN_14006d440 (rcx = DAT_14031a660)",
            "vtable_b0": "0x6E112 call [rax+0xB0]",
            "stream_flush": "0x6E11C call FUN_14006fd90",
            "global_object_rva": "0x31A660",
        },
        "semantic": {
            "summary": "Single global footer object (not inventory nested); 841 B = nested wire + vcall B0 blob",
            "track_display_name": panels[2].get("track_display_name"),
            "loc_sprite": "LocAbandoned (locs.xml)",
        },
        "panels": panels,
        "notable_strings": [
            f["value"]
            for f in fields
            if f.get("writer") == "WriteStdString"
            and isinstance(f.get("value"), dict)
            and f["value"].get("text")
        ],
        "coverage": {
            "traced_bytes": traced,
            "gap_bytes": FOOTER_BYTES - traced,
            "pct": round(100 * traced / FOOTER_BYTES, 1),
        },
        "fields": fields,
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} traced={traced}/{FOOTER_BYTES}")
    print(f"  track={report['semantic']['track_display_name']!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
