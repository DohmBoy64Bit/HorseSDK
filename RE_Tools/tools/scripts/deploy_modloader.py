#!/usr/bin/env python3
"""
Build ModLoader (Release) and copy artifacts next to Game/Horsey.exe.

  python RE_Tools/tools/scripts/deploy_modloader.py
  python RE_Tools/tools/scripts/deploy_modloader.py --no-build
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MOD_BUILD = ROOT / "build" / "modloader"
GAME = ROOT / "Game"
MODS_DIR = GAME / "mods"

ARTIFACTS = (
    ("HorseModLoader.dll", MOD_BUILD / "Release" / "HorseModLoader.dll"),
    ("horse_inject.exe", MOD_BUILD / "Release" / "horse_inject.exe"),
    ("example_mod.dll", MOD_BUILD / "mods" / "Release" / "example_mod.dll"),
    ("minimap_mod.dll", MOD_BUILD / "mods" / "Release" / "minimap_mod.dll"),
)


def run(cmd: list[str]) -> int:
    print("+", " ".join(str(c) for c in cmd))
    return subprocess.call(cmd, cwd=str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-build", action="store_true", help="Only copy; skip cmake build")
    ap.add_argument(
        "--game-dir",
        type=Path,
        default=GAME,
        help="Destination directory (default: HorseSDK/Game)",
    )
    args = ap.parse_args()
    game_dir: Path = args.game_dir.resolve()
    if not game_dir.is_dir():
        print(f"Game dir missing: {game_dir}", file=sys.stderr)
        return 1

    if not args.no_build:
        MOD_BUILD.mkdir(parents=True, exist_ok=True)
        if run(["cmake", "-S", str(ROOT / "ModLoader"), "-B", str(MOD_BUILD)]) != 0:
            return 1
        if run(["cmake", "--build", str(MOD_BUILD), "--config", "Release"]) != 0:
            return 1

    mods_dir = game_dir / "mods"
    mods_dir.mkdir(parents=True, exist_ok=True)

    ini_example = ROOT / "ModLoader" / "HorseModLoader.ini.example"
    ini_dest = game_dir / "HorseModLoader.ini"
    if ini_example.is_file() and not ini_dest.is_file():
        shutil.copy2(ini_example, ini_dest)
        print(f"  -> {ini_dest} (from example)")

    for dest_name, src in ARTIFACTS:
        if not src.is_file():
            print(f"Missing build artifact: {src}", file=sys.stderr)
            print("Run without --no-build or build ModLoader first.", file=sys.stderr)
            return 1
        dest = (
            mods_dir / dest_name
            if dest_name.endswith("_mod.dll") or dest_name == "example_mod.dll"
            else game_dir / dest_name
        )
        try:
            shutil.copy2(src, dest)
        except PermissionError:
            print(
                f"  FAIL {dest} (file in use — close Horsey.exe / injector and retry)",
                file=sys.stderr,
            )
            return 1
        print(f"  -> {dest}")

    print(f"\nDeployed to {game_dir}")
    print("  HorseModLoader.dll")
    print("  horse_inject.exe")
    print("  mods\\*.dll (example_mod, minimap_mod, ...)")
    print("\nUsage: start Horsey.exe, then run horse_inject.exe from the Game folder.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
