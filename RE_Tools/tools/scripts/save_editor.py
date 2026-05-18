#!/usr/bin/env python3
"""
HorseSDK save editor (offline).

  python RE_Tools/tools/scripts/save_editor.py info <save.dat>
  python RE_Tools/tools/scripts/save_editor.py backup <save.dat>
  python RE_Tools/tools/scripts/save_editor.py roundtrip <save.dat>
  python RE_Tools/tools/scripts/save_editor.py list-slots <save.dat>
  python RE_Tools/tools/scripts/save_editor.py interactive <save.dat>

Uses save_file_codec (Save_Write @ 0x6DAB0 layout).
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


def cmd_list_slots(path: Path) -> int:
    data = path.read_bytes()
    p = parse_save_bytes(data, path=str(path))
    print(f"inventory ({len(p.inventory)} slots):")
    for i, slot in enumerate(p.inventory[:20]):
        name = getattr(slot, "name", None) or (slot.get("name") if isinstance(slot, dict) else "?")
        off = getattr(slot, "file_offset", None) or (
            slot.get("file_offset") if isinstance(slot, dict) else 0
        )
        print(f"  [{i:3d}] off={off} name={name!r}")
    if len(p.inventory) > 20:
        print(f"  ... {len(p.inventory) - 20} more (use horse_save_cli for gene decode)")
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


def cmd_interactive(path: Path) -> int:
    print(f"Save editor — {path}")
    print("Commands: info | list-slots | backup | roundtrip | quit")
    while True:
        try:
            line = input("save> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line in ("q", "quit", "exit"):
            break
        if line == "info":
            cmd_info(path)
        elif line == "list-slots":
            cmd_list_slots(path)
        elif line == "backup":
            cmd_backup(path)
        elif line == "roundtrip":
            cmd_roundtrip(path)
        else:
            print("Unknown. Try: info | list-slots | backup | roundtrip | quit")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="HorseSDK save editor (offline)")
    ap.add_argument(
        "command",
        choices=["info", "backup", "roundtrip", "list-slots", "interactive"],
    )
    ap.add_argument("save_path", type=Path)
    args = ap.parse_args()

    if not args.save_path.is_file() and args.command != "info":
        print(f"not found: {args.save_path}", file=sys.stderr)
        return 1

    cmds = {
        "info": cmd_info,
        "backup": cmd_backup,
        "roundtrip": cmd_roundtrip,
        "list-slots": cmd_list_slots,
        "interactive": cmd_interactive,
    }
    return cmds[args.command](args.save_path)


if __name__ == "__main__":
    raise SystemExit(main())
