"""
Parser for genes.dat — verified on Game/data/genes.dat (2026-05-15).

Layout (little-endian):
  u32 gene_count
  u32 first_name_length   (equals len(first gene name), e.g. 4 for "SIZE")
  For genes[0..count-2]:  ASCII name (no null) + u32 len(next name)
  For genes[count-1]:       ASCII name only (no trailing u32)
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GeneDatEntry:
    name: str
    offset: int
    next_name_length: int | None  # u32 after name; None for last gene


@dataclass
class GeneDatFile:
    gene_count: int
    first_name_length: int
    entries: list[GeneDatEntry] = field(default_factory=list)
    source_file: str = ""

    @staticmethod
    def load(file_path: str | Path) -> GeneDatFile:
        path = Path(file_path)
        data = path.read_bytes()
        if len(data) < 8:
            raise ValueError(f"genes.dat too small: {path}")

        count, first_len = struct.unpack_from("<II", data, 0)
        entries: list[GeneDatEntry] = []
        offset = 8

        for i in range(count):
            if offset >= len(data):
                raise ValueError(f"truncated at gene {i} offset {offset}")
            record_start = offset
            if i == 0:
                name_len = first_len
            elif entries[i - 1].next_name_length is None:
                raise ValueError(f"missing next_name_length before gene {i}")
            else:
                name_len = entries[i - 1].next_name_length

            name = data[offset : offset + name_len].decode("ascii")
            offset += name_len
            next_len: int | None = None
            if i < count - 1:
                if offset + 4 > len(data):
                    raise ValueError(f"truncated u32 after {name!r}")
                (next_len,) = struct.unpack_from("<I", data, offset)
                offset += 4
            entries.append(GeneDatEntry(name, record_start, next_len))

        expected_end = offset
        if expected_end != len(data):
            raise ValueError(
                f"size mismatch: parsed {expected_end} bytes, file has {len(data)}"
            )

        return GeneDatFile(count, first_len, entries, str(path))

    def names(self) -> list[str]:
        return [e.name for e in self.entries]


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
    from paths import get_data_dir  # noqa: E402

    gdf = GeneDatFile.load(get_data_dir() / "genes.dat")
    print(f"genes.dat: {gdf.gene_count} entries, first_name_length={gdf.first_name_length}")
    print(f"first={gdf.entries[0].name!r} next_len={gdf.entries[0].next_name_length}")
    print(f"last={gdf.entries[-1].name!r} next_len={gdf.entries[-1].next_name_length}")
