# Save semantics coverage

**Dump:** `204386` bytes · **Layout:** 100% · **Semantic sections complete:** 9/9

| Section | Status | Notes |
|---------|--------|-------|
| format_version | complete | u32 = 12 |
| global_registry | complete | 71 entries — `save_global_registry.json` |
| ctx_main | complete | save_context_block.json |
| horse_vector | complete | count=3, 4×u16 per horse |
| grid | complete | 400×225 @ `0x6DF30`/`0x6E700`; stream **52664 B** + **876 B** pad; decode fills **90000** cells (virtual type-6 after EOF) |
| pairs | complete | 4×(u32,u32) |
| nested_main | complete | b8 wire mapped (`probe_main_nested_b8.py`, C `horse_save_parse_main_nested`) |
| inventory | complete | **410** trace blocks (145376 B); gene @ +0x51 (`0x6D3B0`) |
| footer | complete | 841 B @ `0x31B19` — global `DAT_14031a660` @ `0x6E103` + `vtable+0xB0`; see [SaveFooterFormat.md](SaveFooterFormat.md) |
| round_trip | complete | `save_write_codec.py` **byte-identical** on `save_buffer_dump.bin` |

## Deferred (see [SaveFutureWork.md](SaveFutureWork.md))

- **`0xAE470`** runtime gene apply (after load; not on disk)
- Footer **`vtable+0xB0` / `+0xB8`** wire (separate from gene packs)

Regenerate: `python RE_Tools/tools/scripts/run_save_layout_pipeline.py --skip-frida`