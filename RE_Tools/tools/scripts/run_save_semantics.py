"""
Run save semantics RE pipeline (SaveFutureWork items).

Usage:
  python RE_Tools/tools/scripts/run_save_semantics.py
  python RE_Tools/tools/scripts/run_save_semantics.py --frida-vtable
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
    ap.add_argument("--frida-genetics", action="store_true")
    ap.add_argument("--frida-attach", action="store_true", help="Attach genetics Frida to running game")
    ap.add_argument("--seconds", type=float, default=18.0)
    args = ap.parse_args()
    steps = [
        "decode_genetics_ae470.py",
        "decode_type1_b8.py",
        "xref_type1_b8_grid.py",
        "probe_main_nested_b8.py",
        "expand_main_nested_b8_manifest.py",
        "decode_main_nested_vcall48.py",
        "decode_all_inventory_slots.py",
        "align_inventory_slots.py",
        "map_save_ctx_semantics.py",
        "map_save_load_ctx.py",
        "name_save_ctx_rows.py",
        "decode_footer_extra_wire.py",
    ]
    rc = 0
    for s in steps:
        rc |= run(s)
    extra = ["--frida", "--seconds", str(args.seconds)] if args.frida_vtable else []
    rc |= run("resolve_footer_vtable.py", extra)
    if args.frida_genetics:
        extra_g = ["--seconds", str(args.seconds)]
        if args.frida_attach:
            extra_g.append("--attach")
        rc |= run("frida_genetics_ae470.py", extra_g)
    rc |= run("compare_save_files.py")
    rc |= run("build_save_semantics_coverage.py")
    return min(rc, 1)


if __name__ == "__main__":
    raise SystemExit(main())
