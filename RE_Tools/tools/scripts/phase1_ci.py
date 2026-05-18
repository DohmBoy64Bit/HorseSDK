#!/usr/bin/env python3
"""
Phase 1 CI gate — run all automated verification in one pass.

  python RE_Tools/tools/scripts/phase1_ci.py
  python RE_Tools/tools/scripts/phase1_ci.py --skip-frida

Exit 0 only if all enabled steps pass.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "RE_Tools" / "tools" / "scripts"
DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"


def run(cmd: list[str], env: dict | None = None) -> int:
    print("+", " ".join(cmd))
    e = os.environ.copy()
    if env:
        e.update(env)
    return subprocess.call(cmd, cwd=str(ROOT), env=e)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-frida", action="store_true")
    ap.add_argument("--skip-horse-save", action="store_true")
    ap.add_argument("--skip-sdk", action="store_true")
    args = ap.parse_args()

    steps: list[tuple[str, int]] = []

    steps.append(("phase1_verify", run([sys.executable, str(SCRIPTS / "phase1_verify.py")])))
    steps.append(("save_write_codec", run([sys.executable, str(SCRIPTS / "save_write_codec.py")])))

    if not args.skip_horse_save and DUMP.is_file():
        exe = ROOT / "build" / "horse_save" / "Release" / "horse_save_cli.exe"
        if exe.is_file():
            steps.append(
                (
                    "horse_save_roundtrip",
                    run(
                        [str(exe), "--roundtrip", str(DUMP)],
                        env={"HORSE_SAVE_ROUNDTRIP": "1"},
                    ),
                )
            )
            steps.append(
                (
                    "horse_save_structured",
                    run(
                        [str(exe), "--structured-roundtrip", str(DUMP)],
                    ),
                )
            )
        else:
            print("SKIP horse_save (build with cmake -S RE_Tools/src/horse_save -B build/horse_save)")

    static_scripts = [
        "disasm_game_sim_step.py",
        "map_g_game_state_xrefs.py",
        "disasm_crf_vm.py",
        "trace_shutdown_save.py",
    ]
    for name in static_scripts:
        steps.append((name, run([sys.executable, str(SCRIPTS / name)])))

    if not args.skip_frida:
        for name in ["frida_game_sim_step.py", "frida_font_trace.py"]:
            steps.append((name, run([sys.executable, str(SCRIPTS / name), "--seconds", "10"])))

    if not args.skip_sdk:
        steps.append(("sdk_ci", run([sys.executable, str(SCRIPTS / "sdk_ci.py")])))

    print("\n=== phase1_ci summary ===")
    failed = [n for n, rc in steps if rc != 0]
    for n, rc in steps:
        print(f"  {'OK' if rc == 0 else 'FAIL'} {n} (exit {rc})")
    if failed:
        print(f"\nFailed: {', '.join(failed)}")
        return 1
    print("\nAll steps passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
