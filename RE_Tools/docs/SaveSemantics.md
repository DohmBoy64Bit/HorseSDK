# Save semantics (runtime + wire)

**Verified on:** `Game/Horsey.exe`, `RE_Tools/analysis/save_buffer_dump.bin`  
**Pipeline:** `python RE_Tools/tools/scripts/run_save_semantics.py`

---

## Main nested b8 (343 slots)

| On disk | Count | Mechanism |
|---------|------:|-----------|
| Type-1 record | 1 | `u32(1)` + 57 B — [save_type1_b8.json](../analysis/save_type1_b8.json) |
| Type-2 inners | 20 | 5×164 B blocks (`u32(2)` + 4×40 B) |
| Type-0 tail | 198 | one packed u8 per prop |
| **Implicit EOF** | **124** | `ReadU32` @ `0x70540` returns **0** → default component `operator_new(0xC8)` @ `0x6D700` |

**In-memory header count (343)** includes slots with **no wire bytes**; loader still allocates empty type-0 components.

Full per-slot list: [save_main_nested_b8_manifest.json](../analysis/save_main_nested_b8_manifest.json)

### Type-1 wire (15 B active)

| Off | Size | Exe | Field |
|-----|------|-----|-------|
| 0 | 1 | `0x6D8C0` | packed flags (shared with type-0) |
| 1 | 4 | `0x6FE10` | `[obj+0xA0]` u32 — **linear tile index** on 400-wide grid ([save_type1_xref.json](../analysis/save_type1_xref.json)) |
| 5 | 4 | `0x6FE10` | `[obj+0xA4]` u32 |
| 9 | 4 | `0x6FE10` | `[obj+0xA8]` u32 |
| 13 | 1 | `0x6FEF0` | `[obj+0xAD]` u8 |
| 14 | 1 | `0x6FEF0` | `[obj+0xAC]` u8 |

Write: `0x102DC0` · Read: `0x102E20` · Ctor when `type==1`: `0x101850` (`0xB0` bytes)

---

## SaveContext rows / slots

**Write-only in traced path** — staggered u32 pairs, not a dense `SaveRow13[13]` array on disk.

| Block | Loop | Disk |
|-------|------|------|
| `SaveRow13` | `0x6DDB0` | 13× (`u32` @ `ctx+0x298+N·4`, `u32` @ `ctx+0x2CC+N·4`) |
| `SaveSlot6` | `0x6DD80` | 6× 12 B (u8@+5, u32@+0, u8@+4) |

Sample `save1.dat`: mostly sentinels (`0xFFFFFFFF`, `0xFFFFFF01`); slot3 `byte+4` = **22** (0x16).  
Artifacts: [save_ctx_semantics.json](../analysis/save_ctx_semantics.json) · load mirror [save_ctx_load_semantics.json](../analysis/save_ctx_load_semantics.json)

---

## Footer `vtable+0xB0` / `+0xB8`

| Slot | RVA | Wire on footer nested object |
|------|-----|------------------------------|
| +0xB0 | `0x1017C0` | `u32` @ `+0x25C` + 3×`u8` @ `+0x261..0x263` |
| +0xB8 | `0x101810` | mirror read |

Not the 240 B **gene packs** (`0x6D2A0`). On-disk tail: **7 B** @ footer rel **833** — [save_footer_extra_wire.json](../analysis/save_footer_extra_wire.json). See [save_footer_vtable.json](../analysis/save_footer_vtable.json).

---

## Runtime genetics `0xAE470`

**Not in save file.** After inventory `ReadNestedItem`, `0xADB30` may call `0xAE470` to apply unpacked alleles to horse parts (`RNG` @ `0xC1900`).

Artifacts: [save_genetics_runtime.json](../analysis/save_genetics_runtime.json) · optional Frida [save_genetics_frida.json](../analysis/save_genetics_frida.json) (`--frida-genetics`) · [SaveFutureWork.md](SaveFutureWork.md)

---

## Scripts

| Script | Output |
|--------|--------|
| `decode_type1_b8.py` | `save_type1_b8.json` |
| `xref_type1_b8_grid.py` | `save_type1_xref.json` |
| `expand_main_nested_b8_manifest.py` | `save_main_nested_b8_manifest.json` |
| `map_save_ctx_semantics.py` | `save_ctx_semantics.json` |
| `map_save_load_ctx.py` | `save_ctx_load_semantics.json` |
| `decode_footer_extra_wire.py` | `save_footer_extra_wire.json` |
| `decode_genetics_ae470.py` | `save_genetics_runtime.json` |
| `frida_genetics_ae470.py` | `save_genetics_frida.json` |
| `resolve_footer_vtable.py` | `save_footer_vtable.json` |
| `decode_main_nested_vcall48.py` | `save_main_nested_vcall48.json` |
| `align_inventory_slots.py` | `save_inventory_aligned.json` |
| `compare_save_files.py` | `save_compare.json` |
| `run_save_semantics.py` | runs all of the above |
