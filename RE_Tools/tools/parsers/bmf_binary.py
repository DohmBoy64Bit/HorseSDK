"""
AngelCode BMFont binary format (BMF version 3).

Verified on Game/data/n64.fnt — magic BMF\\x03, blocks 1/2/3/4.
Spec reference: https://www.angelcode.com/products/bmfont/doc/file_format.html
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BmfGlyph:
    id: int
    x: int
    y: int
    width: int
    height: int
    xoffset: int
    yoffset: int
    xadvance: int
    page: int
    chnl: int


@dataclass
class BmfFont:
    version: int
    font_size: int
    face: str
    line_height: int
    base: int
    scale_w: int
    scale_h: int
    pages: list[str] = field(default_factory=list)
    glyphs: list[BmfGlyph] = field(default_factory=list)
    kerning_count: int = 0
    source_file: str = ""

    @staticmethod
    def load(file_path: str | Path) -> BmfFont:
        path = Path(file_path)
        data = path.read_bytes()
        if data[:3] != b"BMF":
            raise ValueError(f"Not BMF: {path}")
        version = data[3]
        if version != 3:
            raise ValueError(f"Unsupported BMF version {version} in {path}")

        font = BmfFont(version=version, font_size=0, face="", line_height=0, base=0, scale_w=0, scale_h=0)
        font.source_file = str(path)
        offset = 4

        while offset + 5 <= len(data):
            block_type = data[offset]
            block_size = struct.unpack_from("<I", data, offset + 1)[0]
            block = data[offset + 5 : offset + 5 + block_size]
            offset += 5 + block_size

            if block_type == 1 and len(block) >= 14:
                font.font_size = struct.unpack_from("<b", block, 0)[0]
                font.face = block[14:].split(b"\x00")[0].decode("utf-8", errors="replace")
            elif block_type == 2 and len(block) >= 10:
                font.line_height, font.base, font.scale_w, font.scale_h, _pages = struct.unpack_from(
                    "<HHHHH", block, 0
                )
            elif block_type == 3:
                font.pages = [p.decode("utf-8", errors="replace") for p in block.split(b"\x00") if p]
            elif block_type == 4:
                glyph_size = 20
                for i in range(0, len(block), glyph_size):
                    if i + glyph_size > len(block):
                        break
                    g = struct.unpack_from("<IHHHHhhhBB", block, i)
                    font.glyphs.append(BmfGlyph(*g))
            elif block_type == 5:
                font.kerning_count = len(block) // 10

        return font


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
    from paths import get_data_dir  # noqa: E402

    fnt = BmfFont.load(get_data_dir() / "n64.fnt")
    print(f"{fnt.face!r} size={fnt.font_size} glyphs={len(fnt.glyphs)} pages={fnt.pages}")
