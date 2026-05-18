#!/usr/bin/env python3
"""
Attach Frida race hooks, wait for you to play a race, write gameplay_frida.json.

  python RE_Tools/tools/scripts/run_frida_race_capture.py
  python RE_Tools/tools/scripts/run_frida_race_capture.py --seconds 300

Requires: Horsey.exe running with a save loaded.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FRIDA = ROOT / "RE_Tools" / "tools" / "scripts" / "frida_gameplay_hooks.py"
ANALYZE = ROOT / "RE_Tools" / "tools" / "scripts" / "analyze_race_correlation.py"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=None, help="Auto-stop after N seconds")
    ap.add_argument("--skip-analyze", action="store_true")
    args = ap.parse_args()

    cmd = [sys.executable, str(FRIDA), "--attach", "--no-race"]
    if args.seconds is not None:
        cmd.extend(["--seconds", str(args.seconds)])

    print("=== Frida race capture ===")
    print("1. Start Horsey.exe and load a save")
    print("2. Run a full race (betting optional)")
    print("3. Press Enter in this terminal when done (unless --seconds set)")
    print()

    rc = subprocess.call(cmd, cwd=str(ROOT))
    if rc != 0:
        return rc

    if args.skip_analyze:
        return 0

    print()
    print("=== Race correlation report ===")
    return subprocess.call([sys.executable, str(ANALYZE)], cwd=str(ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
