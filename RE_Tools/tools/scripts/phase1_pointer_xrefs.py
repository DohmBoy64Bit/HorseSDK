"""
Find pointers to string RVAs in PE sections (8-byte VA match).

Output: RE_Tools/analysis/phase1_pointer_xrefs.json
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
from paths import get_exe_path  # noqa: E402

OUT = ROOT / "RE_Tools" / "analysis" / "phase1_pointer_xrefs.json"
IMAGE_BASE = 0x140000000

TARGETS = [
    "settings.xml",
    "horsey.tmx",
    "genes.dat",
    "genes.xml",
    "quip.crf",
    "n64.fnt",
    "n64_0.png",
    ".dat",
    "save",
    "data\\",
]


def string_rvas(pe: pefile.PE, needle: bytes) -> list[int]:
    data = pe.get_memory_mapped_image()
    out: list[int] = []
    start = 0
    while True:
        idx = data.find(needle, start)
        if idx < 0:
            break
        out.append(pe.get_rva_from_offset(idx))
        start = idx + 1
    return out


def find_va_refs(pe: pefile.PE, target_rva: int) -> list[dict]:
    want = IMAGE_BASE + target_rva
    hits: list[dict] = []
    for section in pe.sections:
        name = section.Name.decode().rstrip("\x00")
        if name not in (".text", ".rdata", ".data", ".pdata"):
            continue
        data = section.get_data()
        sec_rva = section.VirtualAddress
        for off in range(0, len(data) - 7):
            val = struct.unpack_from("<Q", data, off)[0]
            if val == want:
                hits.append({"section": name, "rva": hex(sec_rva + off)})
    return hits


def main() -> int:
    pe = pefile.PE(str(get_exe_path()))
    entries: list[dict] = []
    for label in TARGETS:
        for rva in string_rvas(pe, label.encode()):
            ptrs = find_va_refs(pe, rva)
            entries.append(
                {
                    "string": label,
                    "string_rva": hex(rva),
                    "pointer_sites": ptrs[:40],
                    "pointer_count": len(ptrs),
                }
            )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {"image_base": hex(IMAGE_BASE), "method": "8-byte VA equality scan", "entries": entries},
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {OUT}")
    for e in entries:
        if e["pointer_count"]:
            print(f"  {e['string']} @ {e['string_rva']}: {e['pointer_count']} pointers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
