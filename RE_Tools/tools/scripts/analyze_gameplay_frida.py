#!/usr/bin/env python3
"""Deprecated wrapper — use analyze_race_correlation.py."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ANALYZE = ROOT / "RE_Tools" / "tools" / "scripts" / "analyze_race_correlation.py"


def main() -> int:
    cmd = [sys.executable, str(ANALYZE)]
    if len(sys.argv) > 1:
        cmd.append(sys.argv[1])
    return subprocess.call(cmd, cwd=str(ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
