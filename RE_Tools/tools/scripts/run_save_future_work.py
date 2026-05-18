"""
Run SaveFutureWork.md analysis pipeline (static; optional Frida for vtable).

Usage:
  python RE_Tools/tools/scripts/run_save_future_work.py
  python RE_Tools/tools/scripts/run_save_future_work.py --frida-vtable
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "RE_Tools" / "tools" / "scripts"


def run(name: str, extra: list[str] | None = None) -> int:
    cmd = [sys.executable, str(SCRIPTS / name)] + (extra or [])
    print("+", " ".join(cmd))
    return subprocess.call(cmd, cwd=str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frida-vtable", action="store_true")
    ap.add_argument("--seconds", type=float, default=18.0)
    args = ap.parse_args()
    steps = [
        "decode_genetics_ae470.py",
        "probe_main_nested_b8.py",
        "expand_main_nested_b8_manifest.py",
        "name_save_ctx_rows.py",
    ]
    rc = 0
    for s in steps:
        rc |= run(s)
    extra = ["--frida", "--seconds", str(args.seconds)] if args.frida_vtable else []
    rc |= run("resolve_footer_vtable.py", extra)
    return min(rc, 1)


if __name__ == "__main__":
    raise SystemExit(main())
