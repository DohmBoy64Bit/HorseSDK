"""
Dump race bet preset table from Horsey.exe (.rdata).

Used by RaceStateMachine @ 0x1186 when ctx+0x250==0xb and setup runs:
  idx = (ctx+0x268 != 1) ? 1 : 0;
  ctx+0x2c4 = *(u32*)(DAT_140263ba0 + idx*0xC);
  ctx+0x2c8 = *(u32*)(DAT_140263b9c + idx*0xC);

See RE_Tools/docs/RaceBettingOdds.md and ghidra_exports/Race_91148.c.txt.

Output: RE_Tools/analysis/race_bet_presets.json
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[3]
EXE = ROOT / "Game" / "Horsey.exe"
OUT = ROOT / "RE_Tools" / "analysis" / "race_bet_presets.json"

TABLE_RVA = 0x263B9C  # staggered with DAT_140263ba0 = TABLE_RVA + 4
ROW_BYTES = 12
MAX_ROWS = 4


def main() -> int:
    pe = pefile.PE(str(EXE))
    chunk = pe.get_data(TABLE_RVA, ROW_BYTES * MAX_ROWS)

    rows: list[dict] = []
    for i in range(MAX_ROWS):
        off = i * ROW_BYTES
        rec = chunk[off : off + ROW_BYTES]
        if all(b == 0 for b in rec):
            break
        d0, d1, d2 = struct.unpack_from("<III", rec, 0)
        rows.append(
            {
                "index": i,
                "ctx_2c8": d0,
                "ctx_2c4": d1,
                "third_dword": d2,
                "note": "ctx+0x2c4 from ba0+idx*0xC; ctx+0x2c8 from b9c+idx*0xC",
            }
        )

    def read_f(rva: int) -> float:
        return struct.unpack("<f", pe.get_data(rva, 4))[0]

    out = {
        "source": str(EXE.name),
        "table_rva": hex(TABLE_RVA),
        "payout_constants": {
            "DAT_14025b31c": read_f(0x25B31C),
            "DAT_1402bfb48": read_f(0x2BFB48),
        },
        "rows": rows,
        "idx_mapping": {
            "0": "ctx+0x268 == 1 (standard)",
            "1": "ctx+0x268 != 1 (alternate / exotic)",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
