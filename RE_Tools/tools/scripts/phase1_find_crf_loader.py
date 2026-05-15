"""
Find .crf loader by scanning for CRF header byte patterns and call graph.

Output: RE_Tools/analysis/phase1_crf_loader.json
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_64, Cs

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
from paths import get_exe_path  # noqa: E402

OUT = ROOT / "RE_Tools" / "analysis" / "phase1_crf_loader.json"
IMAGE_BASE = 0x140000000
CRF_MAGIC = bytes([0x01, 0x0E, 0x0A, 0x03])  # quip.crf


def find_callers(pe: pefile.PE, target_rva: int) -> list[int]:
    base = pe.OPTIONAL_HEADER.ImageBase
    target_va = base + target_rva
    hits: list[int] = []
    for section in pe.sections:
        if not section.Name.startswith(b".text"):
            continue
        data = section.get_data()
        sec_rva = section.VirtualAddress
        for off in range(len(data) - 5):
            if data[off] != 0xE8:
                continue
            disp = struct.unpack_from("<i", data, off + 1)[0]
            src = base + sec_rva + off
            if src + 5 + disp == target_va:
                hits.append(sec_rva + off)
    return hits


def scan_cmp_immediate(pe: pefile.PE) -> list[dict]:
    """Find cmp reg, imm32 matching CRF dword patterns."""
    raw = Path(get_exe_path()).read_bytes()
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    imm_le = struct.unpack("<I", CRF_MAGIC)[0]
    hits: list[dict] = []
    for section in pe.sections:
        if not section.Name.startswith(b".text"):
            continue
        code = section.get_data()
        base = IMAGE_BASE + section.VirtualAddress
        for insn in md.disasm(code, base):
            rva = insn.address - IMAGE_BASE
            if insn.mnemonic != "cmp":
                continue
            if str(imm_le) in insn.op_str or CRF_MAGIC.hex()[:6] in insn.op_str:
                hits.append({"rva": hex(rva), "op": insn.op_str})
    return hits[:50]


def main() -> int:
    pe = pefile.PE(str(get_exe_path()))
    raw = Path(get_exe_path()).read_bytes()

    # File IO cluster @ ~0xBF200 (calls 0x6F3C0)
    io_callers = find_callers(pe, 0x6F3C0)
    io_funcs = sorted(set(c - (c % 0x100) for c in io_callers))

    snippets: dict[str, list[str]] = {}
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    for cr in [0xBF200, 0xBF500, 0xBF8C0, 0x6F3C0, 0x6FD40, 0x6FE10]:
        off = pe.get_offset_from_rva(cr)
        if off is None:
            continue
        lines = []
        for i in md.disasm(raw[off : off + 0x100], IMAGE_BASE + cr):
            lines.append(f"{i.address - IMAGE_BASE:08X}: {i.mnemonic} {i.op_str}")
        snippets[hex(cr)] = lines[:30]

    report = {
        "file_append_0x6F3C0_callers": [hex(c) for c in io_callers],
        "hypothesis": "0xBF2xx-0xBF9xx string table / asset path builder; not direct LEA to quip.crf",
        "string_pool_rva": {
            "save_format": "0x263830 save%d.dat",
            "saving_flag": "0x263820 _saving_",
            "quip.crf": "0x980DE",
            "n64.fnt": "0x2658A8",
        },
        "cmp_crf_magic_hits": scan_cmp_immediate(pe),
        "disasm_snippets": snippets,
        "crf_opcode_reference": "RE_Tools/analysis/crf_opcode_trace.json",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
