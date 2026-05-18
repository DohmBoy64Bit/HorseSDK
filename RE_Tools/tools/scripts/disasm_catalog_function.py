"""
Capstone disasm for one or all catalogued game functions.

Usage:
  python RE_Tools/tools/scripts/disasm_catalog_function.py --rva 0x6DAB0 --name Save_Write
  python RE_Tools/tools/scripts/disasm_catalog_function.py --all-known

Output: RE_Tools/analysis/disasm_<name>.txt
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_64, Cs

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
from paths import get_exe_path  # noqa: E402

CATALOG = ROOT / "RE_Tools" / "analysis" / "game_function_catalog.json"
AN = ROOT / "RE_Tools" / "analysis"
IMAGE_BASE = 0x140000000
DEFAULT_BYTES = 0x100


def disasm_at(pe, raw: bytes, rva: int, size: int) -> list[str]:
    off = pe.get_offset_from_rva(rva)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    lines = []
    for i in md.disasm(raw[off : off + size], IMAGE_BASE + rva):
        lines.append(f"{i.address - IMAGE_BASE:06X}: {i.mnemonic:8} {i.op_str}")
    return lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rva", type=str)
    ap.add_argument("--name", type=str, default="fn")
    ap.add_argument("--bytes", type=int, default=DEFAULT_BYTES)
    ap.add_argument("--all-known", action="store_true")
    args = ap.parse_args()

    pe = pefile.PE(str(get_exe_path()))
    raw = get_exe_path().read_bytes()

    targets: list[tuple[str, int]] = []
    if args.all_known:
        if not CATALOG.is_file():
            print("Run build_game_function_catalog.py first")
            return 1
        cat = json.loads(CATALOG.read_text(encoding="utf-8"))
        for f in cat["functions"]:
            if f["name"].startswith("g_"):
                continue
            targets.append((f["name"], int(f["rva"], 16)))
    elif args.rva:
        targets.append((args.name, int(args.rva, 16)))
    else:
        ap.print_help()
        return 1

    for name, rva in targets:
        lines = disasm_at(pe, raw, rva, args.bytes)
        out = AN / f"disasm_{name}.txt"
        header = f"; Horsey.exe+{rva:X} {name}\n; capstone head {args.bytes} bytes\n\n"
        out.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
        print(f"Wrote {out} ({len(lines)} insns)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
