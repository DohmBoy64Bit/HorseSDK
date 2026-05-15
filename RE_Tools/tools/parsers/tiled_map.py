"""Parser for horsey.tmx (Tiled orthogonal map, CSV layer)."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class TilesetRef:
    first_gid: int
    source: str


@dataclass
class Layer:
    id: int
    name: str
    width: int
    height: int
    data: List[List[int]] = field(default_factory=list)

    def flat(self) -> List[int]:
        rows: List[int] = []
        for row in self.data:
            rows.extend(row)
        return rows


@dataclass
class TiledMap:
    width: int
    height: int
    tile_width: int
    tile_height: int
    tilesets: List[TilesetRef] = field(default_factory=list)
    layers: List[Layer] = field(default_factory=list)

    @staticmethod
    def load(file_path: str | Path) -> TiledMap:
        root = ET.parse(file_path).getroot()
        tmap = TiledMap(
            int(root.get("width", "0")),
            int(root.get("height", "0")),
            int(root.get("tilewidth", "0")),
            int(root.get("tileheight", "0")),
        )
        for ts in root.findall("tileset"):
            tmap.tilesets.append(
                TilesetRef(int(ts.get("firstgid", "0")), ts.get("source", ""))
            )
        for layer_elem in root.findall("layer"):
            layer = Layer(
                int(layer_elem.get("id", "0")),
                layer_elem.get("name", ""),
                int(layer_elem.get("width", "0")),
                int(layer_elem.get("height", "0")),
            )
            data_elem = layer_elem.find("data")
            if data_elem is not None and data_elem.get("encoding") == "csv":
                text = (data_elem.text or "").replace("\n", ",").replace("\r", "")
                parts = [p.strip() for p in text.split(",") if p.strip()]
                flat = [int(p) for p in parts]
                if len(flat) == layer.width * layer.height:
                    layer.data = [
                        flat[y * layer.width : (y + 1) * layer.width]
                        for y in range(layer.height)
                    ]
            tmap.layers.append(layer)
        return tmap
