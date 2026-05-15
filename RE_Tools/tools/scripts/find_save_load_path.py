"""
Static analysis: locate save load vs save write call sites (Horsey.exe).

Output: RE_Tools/analysis/save_load_path.json
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

ROOT = Path(__file__).resolve().parents[3]
sys_path = ROOT / "RE_Tools" / "tools" / "core"
import sys

sys.path.insert(0, str(sys_path))
from paths import get_exe_path  # noqa: E402

OUT = ROOT / "RE_Tools" / "analysis" / "save_load_path.json"
IMAGE_BASE = 0x140000000
SAVE_WRITE = 0x6DAB0


def find_calls_to(pe: pefile.PE, raw: bytes, target_rva: int) -> list[dict]:
    text = None
    for s in pe.sections:
        if s.Name.rstrip(b"\x00") == b".text":
            text = s
            break
    if not text:
        return []
    data = raw[text.PointerToRawData : text.PointerToRawData + text.SizeOfRawData]
    base_rva = text.VirtualAddress
    hits = []
    for i in range(len(data) - 5):
        if data[i] != 0xE8:
            continue
        rel = struct.unpack_from("<i", data, i + 1)[0]
        site_rva = base_rva + i
        tgt = site_rva + 5 + rel
        if tgt == target_rva:
            hits.append({"call_site_rva": f"0x{site_rva:X}", "call_site_va": f"0x{IMAGE_BASE + site_rva:X}"})
    return hits


def disasm_window(raw: bytes, pe: pefile.PE, rva: int, before: int = 0x30, after: int = 0x20) -> list[str]:
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    start = max(0, rva - before)
    off = pe.get_offset_from_rva(start)
    chunk = raw[off : off + before + after]
    lines = []
    for ins in md.disasm(chunk, IMAGE_BASE + start):
        if ins.address - IMAGE_BASE < rva - before:
            continue
        if ins.address - IMAGE_BASE > rva + after:
            break
        mark = " <<" if ins.address - IMAGE_BASE == rva else ""
        lines.append(f"0x{ins.address - IMAGE_BASE:X}: {ins.mnemonic} {ins.op_str}{mark}")
    return lines


def main() -> int:
    pe = pefile.PE(str(get_exe_path()))
    raw = Path(get_exe_path()).read_bytes()
    callers = find_calls_to(pe, raw, SAVE_WRITE)

    sites = []
    for c in callers:
        rva = int(c["call_site_rva"], 16)
        ctx = disasm_window(raw, pe, rva, before=0x25, after=0x10)
        edx_imm = None
        for line in ctx:
            if "edx" in line and "mov" in line:
                edx_imm = line
        sites.append({**c, "disasm_before": ctx, "edx_setup": edx_imm})

    report = {
        "save_write_rva": f"0x{SAVE_WRITE:X}",
        "signature": "void Save_Write(void* ctx /*rcx*/, int mode /*edx*/)",
        "call_sites": sites,
        "frida_observed": {
            "0x9828C": "startup load chain (phase1_frida_save_summary.json)",
            "0x10A2C2": "auto-save during gameplay",
            "0x10A822": "paired flush after auto-save",
            "0xBED11": "quit save from GameMain loop",
        },
        "load_chain_static": [
            "0xBE7C6",
            "0x96F59",
            "0x103B84",
            "0x6E663 (save I/O wrapper)",
            "0x6EAB9 (tail)",
            "0x9828C -> Save_Write",
        ],
        "note": "Same Save_Write serializes on write; load likely reads file into buffer then inverse parse — search ReadFile hooks or 0x9828C edx value at runtime.",
    }

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} ({len(sites)} call sites)")
    for s in sites:
        print(f"  {s['call_site_rva']} edx={s.get('edx_setup','?')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
