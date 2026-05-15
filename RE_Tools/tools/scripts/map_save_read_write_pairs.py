"""
Map Horsey.exe save stream Read* RVAs to Write* RVAs (verified via Capstone).

Output: RE_Tools/analysis/save_read_write_pairs.json
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "RE_Tools" / "analysis" / "save_read_write_pairs.json"

# Verified by disasm @ ReadNestedItem 6EF80 vs WriteNestedItem 6EC40,
# grid loop 6E700 vs 6DF30, ReadNestedSave 6D5C0 vs WriteNestedSave 6D440
PAIRS = [
    {"write_rva": "0x6FD40", "read_rva": None, "name": "StreamOpen", "note": "Write only; load uses file -> read cursor globals"},
    {"write_rva": "0x6FDF0", "read_rva": "0x70540", "name": "StreamAvail/ReadU32Peek", "size": 4},
    {"write_rva": "0x6FE10", "read_rva": "0x70320", "name": "WriteU32/ReadU32", "size": 4},
    {"write_rva": "0x6FEB0", "read_rva": "0x705D0", "name": "WriteU8/ReadU8", "size": 1},
    {"write_rva": "0x6FE30", "read_rva": "0x705D0", "name": "WriteU8 alt/ReadU8", "size": 1},
    {"write_rva": "0x6FEF0", "read_rva": "0x70620", "name": "WriteU32FromU8/ReadU8asU32", "size": 4},
    {"write_rva": "0x6FE50", "read_rva": "0x70450", "name": "WriteU16/ReadU16", "size": 2},
    {"write_rva": "0x6FE70", "read_rva": "0x704F0", "name": "WriteU64/ReadU64", "size": 8},
    {"write_rva": "0x6FF10", "read_rva": "0x70670", "name": "WriteF32/ReadF32", "size": 4},
    {"write_rva": "0x6FF30", "read_rva": "0x70670", "name": "WriteVec2F32/ReadF32x2", "size": 8},
    {"write_rva": "0x6FFF0", "read_rva": "0x70890", "name": "WriteStdString/ReadStringLen", "size": -1},
    {"write_rva": "0x6D440", "read_rva": "0x6D5C0", "name": "WriteNestedSave/ReadNestedSave", "size": -2},
    {"write_rva": "0x6EC40", "read_rva": "0x6EF80", "name": "WriteNestedItem/ReadNestedItem", "size": -2},
    {"write_rva": "0x6DF30", "read_rva": "0x6E700", "name": "GridWriteLoop/GridReadLoop", "size": -2},
    {"write_rva": "0x6E043", "read_rva": "0x6E838", "name": "PairWrite/ReadPairVec", "size": -2},
    {"write_rva": "0x6FD90", "read_rva": "0x229340", "name": "FlushToFile/fopenRead", "note": "6FD90 writes file; load path sets read cursor from loaded buffer"},
]

FUNCTIONS = {
    "Save_LoadFromBuffer": {
        "rva": "0x6E643",
        "end": "0x6EAE2",
        "role": "Deserialize save blob into ctx (rsi): grid, pairs, nested",
    },
    "Save_Write": {"rva": "0x6DAB0", "role": "Serialize ctx to heap buffer then 6FD90 flush"},
}

OUT.write_text(json.dumps({"pairs": PAIRS, "functions": FUNCTIONS}, indent=2), encoding="utf-8")
print(f"Wrote {OUT}")
