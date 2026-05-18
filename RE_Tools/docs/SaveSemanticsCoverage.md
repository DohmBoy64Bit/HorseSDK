# Save semantics coverage

**Dump:** `204386` bytes · **Layout:** 100% · **Semantic sections complete:** 9/9

| Section | Status | Notes |
|---------|--------|-------|
| format_version | complete | u32 = 12 |
| global_registry | complete | 71 horse names + flags (save_global_names.json) |
| ctx_main | complete | save_context_block.json |
| horse_vector | complete | count=3, 4×u16 per horse |
| grid | complete | 90k cells — 90000 in save_grid_cells.json |
| pairs | complete | 4×(u32,u32) |
| nested_main | complete | name='unknown'; b8=343; slots=343 |
| inventory | complete | 413×352 B; gene pack @+0x51; aligned 372 |
| footer | complete | track name + 2×0xF0 gene packs @ 0x31B41/0x31CE6 + 7 B FooterExtra @ rel 833 |

## Remaining gaps

- inventory slots with ptr_item_count>0 need WriteNestedItem @ 0x6EC40 field trace (optional)

## Deferred (not on-disk save format)

See [SaveFutureWork.md](../docs/SaveFutureWork.md) — includes **`0xAE470`** runtime genetics.

Regenerate: `python RE_Tools/tools/scripts/run_save_layout_pipeline.py --skip-frida`