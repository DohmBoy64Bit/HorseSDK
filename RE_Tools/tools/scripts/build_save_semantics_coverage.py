"""
Aggregate semantic decode coverage for save1.dat aligned capture.

Output: RE_Tools/analysis/save_semantics_coverage.json
        RE_Tools/docs/SaveSemanticsCoverage.md
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AN = ROOT / "RE_Tools" / "analysis"
OUT_JSON = AN / "save_semantics_coverage.json"
OUT_MD = ROOT / "RE_Tools" / "docs" / "SaveSemanticsCoverage.md"


def load(name: str) -> dict | None:
    p = AN / name
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> int:
    dump_size = (AN / "save_buffer_dump.bin").stat().st_size if (AN / "save_buffer_dump.bin").is_file() else 0
    ctx = load("save_context_block.json")
    main_n = load("save_main_nested_layout.json")
    inv = load("save_inventory_summary.json")
    footer = load("save_footer_layout.json")
    footer_genes = load("save_footer_gene_packs.json")
    genes = load("save_inventory_genes.json")
    grid = load("save_grid_cells.json")

    sections = [
        {
            "id": "format_version",
            "bytes": 4,
            "status": "complete",
            "detail": "u32 = 12",
        },
        {
            "id": "global_registry",
            "bytes": 0x959 - 0x14,
            "status": "complete",
            "detail": "71 horse names + flags (save_global_names.json)",
        },
        {
            "id": "ctx_main",
            "bytes": 0xA3D - 0x959,
            "status": "complete" if ctx and ctx.get("coverage", {}).get("pct", 0) >= 95 else "partial",
            "detail": "save_context_block.json",
            "pct": ctx.get("coverage", {}).get("pct") if ctx else 0,
        },
        {
            "id": "horse_vector",
            "bytes": 0xA59 - 0xA3D,
            "status": "complete",
            "detail": "count=3, 4×u16 per horse",
        },
        {
            "id": "grid",
            "bytes": 0xDEA7 - 0xA59,
            "status": "complete",
            "detail": f"90k cells — {grid.get('cells_decoded', grid.get('cell_count', '90000'))} in save_grid_cells.json",
        },
        {
            "id": "pairs",
            "bytes": 0xDECB - 0xDEA7,
            "status": "complete",
            "detail": "4×(u32,u32)",
        },
        {
            "id": "nested_main",
            "bytes": 0xE339 - 0xDECB,
            "status": "mapped" if main_n else "partial",
            "detail": f"name={main_n.get('name')!r}; b8={main_n.get('d440_header', {}).get('b8_vector_count')}; "
            f"trace {main_n.get('coverage', {}).get('pct_traced', 0)}%",
            "gap_note": "vcall+0x48 variable blobs in trace gaps",
        },
        {
            "id": "inventory",
            "bytes": 0x31B19 - 0xE339,
            "status": "complete" if inv else "partial",
            "detail": f"{inv.get('count', 413)}×352 B; gene pack decoded (0x6D3B0)",
            "ptr_zero": inv.get("ptr_zero_slots") if inv else None,
        },
        {
            "id": "footer",
            "bytes": dump_size - 0x31B19,
            "status": "complete" if footer and footer.get("coverage", {}).get("pct", 0) >= 50 else "partial",
            "detail": (
                "track name + 2×0xF0 gene packs @ 0x31B41/0x31CE6 (0x6D2A0)"
                if footer_genes
                else "Old Abandoned Track + globals"
            ),
            "pct": footer.get("coverage", {}).get("pct") if footer else 0,
        },
    ]

    complete = sum(1 for s in sections if s["status"] == "complete")
    report = {
        "dump_size": dump_size,
        "sections": sections,
        "summary": {
            "byte_layout": "100%",
            "semantic_complete_sections": complete,
            "semantic_total_sections": len(sections),
            "gene_codec": "0x6D3B0 verified round-trip",
            "runtime_genetics": "save_genetics_runtime.json",
            "deferred": "SaveFutureWork.md",
            "remaining_gaps": [
                "main nested vcall+0x48 per-component byte layout (variable)",
                "inventory slots with ptr_item_count>8 need per-slot trace (nonstandard header)",
            ],
        },
    }
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Save semantics coverage",
        "",
        f"**Dump:** `{dump_size}` bytes · **Layout:** 100% · **Semantic sections complete:** {complete}/{len(sections)}",
        "",
        "| Section | Status | Notes |",
        "|---------|--------|-------|",
    ]
    for s in sections:
        lines.append(f"| {s['id']} | {s['status']} | {s['detail']} |")
    lines.extend(
        [
            "",
            "## Remaining gaps",
            "",
        ]
        + [f"- {g}" for g in report["summary"]["remaining_gaps"]]
        + [
            "",
            "## Deferred (not on-disk save format)",
            "",
            "See [SaveFutureWork.md](../docs/SaveFutureWork.md) — includes **`0xAE470`** runtime genetics.",
            "",
            "Regenerate: `python RE_Tools/tools/scripts/run_save_layout_pipeline.py --skip-frida`",
        ]
    )
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_JSON} complete={complete}/{len(sections)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
