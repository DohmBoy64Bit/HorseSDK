"""
Parser for Game/data/*.crf compiled fonts.

Verified layout (all 6 .crf in Game/data/, 2026-05-15):
  Offset 0x00: u8[4]  header_tag — bytes [01, line_height?, ?, 03|06]
  Offset 0x04: u32    field_a — 177 or 185 (purpose UNVERIFIED)
  Offset 0x08: u32    section1_bytes — length of body after 16-byte header
  Offset 0x0C: u32    field_c — constant high bits + 0x07 in low byte (UNVERIFIED)

  Section 1: [0x10 : 0x10 + section1_bytes] — glyph stream (opcode-like bytes)
  Section 2: [0x10 + section1_bytes : EOF] — secondary blob (often 16-bit tables)
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CrfHeader:
    byte0: int
    byte1_line_height_guess: int
    byte2: int
    byte3: int
    field_a: int
    section1_bytes: int
    field_c: int

    @staticmethod
    def from_bytes(data: bytes) -> CrfHeader:
        if len(data) < 16:
            raise ValueError("CRF header requires 16 bytes")
        return CrfHeader(
            data[0],
            data[1],
            data[2],
            data[3],
            struct.unpack_from("<I", data, 4)[0],
            struct.unpack_from("<I", data, 8)[0],
            struct.unpack_from("<I", data, 12)[0],
        )


@dataclass
class CrfFont:
    header: CrfHeader
    section1: bytes
    section2: bytes
    source_file: str = ""

    @property
    def byte_size(self) -> int:
        return 16 + len(self.section1) + len(self.section2)

    @staticmethod
    def load(file_path: str | Path) -> CrfFont:
        path = Path(file_path)
        raw = path.read_bytes()
        hdr = CrfHeader.from_bytes(raw)
        s1_start = 16
        s1_end = s1_start + hdr.section1_bytes
        if s1_end > len(raw):
            raise ValueError(f"{path.name}: section1 extends past EOF ({s1_end} > {len(raw)})")
        return CrfFont(
            hdr,
            raw[s1_start:s1_end],
            raw[s1_end:],
            str(path),
        )


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
    from paths import get_data_dir  # noqa: E402

    for p in sorted(get_data_dir().glob("*.crf")):
        c = CrfFont.load(p)
        print(
            f"{p.name}: hdr={c.header.byte0:02x}{c.header.byte1_line_height_guess:02x}"
            f"{c.header.byte2:02x}{c.header.byte3:02x} "
            f"s1={len(c.section1)} s2={len(c.section2)}"
        )
