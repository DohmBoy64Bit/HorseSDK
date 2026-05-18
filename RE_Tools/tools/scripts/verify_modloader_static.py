#!/usr/bin/env python3
"""
Static checks for mod-loader hook contracts on Game/Horsey.exe.

  python RE_Tools/tools/scripts/verify_modloader_static.py
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))

from paths import get_exe_path  # noqa: E402

SPEND_MONEY = 0x10AC60
GAIN_MONEY = 0x10AB80
# test r8b, r8b @ 0x10AC94 (SpendMoney show_ui)
SPEND_TEST_R8B_OFF = 0x10AC94 - SPEND_MONEY
# test r9b, r9b @ 0x10ACAB (str_variant) — 4D 84 C9
SPEND_TEST_R9B_OFF = 0x10ACAB - SPEND_MONEY


def read_rva(exe: Path, rva: int, n: int) -> bytes:
    data = exe.read_bytes()
    # PE parse minimal: assume .text at file offset from section — use pefile if present
    try:
        import pefile  # type: ignore

        pe = pefile.PE(str(exe), fast_load=True)
        pe.parse_data_directories()
        for sec in pe.sections:
            va = sec.VirtualAddress
            vs = sec.Misc_VirtualSize
            if va <= rva < va + vs:
                off = sec.PointerToRawData + (rva - va)
                return data[off : off + n]
        raise ValueError(f"RVA {rva:#x} not in any section")
    except ImportError:
        # fallback: image base 0x140000000, common file alignment
        off = rva
        return data[off : off + n]


def main() -> int:
    exe = get_exe_path()
    if not exe.is_file():
        print(f"SKIP: {exe} not found")
        return 0

    spend = read_rva(exe, SPEND_MONEY, 0x60)
    gain = read_rva(exe, GAIN_MONEY, 0x20)

    errors: list[str] = []

    # GainMoney: should look like a function prologue (not all zeros)
    if spend[0:1] in (b"\x00", b"\xcc"):
        errors.append(f"SpendMoney @ {SPEND_MONEY:#x} looks invalid at entry")

    if SPEND_TEST_R8B_OFF + 3 > len(spend):
        errors.append("SpendMoney slice too short for r8b test")
    elif spend[SPEND_TEST_R8B_OFF : SPEND_TEST_R8B_OFF + 3] not in (
        b"\x45\x84\xc0",  # test r8b, r8b
        b"\x44\x84\xc0",  # test r8b, al (variant)
    ):
        got = spend[SPEND_TEST_R8B_OFF : SPEND_TEST_R8B_OFF + 3].hex()
        errors.append(
            f"SpendMoney missing test r8b @ +{SPEND_TEST_R8B_OFF:#x} (got {got}); "
            "detour must use 4 args (ctx, cost, show_ui, str_variant)"
        )

    if SPEND_TEST_R9B_OFF + 3 <= len(spend):
        r9 = spend[SPEND_TEST_R9B_OFF : SPEND_TEST_R9B_OFF + 3]
        if r9 not in (b"\x45\x84\xc9", b"\x4d\x84\xc9"):
            errors.append(
                f"SpendMoney r9b test @ +{SPEND_TEST_R9B_OFF:#x} unexpected: {r9.hex()}"
            )

    if gain[0:1] in (b"\x00", b"\xcc"):
        errors.append(f"GainMoney @ {GAIN_MONEY:#x} looks invalid at entry")

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return 1

    print(f"OK: SpendMoney 4-arg prologue verified @ {SPEND_MONEY:#x} on {exe.name}")
    print(f"OK: GainMoney entry @ {GAIN_MONEY:#x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
