#!/usr/bin/env python3
"""
Phase 5 save editor skeleton (offline — no game injection).

  python RE_Tools/tools/scripts/save_editor.py info Game/save/save1.dat
  python RE_Tools/tools/scripts/save_editor.py backup Game/save/save1.dat
  python RE_Tools/tools/scripts/save_editor.py roundtrip Game/save/save1.dat

Uses save_file_codec (same layout as Save_Write @ 0x6DAB0).
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "scripts"))

from save_file_codec import parse_save_bytes, write_save_bytes  # noqa: E402


def cmd_info(path: Path) -> int:
    data = path.read_bytes()
    p = parse_save_bytes(data, path=str(path))
    print(f"path: {path}")
    print(f"size: {len(data)} bytes")
    print(f"format_version: {p.format_version}")
    print(f"grid: {p.grid_width}x{p.grid_height}")
    print(f"inventory_slots: {len(p.inventory)}")
    print(f"global_names: {len(p.global_names)}")
    if p.footer_chunks:
        print(f"footer_chunks: {len(p.footer_chunks)}")
    return 0


def cmd_backup(path: Path) -> int:
    if not path.is_file():
        print(f"not found: {path}", file=sys.stderr)
        return 1
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = path.with_suffix(path.suffix + f".bak_{stamp}")
    shutil.copy2(path, dest)
    print(f"backup -> {dest}")
    return 0


def cmd_roundtrip(path: Path) -> int:
    data = path.read_bytes()
    parsed = parse_save_bytes(data, path=str(path))
    out = write_save_bytes(parsed)
    match = out == data
    print(f"roundtrip size {len(out)} match={match}")
    if not match:
        for i, (a, b) in enumerate(zip(out, data)):
            if a != b:
                print(f"first diff @ {i:#x}: {a:02x} vs {b:02x}")
                break
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="HorseSDK save editor (offline skeleton)")
    ap.add_argument("command", choices=["info", "backup", "roundtrip"])
    ap.add_argument("save_path", type=Path)
    args = ap.parse_args()

    if args.command == "info":
        return cmd_info(args.save_path)
    if args.command == "backup":
        return cmd_backup(args.save_path)
    return cmd_roundtrip(args.save_path)


if __name__ == "__main__":
    raise SystemExit(main())
