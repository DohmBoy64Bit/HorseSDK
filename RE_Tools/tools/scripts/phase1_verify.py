"""
Phase 1: confirm baseline RE facts against Game/Horsey.exe.
Outputs RE_Tools/analysis/phase1_verify.txt and prints a summary.
Does not guess new RVAs — checks repomix claims + PE facts.
"""
from __future__ import annotations

import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
from paths import get_data_dir, get_exe_path, get_game_dir, get_save_dir  # noqa: E402

OUT = ROOT / "RE_Tools" / "analysis" / "phase1_verify.txt"

# Claims from repomix-output-DohmBoy64Bit-Horsey-Game.xml (prior RE, 2026-04-30)
EXPECTED = {
    "entry_point_rva": 0x21EE80,
    "image_base": 0x140000000,
    "main_game_init_rva": 0xBE0F0,
    "render_frame_rva": 0x11E0F0,
    "save_function_rva": 0x6DAB0,
    "settings_loader_rva": 0x711B0,
    "crt_main_rva": 0x21ED0C,
}

STRINGS = {
    "settings.xml": None,
    "horsey.tmx": None,
    "got cheevo: %s": 0x25D928,
    "STEAMUSERSTATS_INTERFACE_VERSION013": 0x25C4E8,
    "STEAMAPPS_INTERFACE_VERSION008": None,
    "SteamUtils010": None,
}

STEAM_IMPORTS = [
    "SteamAPI_Shutdown",
    "SteamAPI_RegisterCallback",
    "SteamAPI_ManualDispatch_Init",
    "SteamInternal_SteamAPI_Init",
    "SteamInternal_ContextInit",
    "SteamAPI_RunCallbacks",
    "SteamInternal_FindOrCreateUserInterface",
    "SteamAPI_UnregisterCallback",
    "SteamAPI_GetHSteamUser",
    "SteamAPI_RestartAppIfNecessary",
]


def log(lines: list[str], msg: str) -> None:
    lines.append(msg)
    print(msg)


def find_string_rva(pe: pefile.PE, needle: bytes) -> int | None:
    data = pe.get_memory_mapped_image()
    idx = data.find(needle)
    if idx < 0:
        return None
    return pe.get_rva_from_offset(idx)


def find_call_targets(pe: pefile.PE, target_rva: int) -> list[int]:
    """Find E8 rel32 call sites targeting target_rva."""
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
            dst = src + 5 + disp
            if dst == target_va:
                hits.append(sec_rva + off)
    return hits


def verify_steam_imports(pe: pefile.PE, lines: list[str]) -> bool:
    ok = True
    found: list[str] = []
    for entry in pe.DIRECTORY_ENTRY_IMPORT:
        if b"steam_api64" not in entry.dll:
            continue
        for imp in entry.imports:
            if imp.name:
                found.append(imp.name.decode())
    for name in STEAM_IMPORTS:
        if name not in found:
            log(lines, f"  FAIL missing steam import: {name}")
            ok = False
    extra = sorted(set(found) - set(STEAM_IMPORTS))
    if extra:
        log(lines, f"  WARN extra steam imports: {extra}")
    log(lines, f"  OK steam_api64 imports ({len(found)}): {', '.join(found)}")
    return ok


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    log(lines, f"Phase 1 verification — {datetime.now(timezone.utc).isoformat()}")
    log(lines, f"Game dir: {get_game_dir()}")
    log(lines, f"Data dir: {get_data_dir()}")
    log(lines, f"Save dir: {get_save_dir()}")
    exe = get_exe_path()
    log(lines, f"EXE: {exe} ({exe.stat().st_size} bytes)")
    log(lines, "")

    pe = pefile.PE(str(exe))
    ep = pe.OPTIONAL_HEADER.AddressOfEntryPoint
    ib = pe.OPTIONAL_HEADER.ImageBase

    log(lines, "=== PE header (confirm repomix §1.2) ===")
    log(
        lines,
        f"  Entry RVA: 0x{ep:08X} "
        f"({'OK' if ep == EXPECTED['entry_point_rva'] else 'MISMATCH expected 0x21EE80'})",
    )
    log(
        lines,
        f"  Image base: 0x{ib:016X} "
        f"({'OK' if ib == EXPECTED['image_base'] else 'MISMATCH'})",
    )

    log(lines, "\n=== Data files (SystemPrompt baseline) ===")
    for name in ("horsey.tmx", "sprites.xml", "genes.xml", "settings.xml"):
        p = get_data_dir() / name if name != "settings.xml" else get_save_dir() / name
        log(lines, f"  {'OK' if p.is_file() else 'MISSING'} {p}")

    log(lines, "\n=== Strings (repomix / steam bypass) ===")
    for s, expected_rva in STRINGS.items():
        rva = find_string_rva(pe, s.encode())
        if rva is None:
            log(lines, f"  MISSING string: {s!r}")
            continue
        note = ""
        if expected_rva is not None and rva != expected_rva:
            note = f" (repomix had 0x{expected_rva:X})"
        elif expected_rva is not None:
            note = " (matches repomix)"
        log(lines, f"  0x{rva:08X} {s!r}{note}")

    log(lines, "\n=== Steam imports (see steam_bypass/README.md) ===")
    verify_steam_imports(pe, lines)

    log(lines, "\n=== Function RVAs — incoming CALL sites (repomix claims) ===")
    for label, rva in [
        ("RenderFrame", EXPECTED["render_frame_rva"]),
        ("Save", EXPECTED["save_function_rva"]),
        ("SettingsLoader", EXPECTED["settings_loader_rva"]),
        ("MainGameInit", EXPECTED["main_game_init_rva"]),
    ]:
        callers = find_call_targets(pe, rva)
        log(
            lines,
            f"  {label} @ 0x{rva:X}: {len(callers)} direct call(s)"
            + (f" from {', '.join(hex(c) for c in callers[:5])}" if callers else " — NEEDS GHIDRA/x64dbg"),
        )

    log(lines, "\n=== Steam API call sites (verified May 2026) ===")
    steam_iat: dict[str, int] = {}
    for entry in pe.DIRECTORY_ENTRY_IMPORT:
        if b"steam_api64" in entry.dll:
            for imp in entry.imports:
                if imp.name:
                    steam_iat[imp.name.decode()] = imp.address - pe.OPTIONAL_HEADER.ImageBase

    for entry in pe.DIRECTORY_ENTRY_IMPORT:
        if b"steam_api64" not in entry.dll:
            continue
    base = pe.OPTIONAL_HEADER.ImageBase
    for section in pe.sections:
        if not section.Name.startswith(b".text"):
            continue
        data = section.get_data()
        sec_rva = section.VirtualAddress
        for off in range(len(data) - 6):
            if data[off] != 0xFF or data[off + 1] != 0x15:
                continue
            disp = struct.unpack_from("<i", data, off + 2)[0]
            insn_rva = sec_rva + off
            tgt_rva = (base + insn_rva + 6 + disp) - base
            for name, iat_rva in steam_iat.items():
                if tgt_rva == iat_rva:
                    log(lines, f"  {name} called from 0x{insn_rva:X}")

    log(lines, "\n=== SDL2 ===")
    # Horsey statically links SDL2 (repomix §hook findings)
    has_sdl_dll = any(
        "sdl2" in entry.dll.decode().lower() for entry in pe.DIRECTORY_ENTRY_IMPORT
    )
    export_count = 0
    if hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
        export_count = len(pe.DIRECTORY_ENTRY_EXPORT.symbols)
    log(
        lines,
        f"  SDL2.dll import: {'yes' if has_sdl_dll else 'no (static SDL — matches repomix)'}",
    )
    log(lines, f"  Export count: {export_count} (SDL re-exports if static)")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(lines, f"\nWrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
