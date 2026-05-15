"""Disassemble WriteNestedSave / ReadNestedSave (Horsey.exe)."""
from __future__ import annotations

import sys
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_64, Cs

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core")
from paths import get_exe_path  # noqa: E402

OUT = ROOT / "RE_Tools" / "analysis" / "disasm_nested_save.txt"
REGIONS = [
    ("WriteNestedSave", 0x6D440, 0x180),
    ("ReadNestedSave", 0x6D5C0, 0x300),
]


def main() -> int:
    pe = pefile.PE(str(get_exe_path()))
    raw = get_exe_path().read_bytes()
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    lines = [f"# Horsey.exe nested save — {get_exe_path()}\n"]
    for name, rva, size in REGIONS:
        off = pe.get_offset_from_rva(rva)
        lines.append(f"=== {name} @ 0x{rva:X} ===")
        for insn in md.disasm(raw[off : off + size], 0x140000000 + rva):
            lines.append(f"  0x{insn.address - 0x140000000:06X}: {insn.mnemonic:8} {insn.op_str}")
        lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
