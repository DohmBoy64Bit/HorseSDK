"""
Probe main nested b8 blob layout (Horsey.exe @ 0x6D440, sample `unknown`).

Output: RE_Tools/analysis/save_main_nested_b8.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "scripts"))

from nested_b8_codec import encode_b8_blob, parse_b8_blob, summarize_b8_blob  # noqa: E402
from save_file_codec import parse_save_bytes  # noqa: E402

DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
OUT = ROOT / "RE_Tools" / "analysis" / "save_main_nested_b8.json"


def main() -> int:
    data = DUMP.read_bytes()
    parsed = parse_save_bytes(data)
    mn = parsed.main_nested
    if not mn:
        print("no main_nested")
        return 1
    entries = parse_b8_blob(mn.b8_blob, mn.b8_count)
    summary = summarize_b8_blob(mn.b8_blob, mn.b8_count)
    rebuilt = encode_b8_blob(entries)
    report = {
        "name": mn.name,
        **summary,
        "reencode_match": rebuilt == mn.b8_blob,
        "entries": [
            {
                "type_id": e.type_id,
                "payload_bytes": len(e.payload),
                "decoded": e.decoded,
            }
            for e in entries
        ],
        "field_layout_type2_inner": {
            "+0x00": "packed_u8 (FUN_14006d8c0)",
            "+0x01": "cell_flag_c ([obj+0x0C])",
            "+0x02": "grid_cell_type_id ([obj+0x48], default 23=GrassLand)",
            "+0x01": "ext_c_u8 [obj+0x0C]",
            "+0x02": "ext_48_u8 [obj+0x48] (often 0x17)",
            "+0x03": "ext_pad_u8",
            "+0x04": "pad8[8]",
            "+0x0C": "coord8[8] tile key",
            "+0x14": "f32[4] @ [obj+0x28..0x34]",
            "+0x24": "link_u32 (often 2)",
        },
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        f"Wrote {OUT} on_disk={summary['on_disk_slots']} "
        f"implicit={summary['implicit_eof_slots']} reencode={report['reencode_match']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
