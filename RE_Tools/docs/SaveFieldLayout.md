# Save file field layout (aligned dump + trace)

**Aligned run (May 2026):** `save_buffer_dump.bin` == `save_writer_trace.json` final size **204386** bytes.

| Artifact | Script |
|----------|--------|
| Dump + trace | `run_save_layout_pipeline.py` |
| Section map | `map_save_full_layout.py` → `save_full_layout.json` |
| Grid tail decode | `decode_save_grid.py` → `save_grid_layout.json` |
| Block boundaries | `frida_trace_save_blocks.py` or `correlate_save_blocks_from_trace.py` → `save_block_correlation.json` |
| Global names | `save_global_names.json` (71 entries) |
| Grid strings (sample) | `save_grid_strings.json` |
| Ctx struct | `SaveContext.h` |

---

## File section map (verified)

| Section | File offset | Size (approx) | Insn / source |
|---------|-------------|---------------|---------------|
| Format version | `0x00` | 4 | `0x6DCBB` WriteU32(`12`) |
| Global header | `0x04` | 12 | `0xC3100`: u64 + u32 + count |
| Global horse registry | `0x14` | `0x959`−`0x14` ≈ **2377 B** | `0xC3100` loop: WriteStdString × **71** + u32 flags |
| **Ctx main block** | **`0x959`** | **`0xA3D`−`0x959`** ≈ **228 B** | `0x6DCCA`…`0x6DDC9` (`rdi` fields, loops) |
| Horse u16 vector | `0xA3D` | 4 + 3×8 = **28 B** | `0x6DDF9` count=**3**, `0x6DE30` 4×u16 |
| Fields `0x278` / `0x27C` | `0xA59` | 8 | `0x6DEA9` / `0x6DEB7` |
| Grid prefix | `0xA61` | ~802 B | Leading `(0x0F,0x09)` × (width+1) pairs |
| Grid main | `0xD83` | ~53 KB | `0x6DF30` WriteU8 loop (compact trace omits) |
| Pair vector | `0xDEA7` | 36 B | `0x6E043` — count **4** + 4×`(u32,u32)` |
| Main nested | `0xDECB` | **1134 B** | `0x6E0A6` → `0x6D440` (name **`unknown`**) |
| Inventory nested | `0xE339`+ | **352 B** × **~413** | `0x6E0D6` → `0x6D440` per slot |

---

## 1. Header `0x00`–`0x13`

| Offset | Writer | Value (sample) |
|--------|--------|----------------|
| `0x00` | WriteU32 | `12` |
| `0x04` | WriteU64 | `0x06D2A89F` (low dword) + `0` |
| `0x0C` | WriteU32 | `22` (`0x16`) |
| `0x10` | WriteU32 | count = **71** |

---

## 2. Global registry `0xC3100` (`0x14` … `0x958`)

**Not** the same as the in-game horse name in the ctx block — this is the **global name table** written before `rdi` serialization.

Examples from `save_global_names.json`:

| Offset | Name |
|--------|------|
| `0x14` | Dale |
| `0x4C` | Hoofy And The Blowfish |
| `0x7C` | Neptune |
| `0xB7` | Armano |
| `0xD7` | Baguette Magique |
| `0x101` | Call Me Ishmael |
| `0x144` | Ham Grenade |
| … | 71 total |

Each entry: **WriteStdString** + trailing **u32** flag words (see trace `0x6FE10` between strings).

---

## 3. Ctx block `0x959` … `0xA3C` (`rdi`)

Starts at first **WriteF32** (`0x6DCEB`, `ctx+0x114`). Ends before horse vector count @ `0xA3D`.

| Ctx `rdi+` | Insn | Notes |
|------------|------|-------|
| `0x254` | `0x6DCCA` | u32 |
| `0x314` | `0x6DCD5` | u32 |
| `0x268` | `0x6DCE0` | u32 |
| `0x114` | `0x6DCEB` | **f32** @ file `0x959` (`0x3F800000` = 1.0f in trace) |
| `0x318` | `0x6DCFE` | u32 |
| `0x308` | `0x6DD09` | active horse name (fourcc / string) |
| `0x440` | `0x6DD14` | u32 |
| flags `0x414`… | `0x6DD19`… | WriteU32FromU8 (4 B each) |
| `0x39C` | `0x6DD61` | WriteVec2F32 (8 B) |
| `0x410` | `0x6DD6C` | u32 |
| `0x31C`+ | `0x6DD71` | 6× slot (12 B each) |
| `0x2CC`+ | `0x6DDA3` | 13× row (8 B each) |

See `save_full_layout.json` → `ctx_main_block.events_by_offset` for dump-correlated values.

---

## 4. Horse u16 vector @ `0xA3D`

| Offset | Content |
|--------|---------|
| `0xA3D` | count = **3** |
| `0xA41`+ | 3 records × 8 bytes (4×`u16`) |

In-memory stride **0x24**; only four words serialized per horse.

---

## 5. Tail `0xA61`+ (grid / pairs / nested)

**Dimensions (sample):** `ctx+0x278` = **400**, `ctx+0x27C` = **225** → **90 000** in-memory cells (`imul` @ `0x6DF18`). Empty cells (`type == 6`) write **0 bytes**.

| File range | Size | Source |
|------------|------|--------|
| `0xA61`–`0xD82` | 802 B | **401** × `(0x0F, 0x09)` prefix (often `width+1`) |
| `0xD83`–`0xDEA6` | ~53 KB | Grid **WriteU8** @ `0x6DF30` / `0x6FEB0 |
| `0xDEA7`–EOF | ~147 KB | Pairs, nested saves, strings (visible in compact trace) |

**In-memory cell** (`SaveGridCell`, stride **0x28**): `type@0`, `extra@4`, `layer@8`, `flag_c@0xC`, `flag_d@0xD`.  
**`0x1167B0`** is a **type lookup** (returns `u32` in `eax`; `test eax` @ `0x6DFF3`) — not a stream writer.

**`WriteNestedSave` @ `0x6D440`:** `WriteStdString` + vector of `0x6EC40` items + `(u32,u32)` pair loop + `WriteVec2F32` + optional `0x6D2A0`.

Artifacts: `save_grid_layout.json`, `save_block_correlation.json` (`correlate_save_blocks_from_trace.py` or Frida + `correlate_save_blocks.py`).

**Correlated tail (aligned trace run):**

| Section | Offset | Size | Caller |
|---------|--------|------|--------|
| Pairs | `0xDEA7` | 36 | `0x6E043` |
| Main nested | `0xDECB` | 1134 | `0x6E0A6` |
| Inventory #0 | `0xE339` | 352 | `0x6E0D6` |
| Inventory #1 | `0xE499` | 352 | `0x6E0D6` |
| … | +`0x160` | 352 | ~413 total |

### 352-byte inventory record (`0x6D440` @ `0x6E0D6`)

| Rel | Size | Writer | Source |
|-----|------|--------|--------|
| `0x00` | 4+len | WriteStdString | `object+0x18` (often len **0**) |
| `0x04` | 4 | WriteU32 | ptr-vector count `(+0x138−+0x130)>>3` → **0** skips `0x6EC40` |
| `0x08` | 4 | WriteU32 | merge index `0x6D4F1` |
| `0x0C` | 4 | WriteU32 | `+0xB8` vector count |
| `0x10` | 8 | WriteVec2F32 | `object+0x0C` |
| `0x18`–`0x140` | ~297 | WriteU8 / vcall | **opaque** in compact trace (6D2A0 / `vtable+0x48`) |
| `0x141` | 8 | WriteU64 | `0x6EC40` `+0x2A8` |
| `0x149` | 4 | WriteU32 | tail |
| `0x14D` | 2 | WriteU16 | tail |
| `0x158` | 8 | WriteVec2F32 | tail |

Sample traced sub-fields @ `+0x1A`…`+0x4D`: `WriteU16`, `WriteU32` **`309`** @ `+0x20` (`+0x1F8`), `WriteVec2F32`, 4×`WriteF32`.

Full decode: `save_inventory_record_layout.json` · `decode_inventory_record.py` · `SaveInventoryRecord.h`

---

## Writers (RVA)

| RVA | Name | Bytes |
|-----|------|-------|
| `0x6FE10` | WriteU32 | 4 |
| `0x6FE70` | WriteU64 | 8 |
| `0x6FED0` | WriteU32 count | 4 |
| `0x6FFF0` | WriteStdString | 4 + len |
| `0x6FEF0` | WriteU32FromU8 | 4 |
| `0x6FF10` | WriteF32 | 4 |
| `0x6FE50` | WriteU16 | 2 |
| `0x6FF30` | WriteVec2F32 | 8 |

---

## 6. Complete file map

**100% byte coverage:** [SaveCompleteFormat.md](SaveCompleteFormat.md) · `save_complete_format.json`

| Artifact | Script |
|----------|--------|
| Full section map | `build_save_complete_map.py` |
| Load @ `0x6E643` | [SaveLoadPath.md](SaveLoadPath.md) · `save_read_write_pairs.json` |
| Grid 90k cells | `decode_grid_cells.py` → `save_grid_cells.json` |
| Inventory pack | `decode_inventory_opaque.py` (`0x6D2A0`/`0x6D3B0`) |
| Main nested 1134 B | `decode_main_nested.py` → `save_main_nested_layout.json` |
| Footer 841 B | `decode_save_footer.py` → `save_footer_layout.json` |

---

## Regenerate

```bat
python RE_Tools\tools\scripts\run_save_layout_pipeline.py --skip-frida
```

Skip Frida if artifacts exist:

```bat
python RE_Tools\tools\scripts\run_save_layout_pipeline.py --skip-frida
```
