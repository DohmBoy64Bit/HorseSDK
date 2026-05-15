# `Game/save/save1.dat` — complete layout

**Aligned capture:** `save_buffer_dump.bin` = **204386** bytes (May 2026 pipeline).

| Doc | Content |
|-----|---------|
| [SaveCompleteFormat.md](SaveCompleteFormat.md) | Full section table + coverage |
| [SaveFieldLayout.md](SaveFieldLayout.md) | Per-field ctx / writers |
| [SaveInventoryRecord.h](SaveInventoryRecord.h) | 352 B inventory record |

**Regenerate everything:**

```bat
python RE_Tools\tools\scripts\run_save_layout_pipeline.py --skip-frida
python RE_Tools\tools\scripts\build_save_complete_map.py
```

(Use pipeline without `--skip-frida` to refresh dump + trace in-game.)

---

## Section map (100% bytes accounted)

| Offset | Size | Section | Writer RVAs |
|--------|------|---------|-------------|
| `0x0000` | 4 | Format version `12` | `0x6DCBB` |
| `0x0004` | 16 | Global header | `0xC3100` |
| `0x0014` | 2389 | Global horse names × **71** | `0xC3100` |
| `0x0959` | 228 | **SaveContext** (`rdi`) | `0x6DCCA`… |
| `0x0A3D` | 28 | Horse u16 vector | `0x6DDF9` |
| `0x0A59` | 8 | Grid 400×225 dims | `0x6DEA9` |
| `0x0A61` | 802 | Grid prefix `0x0F 0x09` × 401 | `0x6DF30` |
| `0x0D83` | 53540 | Grid cell **WriteU8** blob | `0x6DF30` |
| `0xDEA7` | 36 | Pair vector (4 pairs) | `0x6E043` |
| `0xDECB` | 1134 | Main nested (`unknown`) | `0x6E0A6` |
| `0xE339` | 145376 | Inventory **413×352** B | `0x6E0D6` |
| `0x31B19` | 841 | Global footer nested | `0x6E103` |

---

## Verified header (from dump)

| Offset | Value |
|--------|-------|
| `0x00` | `u32 12` |
| `0x04` | `u64` / timestamp-like `0x06D2A89F` |
| `0x0C` | `u32 22` |
| `0x10` | `u32 71` (global name count) |
| `0x18` | `"Dale"` (first registry string) |

---

## Tools

| Script | Output |
|--------|--------|
| `frida_dump_save_buffer.py` | `save_buffer_dump.bin` |
| `frida_trace_save_writers.py --compact` | `save_writer_trace.json` |
| `build_save_complete_map.py` | `save_complete_format.json`, `SaveCompleteFormat.md` |
| `decode_main_nested.py` | `save_main_nested_layout.json` |
| `decode_inventory_record.py` | `save_inventory_record_layout.json` |
| `decode_save_footer.py` | `save_footer_layout.json` |

---

## Grid encoding (`decode_grid_u8.py`)

| Token | Count (sample) | Meaning |
|-------|----------------|---------|
| `0x0F 0x09` | 401 prefix + 366 main | Default empty cell (2 B) |
| `0x3F` + byte | 656 | Skipped-row flush (`r14` @ `0x6DF6F`) |
| single `u8` | ~49k | Encoded non-empty cell |

See `save_grid_u8_layout.json`.

## Load path (item 1)

**Deserialize:** `Save_LoadFromBuffer` @ **`0x6E643`** — grid loop **`0x6E700`**, nested **`0x6D5C0`**, item **`0x6EF80`**.  
**Serialize:** `Save_Write` @ `0x6DAB0` → `0x6FD90` writes file.  
Read/write RVA table: `save_read_write_pairs.json` · [SaveLoadPath.md](SaveLoadPath.md).

## Grid cells (items 3–4)

**90 000 cells decoded** from grid stream (`decode_grid_cells.py` → `save_grid_cells.json`):

| Encoding | Meaning |
|----------|---------|
| `0x3F`, `N` | Skip **N** empty (type 6) cells |
| `0x3B`–`0x3E` | Type 0 + layer |
| `b0`, `b1` | Type + flags + layer byte |
| `0x0F`, `0x09` | Type 15, layer 9 (common) |

## Inventory opaque (item 3)

Packed blob **`0x6D2A0`** / unpacked **`0x6D3B0`** @ object `+0x2B8` (**240 B** on disk, **0x1E0** unpacked).

| Step | Detail |
|------|--------|
| Unpack | `0x6D3B0`: **0x78** loops × 2 packed bytes → 4 bytes (2 per track) |
| Nibble | `packed = ((hi+1)&7)<<3 \| ((lo+1)&7)`; stored values **0..3** |
| Track A | `unpacked[0..0xEF]` — **240** genes, index into **g0..g3** (see `genes.xml`) |
| Track B | `unpacked[0xF0..0x1DF]` — same for second allele column |
| Names | Order = **`genes.dat`** / **`genes.xml`** (240 entries) |

**Not the same as** `+0xCC` **`gene_slots[20]`** — those are sparse **ReadU32** `(index,value)` pairs in **`0x6EF80`** after unpack.

Scripts: `inventory_pack_codec.py`, `decode_inventory_opaque.py` → `save_inventory_genes.json`.

## Coverage

| Layer | Status |
|-------|--------|
| **Byte layout** | 100% — `save_complete_format.json` |
| **Semantics** | 7/9 sections complete — [SaveSemanticsCoverage.md](SaveSemanticsCoverage.md) |
| **Grid** | 90 000 cells — `save_grid_cells.json` |
| **Gene pack** | `0x6D3B0` → 240×2 alleles — `save_inventory_genes.json` |
| **Inventory** | 413×352 B — `save_inventory_all.json` |
| **Ctx** | 228 B traced — `save_context_block.json` |
| **Main nested** | name `unknown`, 343× vcall blobs — `save_main_nested_layout.json` |
| **Footer** | includes `Old Abandoned Track` — `save_footer_layout.json` |
| **Runtime genes** | `0xAE470` — `save_genetics_runtime.json` |

Regenerate: `python RE_Tools\tools\scripts\run_save_layout_pipeline.py --skip-frida`
