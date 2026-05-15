"""Parser for AngelCode BMFont text format (.txt sidecars in data/)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class BMFont:
    name: str = ""
    size: int = 0
    ascent: int = 0
    descent: int = 0
    char_count: int = 0
    kerning_count: int = 0
  # parallel arrays keyed by char code order in `chars` line
    advances: List[int] = field(default_factory=list)
    source_file: str = ""

    @staticmethod
    def load(file_path: str | Path) -> BMFont:
        text = Path(file_path).read_text(encoding="utf-8", errors="replace")
        bm = BMFont(source_file=str(file_path))
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            if key == "name":
                bm.name = val
            elif key == "size":
                bm.size = int(val)
            elif key == "ascent":
                bm.ascent = int(val)
            elif key == "descent":
                bm.descent = int(val)
            elif key == "char_count":
                bm.char_count = int(val)
            elif key == "kerning_count":
                bm.kerning_count = int(val)
            elif key == "advance":
                bm.advances = [int(x) for x in val.split(",") if x]
        return bm
