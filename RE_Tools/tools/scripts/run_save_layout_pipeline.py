"""
Aligned save layout pipeline: dump + compact trace + section map.

  python RE_Tools/tools/scripts/run_save_layout_pipeline.py
  python RE_Tools/tools/scripts/run_save_layout_pipeline.py --skip-frida
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "RE_Tools" / "tools" / "scripts"


def run(name: str, *args: str) -> None:
    cmd = [sys.executable, str(SCRIPTS / name), *args]
    print(f"\n>>> {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-frida", action="store_true")
    ap.add_argument("--seconds", type=float, default=45.0)
    args = ap.parse_args()

    if not args.skip_frida:
        run("frida_dump_save_buffer.py", "--seconds", str(args.seconds))
        run("frida_trace_save_writers.py", "--compact", "--seconds", str(args.seconds))

    run("build_save_layout_from_trace.py")
    run("decode_save_grid.py")
    if not args.skip_frida:
        run("frida_trace_save_blocks.py", "--seconds", str(args.seconds))
    run("correlate_save_blocks.py")
    run("decode_inventory_record.py")
    run("decode_main_nested.py")
    run("decode_save_footer_fields.py")
    run("decode_footer_gene_packs.py")
    run("grid_type_lookup.py")
    run("decode_save_context_block.py")
    run("decode_all_inventory_slots.py")
    run("decode_all_inventory_genes.py")
    run("export_inventory_blocks.py")
    run("generate_inventory_blocks_c.py")
    run("save_file_codec.py")
    run("save_write_codec.py")
    run("probe_main_nested_b8.py")
    run("disasm_nested_save.py")
    run("decode_genetics_ae470.py")
    run("decode_grid_u8.py")
    run("find_save_load_path.py")
    run("map_save_read_write_pairs.py")
    run("decode_grid_cells.py")
    run("decode_inventory_opaque.py")
    run("build_save_complete_map.py")
    run("build_save_semantics_coverage.py")
    run("map_save_full_layout.py")
    run("parse_save_sections.py")
    print("\nDone. See RE_Tools/analysis/save_full_layout.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
