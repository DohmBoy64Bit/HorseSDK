#!/usr/bin/env python3
"""
Spot-check catalog RVAs against Game/Horsey.exe (entry not int3/00).

  python RE_Tools/tools/scripts/verify_catalog_rvas.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))

from paths import get_exe_path  # noqa: E402

CATALOG = ROOT / "RE_Tools" / "analysis" / "game_function_catalog.json"


def read_rva(exe: Path, rva: int, n: int = 4) -> bytes:
    import pefile  # type: ignore

    pe = pefile.PE(str(exe), fast_load=True)
    pe.parse_data_directories()
    data = exe.read_bytes()
    for sec in pe.sections:
        va = sec.VirtualAddress
        vs = sec.Misc_VirtualSize
        if va <= rva < va + vs:
            off = sec.PointerToRawData + (rva - va)
            return data[off : off + n]
    raise ValueError(f"RVA {rva:#x} out of range")


def main() -> int:
    exe = get_exe_path()
    if not exe.is_file():
        print(f"SKIP: {exe} not found")
        return 0
    if not CATALOG.is_file():
        print(f"FAIL: missing {CATALOG}")
        return 1

    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    funcs = cat.get("functions") or []
    failed: list[str] = []
    checked = 0

    for fn in funcs:
        rva = fn.get("rva")
        name = fn.get("name", "?")
        if rva is None:
            continue
        rva_int = int(rva, 0) if isinstance(rva, str) else int(rva)
        try:
            head = read_rva(exe, rva_int, 4)
        except Exception as e:
            failed.append(f"{name} @ {rva_int:#x}: {e}")
            continue
        checked += 1
        if head[0] == 0xCC or head == b"\x00\x00\x00\x00":
            failed.append(f"{name} @ {rva_int:#x}: bad entry {head.hex()}")

    if failed:
        for line in failed[:20]:
            print(f"FAIL: {line}")
        if len(failed) > 20:
            print(f"... and {len(failed) - 20} more")
        return 1

    print(f"OK: {checked} catalog entries have plausible prologues on {exe.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
