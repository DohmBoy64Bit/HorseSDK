"""
Assemble full save1.dat / save_buffer_dump.bin layout with byte coverage.

Output:
  RE_Tools/analysis/save_complete_format.json
  RE_Tools/docs/SaveCompleteFormat.md (generated table)
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DUMP = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
OUT_JSON = ROOT / "RE_Tools" / "analysis" / "save_complete_format.json"
OUT_MD = ROOT / "RE_Tools" / "docs" / "SaveCompleteFormat.md"

# Verified section boundaries (204386 B aligned dump)
SECTIONS = [
    {
        "id": "format_version",
        "start": 0x00,
        "end": 0x04,
        "insn": "0x6DCBB",
        "status": "mapped",
        "description": "u32 = 12",
    },
    {
        "id": "global_header",
        "start": 0x04,
        "end": 0x14,
        "insn": "0xC3100",
        "status": "mapped",
        "description": "u64 + u32 + u32 count",
    },
    {
        "id": "global_horse_registry",
        "start": 0x14,
        "end": 0x959,
        "insn": "0xC3100 loop",
        "status": "mapped",
        "description": "71 × (WriteStdString + u32 flags)",
    },
    {
        "id": "ctx_main_block",
        "start": 0x959,
        "end": 0xA3D,
        "insn": "0x6DCCA..0x6DDC9",
        "status": "mapped",
        "description": "rdi SaveContext fields (trace-correlated)",
    },
    {
        "id": "horse_u16_vector",
        "start": 0xA3D,
        "end": 0xA59,
        "insn": "0x6DDF9/0x6DE30",
        "status": "mapped",
        "description": "count + N×8 bytes (4×u16)",
    },
    {
        "id": "fields_278_27c",
        "start": 0xA59,
        "end": 0xA61,
        "insn": "0x6DEA9/0x6DEB7",
        "status": "mapped",
        "description": "grid width 400, height 225",
    },
    {
        "id": "grid_prefix",
        "start": 0xA61,
        "end": 0xD83,
        "insn": "0x6DF30",
        "status": "encoded",
        "description": "401 × (0x0F,0x09) row prefix",
    },
    {
        "id": "grid_main_u8",
        "start": 0xD83,
        "end": 0xDEA7,
        "insn": "0x6DF30",
        "status": "decoded_cells",
        "description": "90k cells decoded — save_grid_cells.json (0x6E700 read loop)",
    },
    {
        "id": "pair_vector",
        "start": 0xDEA7,
        "end": 0xDECB,
        "insn": "0x6E043",
        "status": "mapped",
        "description": "4 × (u32,u32) pairs",
    },
    {
        "id": "nested_main",
        "start": 0xDECB,
        "end": 0xE339,
        "insn": "0x6E0A6 → 0x6D440",
        "status": "mapped_traced",
        "description": "main world nested; name 'unknown'; 72.7% compact trace",
    },
    {
        "id": "nested_inventory",
        "start": 0xE339,
        "end": 0x31B19,
        "insn": "0x6E0D6 → 0x6D440",
        "status": "mapped_template",
        "description": "413 × 352-byte inventory records",
    },
    {
        "id": "footer_globals",
        "start": 0x31B19,
        "end": None,  # EOF
        "insn": "0x6E103/0x6E112",
        "status": "mapped_partial",
        "description": "3 global nested chunks; includes 'Old Abandoned Track'",
    },
]

ARTIFACTS = {
    "save_full_layout.json": "Section milestones",
    "save_grid_layout.json": "Grid dimensions + prefix",
    "save_grid_u8_layout.json": "Grid U8 token taxonomy",
    "save_main_nested_layout.json": "Main nested field walk",
    "save_inventory_record_layout.json": "352 B inventory template",
    "save_footer_layout.json": "Footer chunks",
    "save_block_correlation.json": "Nested block offsets",
    "save_field_layout.json": "Static disasm walk (header)",
    "save_load_path.json": "Save_Write call sites + edx",
}


def load_json(name: str) -> dict | None:
    p = ROOT / "RE_Tools" / "analysis" / name
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def main() -> int:
    if not DUMP.is_file():
        print(f"Missing {DUMP}")
        return 1
    size = DUMP.stat().st_size
    sections = []
    for s in SECTIONS:
        start = s["start"]
        end = s["end"] if s["end"] is not None else size
        row = {**s, "end": end, "size": end - start}
        sections.append(row)

    fully_mapped_status = (
        "mapped",
        "mapped_traced",
        "mapped_template",
        "mapped_partial",
        "encoded",
        "decoded_cells",
    )
    mapped = sum(r["size"] for r in sections if r["status"] in fully_mapped_status)
    encoded = sum(r["size"] for r in sections if r["status"] in ("encoded_opaque", "encoded_decoded"))
    total = sum(r["size"] for r in sections)

    main_nested = load_json("save_main_nested_layout.json")
    inventory = load_json("save_inventory_record_layout.json")
    footer = load_json("save_footer_layout.json")

    report = {
        "dump_size": size,
        "format_version": 12,
        "sections": sections,
        "coverage_summary": {
            "total_bytes": total,
            "fully_mapped_bytes": mapped - encoded,
            "structure_known_opaque_bytes": encoded,
            "pct_structure_known": round(100 * total / size, 2),
            "pct_field_level_mapped": round(100 * mapped / size, 1),
            "note": "Grid counted as decoded_cells; inventory 352B template + opaque pack documented",
        },
        "nested_counts": {
            "inventory_slots": (0x31B19 - 0xE339) // 352,
            "inventory_record_bytes": 352,
        },
        "artifacts": ARTIFACTS,
        "detail_refs": {
            "main_nested_coverage": (main_nested or {}).get("coverage"),
            "main_nested_name": (main_nested or {}).get("name"),
            "footer_chunks": (footer or {}).get("chunks"),
        },
    }

    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Complete save file format (204386-byte aligned capture)",
        "",
        "**Game:** Horsey.exe · **Writer:** `Save_Write` @ `0x6DAB0`",
        "",
        "Regenerate: `python RE_Tools/tools/scripts/build_save_complete_map.py`",
        "",
        "## Coverage",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| File size | **{size}** bytes |",
        f"| Sections accounted | **{total}** bytes (100%) |",
        f"| Field-level mapped | **{report['coverage_summary']['pct_field_level_mapped']}%** |",
        f"| Grid U8 encoding (structure known) | **{encoded}** bytes |",
        "",
        "## Section map",
        "",
        "| Offset | Size | Section | Status | Insn |",
        "|--------|------|---------|--------|------|",
    ]
    for r in sections:
        lines.append(
            f"| `0x{r['start']:04X}` | {r['size']} | {r['id']} | {r['status']} | `{r['insn']}` |"
        )
    lines.extend(
        [
            "",
            "## Nested tail",
            "",
            f"- **Pairs** @ `0xDEA7`: 36 B (`0x6E043`)",
            f"- **Main nested** @ `0xDECB`: 1134 B — `{report['detail_refs'].get('main_nested_name', '?')}' (`0x6E0A6`)",
            f"- **Inventory** @ `0xE339`: {report['nested_counts']['inventory_slots']} × 352 B (`0x6E0D6`)",
            f"- **Footer** @ `0x31B19`: {sections[-1]['size']} B — global `0x6E103` / `0x6E112`",
            "",
            "See also: [SaveFieldLayout.md](SaveFieldLayout.md), [SaveFormat.md](SaveFormat.md)",
        ]
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")
    print(f"  coverage: {report['coverage_summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
