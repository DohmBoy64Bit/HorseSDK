"""
Race mechanics RE: score formula string, sim helpers, LerpHorse, RNG.

Scans Horsey.exe (Capstone) for:
  - xrefs to race score format @ .rdata 0x2674E0
  - function entries near LerpHorse tag, SimStartRace dispatch, race FSM callees
  - E8 callers into sim_mid_dispatch for SimStartRace path

Output:
  RE_Tools/analysis/race_mechanics.json
  RE_Tools/analysis/disasm_race_*.txt (per function)
  Updates sections in RE_Tools/docs/RaceMechanics.md (via --write-doc)

Usage:
  python RE_Tools/tools/scripts/analyze_race_mechanics.py
  python RE_Tools/tools/scripts/analyze_race_mechanics.py --write-doc
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_64, Cs

ROOT = Path(__file__).resolve().parents[3]
EXE = ROOT / "Game" / "Horsey.exe"
OUT_JSON = ROOT / "RE_Tools" / "analysis" / "race_mechanics.json"
OUT_DOC = ROOT / "RE_Tools" / "docs" / "RaceMechanics.md"
AN = ROOT / "RE_Tools" / "analysis"
IMAGE_BASE = 0x140000000

RACE_SCORE_FMT_RVA = 0x2674E0
LERP_TAG_RVA = 0x262830
SIM_START_TAG_RVA = 0x25BB70

PINNED = [
    ("RaceStateMachine", 0x8F2B0),
    ("RaceAdvanceSim", 0x8C9E0),
    ("RaceUpdateHorses", 0x8CC10),
    ("RacePhaseDispatch", 0x8A7F0),
    ("RaceInitLayout", 0x8A850),
    ("SimMessageDispatch", 0x5E0C2),
    ("SimRandMod", 0xC1900),
    ("GainMoney", 0x10AB80),
    ("SpendMoney", 0x10AC60),
]

DISASM_BYTES = 0x280


def text_section(pe, raw: bytes) -> tuple[bytes, int]:
    for sec in pe.sections:
        if sec.Name.startswith(b".text"):
            off = sec.PointerToRawData
            return raw[off : off + sec.SizeOfRawData], sec.VirtualAddress
    raise RuntimeError("no .text")


def find_function_entry(text: bytes, text_rva: int, site_rva: int, max_back: int = 0x3000) -> int | None:
    off = site_rva - text_rva
    if off < 0 or off >= len(text):
        return None
    start = max(0, off - max_back)
    chunk = text[start:off]
    candidates: list[int] = []
    for i in range(len(chunk) - 3, -1, -1):
        b0, b1 = chunk[i], chunk[i + 1] if i + 1 < len(chunk) else 0
        if b0 == 0x40 and b1 == 0x55:
            candidates.append(text_rva + start + i)
        elif b0 == 0x48 and b1 == 0x89 and i + 3 < len(chunk) and chunk[i + 2] == 0x5C:
            candidates.append(text_rva + start + i)
        elif b0 == 0x48 and b1 == 0x83 and i + 2 < len(chunk) and chunk[i + 2] == 0xEC:
            candidates.append(text_rva + start + i)
    return candidates[-1] if candidates else None


def code_xrefs_to(text: bytes, text_rva: int, target_rva: int, raw: bytes, pe) -> list[int]:
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    hits: list[int] = []
    for i in range(len(text) - 7):
        rva_here = text_rva + i
        for insn_len in range(4, 8):
            if i + insn_len > len(text):
                break
            va_next = IMAGE_BASE + rva_here + insn_len
            disp = struct.unpack_from("<i", text, i + insn_len - 4)[0]
            if (va_next + disp) - IMAGE_BASE != target_rva:
                continue
            off = pe.get_offset_from_rva(rva_here)
            insns = list(md.disasm(raw[off : off + 8], IMAGE_BASE + rva_here))
            if not insns:
                break
            if insns[0].mnemonic in ("lea", "mov", "movsd", "movups") and "rip" in insns[0].op_str:
                hits.append(rva_here)
            break
    return sorted(set(hits))


def disasm_at(pe, raw: bytes, rva: int, size: int) -> list[str]:
    off = pe.get_offset_from_rva(rva)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    lines = []
    for i in md.disasm(raw[off : off + size], IMAGE_BASE + rva):
        lines.append(f"{i.address - IMAGE_BASE:06X}: {i.mnemonic:8} {i.op_str}")
    return lines


def scan_calls_to(text: bytes, text_rva: int, target_rva: int, limit: int = 32) -> list[dict]:
    out: list[dict] = []
    i = 0
    while i + 5 <= len(text):
        if text[i] != 0xE8:
            i += 1
            continue
        rel = struct.unpack_from("<i", text, i + 1)[0]
        call_rva = text_rva + i
        tgt = call_rva + 5 + rel
        if tgt == target_rva:
            entry = find_function_entry(text, text_rva, call_rva)
            out.append({"call_rva": hex(call_rva), "caller_entry": hex(entry) if entry else None})
            if len(out) >= limit:
                break
        i += 1
    return out


def main() -> int:
    raw = EXE.read_bytes()
    pe = pefile.PE(str(EXE))
    text, text_rva = text_section(pe, raw)

    score_xrefs = code_xrefs_to(text, text_rva, RACE_SCORE_FMT_RVA, raw, pe)
    lerp_xrefs = code_xrefs_to(text, text_rva, LERP_TAG_RVA, raw, pe)
    sim_start_xrefs = code_xrefs_to(text, text_rva, SIM_START_TAG_RVA, raw, pe)

    score_sites: list[dict] = []
    for xr in score_xrefs:
        entry = find_function_entry(text, text_rva, xr)
        score_sites.append(
            {
                "xref_rva": hex(xr),
                "function_entry": hex(entry) if entry else None,
            }
        )

    lerp_sites: list[dict] = []
    for xr in lerp_xrefs:
        entry = find_function_entry(text, text_rva, xr)
        lerp_sites.append({"xref_rva": hex(xr), "function_entry": hex(entry) if entry else None})

    sim_start_sites: list[dict] = []
    for xr in sim_start_xrefs:
        entry = find_function_entry(text, text_rva, xr)
        sim_start_sites.append({"xref_rva": hex(xr), "function_entry": hex(entry) if entry else None})

    disasm_exports: list[str] = []
    for name, rva in PINNED:
        lines = disasm_at(pe, raw, rva, DISASM_BYTES)
        out = AN / f"disasm_race_{name}.txt"
        header = f"; Horsey.exe+{rva:X} {name}\n; capstone {DISASM_BYTES} bytes from entry\n\n"
        out.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
        disasm_exports.append(str(out.relative_to(ROOT)).replace("\\", "/"))

    # Score function: disasm around primary xref
    score_entry = 0xE2B80  # HorseRaceScore entry (0xE2C00 is mid-body gate)
    if score_xrefs:
        lines = disasm_at(pe, raw, score_entry, 0x500)
        out = AN / "disasm_race_HorseRaceScore.txt"
        header = (
            f"; Horsey.exe+{score_entry:X} HorseRaceScore\n"
            f"; vtable 0x267368[0]; formula @ 0xE2FBD -> [ctx+0x450]; fmt @ {score_xrefs[0]:X}\n\n"
        )
        out.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
        disasm_exports.append(str(out.relative_to(ROOT)).replace("\\", "/"))

    lerp_entry = None
    if lerp_xrefs:
        lerp_entry = find_function_entry(text, text_rva, lerp_xrefs[0])
        if lerp_entry:
            lines = disasm_at(pe, raw, lerp_entry, 0x400)
            out = AN / "disasm_race_LerpHorse.txt"
            header = f"; Horsey.exe+{lerp_entry:X} LerpHorse (guess)\n; tag xref @ {lerp_xrefs[0]:X}\n\n"
            out.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
            disasm_exports.append(str(out.relative_to(ROOT)).replace("\\", "/"))

    rand_callers = scan_calls_to(text, text_rva, 0xC1900, limit=24)

    payload = {
        "source": "Game/Horsey.exe",
        "image_base": hex(IMAGE_BASE),
        "race_score_format": {
            "string_rva": hex(RACE_SCORE_FMT_RVA),
            "text": "%s = (%d rand + %d nice + %d record) * %d years + %d deco   gdist=%.3f",
            "xrefs": score_sites,
            "function_entry": "0xE2B80",
            "vtable_rva": "0x267368",
            "vtable_slot0": "0xE2B80",
            "formula_store_rva": "0xE2FBD",
            "ctx_race_score_offset": "0x450",
            "pseudocode": "score = (record + nice + rand) * years + deco; optional +5; store [ctx+0x450]",
        },
        "sim_start_race_handler": {
            "entry": "0x5F020",
            "name": "RaceSimHandler",
            "sim_start_post_rva": "0x5F365",
            "race_active_flag": "ctx+0x258",
            "ui_state_eq_7": "ctx+0xE0",
        },
        "race_sim_object_init": {"entry": "0x5F900", "note": "ctor only, not SimStartRace handler"},
        "settings_seed": {
            "key_string_rva": "0x26254C",
            "parse_rva": "0x71BCE",
            "global_rva": "0x2F1587",
            "name": "g_settings_seed",
        },
        "prng": {
            "global_rva": "0x2F2700",
            "sim_rand_mod": "0xC1900",
            "sim_rand_seed": "0xC2080",
        },
        "lerp_horse": {
            "tag_rva": hex(LERP_TAG_RVA),
            "xrefs": lerp_sites,
            "function_entry_guess": hex(lerp_entry) if lerp_entry else None,
        },
        "sim_start_race": {
            "tag_rva": hex(SIM_START_TAG_RVA),
            "xrefs": sim_start_sites,
        },
        "pinned_functions": [{"name": n, "rva": hex(r)} for n, r in PINNED],
        "sim_rand_mod_callers_sample": rand_callers,
        "disasm_files": disasm_exports,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_JSON}")
    for p in disasm_exports:
        print(f"  {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
