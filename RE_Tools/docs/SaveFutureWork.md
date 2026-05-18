# Save RE — deferred work

Items intentionally **out of scope** for on-disk save format v12. Do not block round-trip or loader work on these unless gameplay/runtime integration is the goal.

**Pipeline:** `python RE_Tools/tools/scripts/run_save_semantics.py`  
Optional: `--frida-vtable`, `--frida-genetics`

## `FUN_1400AE470` — runtime genetics apply

| Item | Detail |
|------|--------|
| **RVA** | `0xAE470` |
| **Called from** | `0xADB30` after `ReadNestedItem` when `[item+0x234] >= 0` |
| **On disk** | **No** — not part of `save1.dat` bytes |
| **Relation to save** | After `0x6D3B0` unpacks the **0xF0** gene pack @ inventory `+0x51`, AE470 maps allele indices into live horse component bytes using RNG @ `0xC1900` |
| **Artifacts** | `save_genetics_runtime.json`, `disasm_genetics_ae470.txt`, `decode_genetics_ae470.py` |

**Pinned status:** documented; static disasm in `save_genetics_runtime.json`. Optional live capture: `frida_genetics_ae470.py` → `save_genetics_frida.json` (`run_save_semantics.py --frida-genetics`). Still **no** C phenotype editor.

## Footer `vtable+0xB0` / `+0xB8`

| Item | Detail |
|------|--------|
| **Write** | `0x6E112` — `call [rax+0xB0]` after `WriteNestedSave` |
| **Read** | `0x6EA08` — `call [rax+0xB8]` after `ReadNestedSave` |
| **On disk** | **7 B** @ footer blob rel **833** (`save_footer_extra_wire.json`); `horse_save_parse_footer()` → `HorseSaveFooterExtra`. Gene packs are separate @ `0x31B41`/`0x31CE6`. |
| **Pinned status:** **resolved** — `FooterExtra_Write` @ `0x1017C0`, `FooterExtra_Read` @ `0x101810`. |
| **Artifacts** | `save_footer_vtable.json`, `save_footer_extra_wire.json`, `decode_footer_extra_wire.py` |

## Other

- **Ctx rows/slots** — write: [save_ctx_semantics.json](../analysis/save_ctx_semantics.json); load mirror: [save_ctx_load_semantics.json](../analysis/save_ctx_load_semantics.json) (`0x6E470`/`0x6E4A0`).
- **343× b8** — [save_main_nested_b8_manifest.json](../analysis/save_main_nested_b8_manifest.json); type-1 tile index: [save_type1_xref.json](../analysis/save_type1_xref.json).
- **Hub doc:** [SaveSemantics.md](SaveSemantics.md) · run `run_save_semantics.py`.
