"""Parser for TextureAtlas XML (terrain, locs, veg, sprites, furniture, biglogo)."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class Sprite:
    name: str
    x: int
    y: int
    width: int
    height: int
    frame_count: Optional[int] = None
    hotspot_x: Optional[float] = None
    hotspot_y: Optional[float] = None

    @staticmethod
    def from_xml(element: ET.Element) -> Sprite:
        a = element.attrib
        return Sprite(
            a.get("n", ""),
            int(a.get("x", "0")),
            int(a.get("y", "0")),
            int(a.get("w", "0")),
            int(a.get("h", "0")),
            int(a["c"]) if "c" in a else None,
            float(a["hx"]) if "hx" in a else None,
            float(a["hy"]) if "hy" in a else None,
        )


@dataclass
class TextureAtlas:
    sprites: List[Sprite] = field(default_factory=list)
    source_file: str = ""

    @staticmethod
    def load(file_path: str | Path) -> TextureAtlas:
        root = ET.parse(file_path).getroot()
        if root.tag != "TextureAtlas":
            raise ValueError(f"Expected TextureAtlas root, got {root.tag}")
        atlas = TextureAtlas(source_file=str(file_path))
        for elem in root.findall("sprite"):
            atlas.sprites.append(Sprite.from_xml(elem))
        return atlas
