"""
Capstone disassembly at Phase 1 RVAs (Game/Horsey.exe).

Output: RE_Tools/analysis/disasm_phase1.txt
"""
from __future__ import annotations

import sys
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_64, Cs

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
from paths import get_exe_path  # noqa: E402

OUT = ROOT / "RE_Tools" / "analysis" / "disasm_phase1.txt"
IMAGE_BASE = 0x140000000

REGIONS = {
    "GameMain_InitAndLoop": (0xBE0F0, 0x120),
    "Loop_PollEvent_First": (0xBEA80, 0x80),
    "Loop_GL_SwapWindow": (0xBEAD0, 0x40),
    "Save_Write": (0x6DAB0, 0x100),
    "SettingsLoader": (0x711B0, 0x100),
    "Save_Caller_1": (0x98280, 0x40),
    "CRT_call_GameMain": (0x21EE00, 0x30),
}


def rva_to_offset(pe: pefile.PE, rva: int) -> int | None:
    return pe.get_offset_from_rva(rva)


def main() -> int:
    pe = pefile.PE(str(get_exe_path()))
    raw = Path(get_exe_path()).read_bytes()
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True

    lines: list[str] = []
    lines.append(f"Disassembly — {get_exe_path()}")
    lines.append(f"Image base {hex(IMAGE_BASE)}\n")

    for name, (rva, size) in REGIONS.items():
        off = rva_to_offset(pe, rva)
        if off is None:
            lines.append(f"=== {name} @ 0x{rva:X} — RVA not mapped ===\n")
            continue
        chunk = raw[off : off + size]
        lines.append(f"=== {name} @ RVA 0x{rva:X} (file+0x{off:X}, {size} bytes) ===")
        for insn in md.disasm(chunk, IMAGE_BASE + rva):
            lines.append(f"  0x{insn.address - IMAGE_BASE:08X}: {insn.mnemonic:8} {insn.op_str}")
        lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
