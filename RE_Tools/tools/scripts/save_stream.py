"""
Little-endian save read/write cursor (Horsey.exe stream @ 0x70320 / 0x6FE10).

Verified: RE_Tools/docs/SaveGhidraCrossref.md, save_buffer_dump.bin
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field


@dataclass
class SaveStream:
    data: bytes
    pos: int = 0

    def remaining(self) -> int:
        return len(self.data) - self.pos

    def tell(self) -> int:
        return self.pos

    def seek(self, pos: int) -> None:
        if pos < 0 or pos > len(self.data):
            raise ValueError(f"seek {pos} out of range")
        self.pos = pos

    def read_bytes(self, n: int) -> bytes:
        if self.pos + n > len(self.data):
            raise EOFError(f"truncated at {self.pos:#x} need {n}")
        out = self.data[self.pos : self.pos + n]
        self.pos += n
        return out

    def read_u8(self) -> int:
        return self.read_bytes(1)[0]

    def read_u16(self) -> int:
        return struct.unpack_from("<H", self.read_bytes(2), 0)[0]

    def read_u32(self) -> int:
        return struct.unpack_from("<I", self.read_bytes(4), 0)[0]

    def read_u64(self) -> int:
        return struct.unpack_from("<Q", self.read_bytes(8), 0)[0]

    def read_f32(self) -> float:
        return struct.unpack_from("<f", self.read_bytes(4), 0)[0]

    def read_vec2(self) -> tuple[float, float]:
        return struct.unpack_from("<ff", self.read_bytes(8), 0)

    def read_string(self) -> str:
        n = self.read_u32()
        if n == 0:
            return ""
        return self.read_bytes(n).split(b"\x00")[0].decode("utf-8", errors="replace")

    def write_bytes(self, b: bytes) -> None:
        self.data += b  # type: ignore[misc]
        self.pos = len(self.data)

    def write_u32(self, v: int) -> None:
        self.write_bytes(struct.pack("<I", v & 0xFFFFFFFF))

    def write_u8(self, v: int) -> None:
        self.write_bytes(bytes([v & 0xFF]))

    def write_f32(self, v: float) -> None:
        self.write_bytes(struct.pack("<f", v))

    def write_vec2(self, x: float, y: float) -> None:
        self.write_bytes(struct.pack("<ff", x, y))

    def write_string(self, s: str) -> None:
        raw = s.encode("utf-8")
        self.write_u32(len(raw))
        self.write_bytes(raw)
