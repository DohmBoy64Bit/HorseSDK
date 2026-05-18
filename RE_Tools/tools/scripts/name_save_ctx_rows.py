"""
Name SaveContext SaveSlot6 / SaveRow13 fields from disk sample + exe xrefs.

Verified write loops: Horsey.exe+0x6DD80 (6 slots), +0x6DDB0 (13 rows)
Output: RE_Tools/analysis/save_ctx_row_names.json
        updates RE_Tools/docs/SaveContext.h row comments
"""
from __future__ import annotations

import json
import re
import struct
import sys
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_64, Cs

ROOT = Path(__file__).resolve().parents[3]
DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
TRACE = ROOT / "RE_Tools" / "analysis" / "save_writer_trace.json"
OUT = ROOT / "RE_Tools" / "analysis" / "save_ctx_row_names.json"
HDR = ROOT / "RE_Tools" / "docs" / "SaveContext.h"
IMAGE_BASE = 0x140000000

CTX_START = 0x959
CTX_END = 0xA3D


def u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def parse_slots_and_rows(dump: bytes, events: list) -> tuple[list[dict], list[dict]]:
    sub = sorted(
        [e for e in events if CTX_START <= e["file_offset"] < CTX_END],
        key=lambda x: x["file_offset"],
    )
    slots: list[dict] = []
    rows: list[dict] = []
    slot_i = 0
    row_i = 0
    for e in sub:
        fo = e["file_offset"]
        w = e["writer"]
        if w == "WriteU32FromU8" and slot_i < 6:
            slots.append(
                {
                    "index": slot_i,
                    "file_offset": fo,
                    "byte5": u32(dump, fo),
                    "ctx_off": f"0x31C+{slot_i * 8}+5",
                }
            )
        elif w == "WriteU32" and "0x31C" in (e.get("source") or ""):
            pass
        elif w == "WriteU32" and slot_i < 6 and len(slots) == slot_i:
            slots[slot_i]["dword0"] = u32(dump, fo)
            slot_i += 1
        elif fo >= CTX_START + 0x298 - CTX_START and row_i < 13:
            rel = fo - CTX_START
            if len(rows) <= row_i:
                rows.append({"index": row_i, "file_offset_pair": fo})
            if "field-0x34" in (e.get("note") or "") or (
                e.get("source") and "0x298" in e["source"]
            ):
                rows[row_i]["field_m34"] = u32(dump, fo)
            else:
                rows[row_i]["field_0"] = u32(dump, fo)
                row_i += 1
    return slots, rows


def scan_ctx_xrefs(pe, raw: bytes) -> dict[str, list[str]]:
    """Find instructions referencing rdi+0x298..0x320 (row/slot region)."""
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    pat = re.compile(r"rdi \+ (0x[0-9a-f]+)", re.I)
    hits: dict[str, list[str]] = {}
    for sec in pe.sections:
        if sec.Name.rstrip(b"\x00") != b".text":
            continue
        base = sec.VirtualAddress
        data = raw[sec.PointerToRawData : sec.PointerToRawData + sec.SizeOfRawData]
        for ins in md.disasm(data, IMAGE_BASE + base):
            m = pat.search(ins.op_str)
            if not m:
                continue
            off = int(m.group(1), 16)
            if 0x290 <= off <= 0x330:
                key = f"ctx+0x{off:X}"
                line = f"{ins.address - IMAGE_BASE:06X}: {ins.mnemonic} {ins.op_str}"
                hits.setdefault(key, []).append(line)
                if len(hits[key]) > 8:
                    hits[key] = hits[key][:8]
    return hits


def rows_from_field_layout(dump: bytes) -> list[dict]:
    layout = json.loads(
        (ROOT / "RE_Tools" / "analysis" / "save_field_layout.json").read_text(encoding="utf-8")
    )
    rows: list[dict] = []
    cur: dict | None = None
    for f in layout.get("fields", []):
        note = f.get("note") or ""
        if "row" not in note or "field" not in note:
            continue
        idx = int(note.split("row")[1].split()[0])
        while len(rows) <= idx:
            rows.append({"index": len(rows)})
        row = rows[idx]
        fo = f["file_offset"]
        val = u32(dump, fo) if fo + 4 <= len(dump) else None
        if "field-0x34" in note:
            row["field_m34_u32"] = val
            row["file_off_m34"] = fo
        elif "field+0" in note:
            row["field_0_u32"] = val
            row["file_off_0"] = fo
        row["name_guess"] = _guess_row(idx, row.get("field_m34_u32") or 0)
    return rows


def slots_from_field_layout(dump: bytes) -> list[dict]:
    layout = json.loads(
        (ROOT / "RE_Tools" / "analysis" / "save_field_layout.json").read_text(encoding="utf-8")
    )
    slots: list[dict] = []
    cur = -1
    for f in layout.get("fields", []):
        note = f.get("note") or ""
        if "slot" not in note:
            continue
        if True:
            m = re.search(r"slot(\d+)", note)
            if not m:
                continue
            cur = int(m.group(1))
        while len(slots) <= cur:
            slots.append({"index": len(slots), "name_guess": _guess_slot(len(slots))})
        fo = f["file_offset"]
        w = f.get("writer", "")
        if w == "WriteU32":
            slots[cur]["dword0"] = u32(dump, fo)
            slots[cur]["file_off_dword0"] = fo
        elif w == "WriteU32FromU8":
            slots[cur]["byte_from_u8"] = u32(dump, fo)
            slots[cur]["file_off_byte"] = fo
    return slots


def main() -> int:
    if not DUMP.is_file():
        print("Need dump")
        return 1
    dump = DUMP.read_bytes()
    rows = rows_from_field_layout(dump)
    slots = slots_from_field_layout(dump)

    sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
    from paths import get_exe_path  # noqa: E402

    pe = pefile.PE(str(get_exe_path()))
    raw = get_exe_path().read_bytes()
    xrefs = scan_ctx_xrefs(pe, raw)

    semantics = {
        "SaveRow13": {
            "write_loop": "0x6DDB0 — 13× (WriteU32 [rbx-0x34], WriteU32 [rbx]); rbx += 4",
            "layout": "staggered u32 pair: field_m34 @ ctx+0x298+N*4, field_0 @ ctx+0x2CC+N*4",
            "sample_save1": "all zeros in save_buffer_dump.bin",
        },
        "SaveSlot6": {
            "write_loop": "0x6DD80 — 6× (u8@+5, u32@+0, u8@+4); rbx += 8",
            "layout": "8 B mem / 12 B disk per slot",
            "sample_save1": "all zeros",
        },
    }

    report = {
        "semantics": semantics,
        "rows13": rows,
        "slots6": slots,
        "exe_xrefs_sample": xrefs,
        "disasm_refs": {"rows": "0x6DDB0", "slots": "0x6DD80"},
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _patch_header(rows, slots)
    print(f"Wrote {OUT} rows={len(rows)} slots={len(slots)} xref_keys={len(xrefs)}")
    return 0


def _guess_row(n: int, val: int) -> str:
    names = [
        "row_world_time_or_seed",
        "row_camera_or_view",
        "row_game_flags_a",
        "row_game_flags_b",
        "row_horse_stat_a",
        "row_horse_stat_b",
        "row_inventory_meta",
        "row_quest_or_progress",
        "row_audio_or_env",
        "row_ui_state",
        "row_unused_10",
        "row_unused_11",
        "row_unused_12",
    ]
    return names[n] if n < len(names) else f"row_{n}"


def _guess_slot(n: int) -> str:
    return [
        "slot_horse_care_a",
        "slot_horse_care_b",
        "slot_breeding_flag",
        "slot_training",
        "slot_equipment",
        "slot_misc",
    ][n]


def _patch_header(rows: list[dict], slots: list[dict]) -> None:
    if not HDR.is_file():
        return
    text = HDR.read_text(encoding="utf-8")
    for n, row in enumerate(rows):
        g = row["name_guess"]
        old = f"}} SaveRow13;"
        if n == 0:
            text = text.replace(
                "typedef struct SaveRow13 {",
                "typedef struct SaveRow13 { /* names: see save_ctx_row_names.json */",
            )
    HDR.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
