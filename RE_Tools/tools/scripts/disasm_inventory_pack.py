"""Disassemble 0x6D2A0 / 0x6D3B0 and callers @ 0x6EC40 / 0x6EF80."""
from __future__ import annotations

import sys
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_64, Cs

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
from paths import get_exe_path  # noqa: E402

IMAGE_BASE = 0x140000000
OUT = ROOT / "RE_Tools" / "analysis" / "disasm_inventory_pack.txt"

REGIONS = [
    ("pack_6D2A0", 0x6D2A0, 0x120),
    ("unpack_6D3B0", 0x6D3B0, 0x120),
    ("WriteNestedItem_6EC40_call_pack", 0x6EC40, 0x280),
    ("ReadNestedItem_6EF80_call_unpack", 0x6EF80, 0x280),
]


def main() -> int:
    pe = pefile.PE(str(get_exe_path()))
    raw = get_exe_path().read_bytes()
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    lines: list[str] = [f"Horsey.exe — {get_exe_path()}\n"]
    for name, rva, size in REGIONS:
        off = pe.get_offset_from_rva(rva)
        chunk = raw[off : off + size]
        lines.append(f"=== {name} @ 0x{rva:X} ===")
        for insn in md.disasm(chunk, IMAGE_BASE + rva):
            lines.append(f"  0x{insn.address - IMAGE_BASE:06X}: {insn.mnemonic:8} {insn.op_str}")
        lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
