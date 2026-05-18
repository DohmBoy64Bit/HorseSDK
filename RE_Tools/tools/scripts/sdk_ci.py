#!/usr/bin/env python3
"""
SDK CI — catalog generation, CMake build, smoke tests.

  python RE_Tools/tools/scripts/sdk_ci.py
  python RE_Tools/tools/scripts/sdk_ci.py --skip-data-smoke
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "RE_Tools" / "tools" / "scripts"
SDK_BUILD = ROOT / "build" / "sdk"
MOD_BUILD = ROOT / "build" / "modloader"
GAME_DATA = ROOT / "Game" / "data"


def run(cmd: list[str], *, cwd: Path | None = None) -> int:
    print("+", " ".join(str(c) for c in cmd))
    return subprocess.call(cmd, cwd=str(cwd or ROOT))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-modloader", action="store_true")
    ap.add_argument("--skip-data-smoke", action="store_true")
    ap.add_argument("--skip-deploy", action="store_true", help="Skip deploy_modloader.py to Game/")
    args = ap.parse_args()

    steps: list[tuple[str, int]] = []

    steps.append(
        ("catalog", run([sys.executable, str(SCRIPTS / "build_game_function_catalog.py")]))
    )
    steps.append(
        (
            "verify_modloader_static",
            run([sys.executable, str(SCRIPTS / "verify_modloader_static.py")]),
        )
    )
    steps.append(
        (
            "verify_catalog_rvas",
            run([sys.executable, str(SCRIPTS / "verify_catalog_rvas.py")]),
        )
    )

    SDK_BUILD.mkdir(parents=True, exist_ok=True)
    steps.append(
        (
            "cmake_sdk_configure",
            run(
                [
                    "cmake",
                    "-S",
                    str(ROOT / "SDK"),
                    "-B",
                    str(SDK_BUILD),
                    "-DCMAKE_BUILD_TYPE=Release",
                ]
            ),
        )
    )
    steps.append(
        (
            "cmake_sdk_build",
            run(["cmake", "--build", str(SDK_BUILD), "--config", "Release"]),
        )
    )

    resolve_exe = SDK_BUILD / "examples" / "Release" / "horse_resolve_example.exe"
    if resolve_exe.is_file():
        # Exit 1 when Horsey.exe not loaded is expected.
        rc = run([str(resolve_exe)])
        steps.append(("resolve_example_smoke", 0 if rc in (0, 1) else rc))
    else:
        steps.append(("resolve_example_smoke", 1))

    types_h = ROOT / "SDK" / "include" / "horse" / "game_function_types.h"
    hooks_h = ROOT / "SDK" / "include" / "horse" / "game_function_hooks.h"
    steps.append(("types_header", 0 if types_h.is_file() else 1))
    steps.append(("hooks_header", 0 if hooks_h.is_file() else 1))

    steps.append(
        (
            "save_editor_roundtrip",
            run(
                [
                    sys.executable,
                    str(SCRIPTS / "save_editor.py"),
                    "roundtrip",
                    str(ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"),
                ]
            ),
        )
    )

    if not args.skip_data_smoke:
        cli = SDK_BUILD / "horse_data" / "Release" / "horse_data_cli.exe"
        genes = GAME_DATA / "genes.dat"
        tmx = GAME_DATA / "horsey.tmx"
        if cli.is_file() and genes.is_file():
            steps.append(("genes_dat_smoke", run([str(cli), "genes", str(genes)])))
        else:
            print("SKIP genes_dat_smoke (build SDK with data or missing Game/data)")
        if cli.is_file() and tmx.is_file():
            steps.append(("tmx_smoke", run([str(cli), "tmx", str(tmx)])))
        else:
            print("SKIP tmx_smoke")

    if not args.skip_modloader:
        MOD_BUILD.mkdir(parents=True, exist_ok=True)
        steps.append(
            (
                "cmake_mod_configure",
                run(
                    [
                        "cmake",
                        "-S",
                        str(ROOT / "ModLoader"),
                        "-B",
                        str(MOD_BUILD),
                    ]
                ),
            )
        )
        steps.append(
            (
                "cmake_mod_build",
                run(["cmake", "--build", str(MOD_BUILD), "--config", "Release"]),
            )
        )
        loader = MOD_BUILD / "Release" / "HorseModLoader.dll"
        steps.append(("modloader_dll", 0 if loader.is_file() else 1))

        if not args.skip_deploy:
            steps.append(
                (
                    "deploy_modloader",
                    run(
                        [
                            sys.executable,
                            str(SCRIPTS / "deploy_modloader.py"),
                            "--no-build",
                        ]
                    ),
                )
            )

    print("\n=== sdk_ci summary ===")
    failed = [n for n, rc in steps if rc != 0]
    for n, rc in steps:
        print(f"  {'OK' if rc == 0 else 'FAIL'} {n} (exit {rc})")
    if failed:
        print(f"\nFailed: {', '.join(failed)}")
        return 1
    print("\nAll SDK CI steps passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
