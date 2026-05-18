# Ghidra cross-reference — save / load (May 2026)

**Source:** User-provided Ghidra export for `Game/Horsey.exe` (image base `0x140000000`).  
**Cross-check:** Capstone traces in `RE_Tools/analysis/disasm_save_load_io.txt`, `disasm_inventory_pack.txt`, aligned `save_buffer_dump.bin`.

## Top-level functions

| Ghidra name | RVA | Our name | Role |
|-------------|-----|----------|------|
| `FUN_14006dab0` | `0x6DAB0` | **Save_Write** | Build save into heap stream → `save%d.dat` |
| `FUN_14006e2b0` | `0x6E2B0` | **Save_Load** | Open `save%d.dat` → parse into `param_1` (ctx) |
| `FUN_14006e643` | `0x6E643` | **Save_LoadFromBuffer** | Parse **already-loaded** read cursor (grid @ `0x6E700`); used when buffer is in memory |
| `FUN_14006fd90` | `0x6FD90` | Flush write stream | `fwrite` after `Save_Write` |
| `FUN_14006f3c0` | `0x6F3C0` | Open read stream | Load path: attach file to read globals |
| `FUN_14006fb90` | `0x6FB90` | Read stream OK? | Load: abort if file missing/empty |

**Callers (from your xrefs):**

| Function | Calls |
|----------|--------|
| `FUN_140098040` @ `0x9828C` | `Save_Write` |
| `FUN_1401035e0` @ `0x103B7F` | `Save_Load` (`0x6E2B0`) |

`Save_Load` (`0x6E2B0`) contains the **full** deserialize (ctx fields, grid, pairs, nested, inventory). `Save_LoadFromBuffer` (`0x6E643`) is the **same parser** on the global read buffer without opening a file — same grid loop @ `0x6E700` we traced earlier.

## Stream helpers (read ↔ write)

| Ghidra (read) | RVA | Ghidra (write) | RVA |
|---------------|-----|----------------|-----|
| `FUN_140070320` | `0x70320` | `FUN_14006fe10` | `0x6FE10` | u32 |
| `FUN_140070620` | `0x70620` | `FUN_14006fef0` | `0x6FEF0` | u8 → u32 |
| `FUN_140070450` | `0x70450` | `FUN_14006fe50` | `0x6FE50` | u16 |
| `FUN_1400704f0` | `0x704F0` | `FUN_14006fe70` | `0x6FE70` | u64 |
| `FUN_140070670` | `0x70670` | `FUN_14006ff10` | `0x6FF10` | f32 |
| `FUN_1400706c0` | `0x706C0` | `FUN_14006ff30` | `0x6FF30` | vec2 f32 |
| `FUN_1400705d0` | `0x705D0` | `FUN_14006feb0` | `0x6FEB0` | u8 (grid) |
| `FUN_140070890` | `0x70890` | `FUN_14006fff0` | `0x6FFF0` | string |
| `FUN_14006d5c0` | `0x6D5C0` | `FUN_14006d440` | `0x6D440` | nested save |
| (in nested) `FUN_14006ef80` | `0x6EF80` | `FUN_14006ec40` | `0x6EC40` | nested item |
| `FUN_14006d3b0` | `0x6D3B0` | `FUN_14006d2a0` | `0x6D2A0` | gene pack @ item `+0x2B8` |

## `Save_Write` sequence (`FUN_14006dab0`)

High-level order (matches `save_writer_trace.json`):

1. `FUN_1400bee80("_saving_")` — UI/lock flag  
2. Slot checks on `[ctx+0x25c]` (`0x1c` / `0xd` / `-1`) and optional `FUN_1400dcbb0` per-horse slice save  
3. `FUN_140088000` → **`save%d.dat`** (`param_2` = slot index)  
4. `FUN_14006f3c0` — open **write** stream; `FUN_14006fd40(250000)` reserve  
5. `FUN_14006fe10(0xC)` — format version **12**  
6. `FUN_1400c3100()` — global horse name table (`0xC3100`)  
7. **Ctx block** — fields at `+0x254`, `+0x314`, `+0x268`, `+0x114` (f32), `+0x318`, `+0x308`, `+0x440`, bytes `+0x414`…`+0x41c`, vec2 `+0x39c`, `+0x410`  
8. **6× `SaveSlot6`** @ `+0x31c` (12 B each on disk)  
9. **13× `SaveRow13`** @ `+0x2cc` (8 B each)  
10. **Horse u16 vector** @ `+0x280`…`+0x288` (stride **0x24** in memory, 4× u16 written)  
11. **`[ctx+0x278]` / `[ctx+0x27c]`** — grid width / height  
12. **Grid loop** @ `0x6DF30` — `0x28` B cells, `WriteU8` encoding (`0x3F` runs, type 6 empty, layer TLS bases)  
13. **Pair vector** @ `+0x420` / `+0x428` — `FUN_14006fed0` + pairs  
14. **`FUN_14006d440(ctx)`** — main world nested (`name` = **`unknown`**)  
15. **Inventory loop** `RSI = 0 … 0x180` step 8: `[ctx+0x438]` → `FUN_14006d440` + **`vtable+0xB0`** serialize  
16. **`FUN_14006d440(DAT_14031a660)`** + **`vtable+0xB0`** — global footer  
17. **`FUN_14006fd90`** — flush to disk  

## `Save_Load` sequence (`FUN_14006e2b0`)

1. `save%d.dat` → `FUN_14006f3c0` / `FUN_14006fb90` (fail → return 0)  
2. Read same ctx fields as write (offsets above)  
3. Resize horse vector @ `+0x280` if needed (`FUN_14006f9a0` / `FUN_14006fb40`)  
4. Read horse u16s (4× per horse, stride **0x24**)  
5. Read width/height; allocate grid `operator_new(0x28 × w×h)` → `[ctx+0x270]`  
6. **Grid read loop** — mirror of write (`0x3F`+count, `0x3B`…`0x3E`, two-byte cells, type **0x14** when layer == `DAT_140310400`)  
7. `FUN_140106440(ctx,1)` — post-grid hook  
8. Read pairs → `[ctx+0x420]`  
9. **`FUN_14006d5c0(ctx)`** — main nested  
10. Inventory: for `i in 0..0x25` or `0..0x29` (build-dependent `DAT_140320940`), optional `FUN_140103f40` alloc + `FUN_14006d5c0` + **`vtable+0xB8`** deserialize  
11. Extra slot `0x25` horse object when `DAT_140320940 < 0xB`  
12. **`FUN_14006d5c0(DAT_14031a660)`** + **`vtable+0xB8`** — footer  
13. `FUN_14010a3d0` / horse position fixups on `[ctx+0x300]`  

## Grid TLS layer bases (verified strings in Ghidra)

| Global | Init string (little-endian) | Role in grid codec |
|--------|----------------------------|---------------------|
| `DAT_1403103e0` | `"Water"` | Empty-run layer for type **6** skips |
| `DAT_1403103f8` | `"Plain"` | Type **0** layer offset base (`byte - 0x3B + Plain`) |
| `DAT_140310400` | `"Pond"` | Special case → cell type **0x14** when layer byte matches |

These match `decode_grid_cells.py` / `save_grid_cells.json`.

## Inventory: write `+0xB0` vs read `+0xB8`

| Pass | Vtable offset | When |
|------|---------------|------|
| Write | `+0xB0` | After each `WriteNestedSave` in inventory loop |
| Read | `+0xB8` | After each `ReadNestedSave` in inventory loop |

Per-item body still uses **`ReadNestedItem` / `WriteNestedItem`** (`0x6EF80` / `0x6EC40`), including **`0x6D3B0`** gene pack @ `+0x2B8`.

## `SaveContext` offsets (`param_1` / `rdi`)

| Offset | Semantics (Ghidra-confirmed) |
|--------|------------------------------|
| `+0x114` | float (often `1.0f` on write) |
| `+0x254` | u32 — session / timestamp-like |
| `+0x268` | u32 — e.g. `21` in sample |
| `+0x278` | grid width (**400** in sample) |
| `+0x27c` | grid height (**225** in sample) |
| `+0x270` | pointer to grid cell array (**0x28** stride) |
| `+0x280` / `+0x288` | horse struct vector begin/end |
| `+0x2cc` | 13× row pairs (8 B on disk) |
| `+0x31c` | 6× slot structs (12 B on disk) |
| `+0x308` | active horse name as **u32 fourcc** (`"Dale"` = `0x656C6144`) |
| `+0x300` | pointer to current horse / player object — minimap probe: often **invalid** in farm; see [MapViewPosition.md](MapViewPosition.md) |
| `+0x25c` | save **mode / slot index** (`-1` full, `0xD` partial, `0x1C` special) |
| `+0x420` / `+0x428` | (u32,u32) pair vector |
| `+0x438` | pointer table — **0x180** bytes stepped in inventory loop (48 pointers) |
| `+0x394` / `+0x398` | footer camera floats — **static in Frida** while panning; not live view XY ([MapViewPosition.md](MapViewPosition.md)) |
| `+0x39C` | serialized blob (`WriteString`) — **not** live minimap position |

## Nested world object

- **`FUN_14006d440(ctx)`** on write / **`FUN_14006d5c0(ctx)`** on read uses the **main ctx** object.  
- Ghidra string at file `0xDECB`: **`unknown`** (`name_len = 7`).  
- `[nested+0xB8]` vector count **343** in sample → 343× (`WriteU32` + `vtable+0x48` blob) — explains main-nested trace gaps.

## What this confirms from prior RE

| Prior finding | Ghidra |
|---------------|--------|
| `Save_Write` @ `0x6DAB0` | `FUN_14006dab0` ✓ |
| ReadU8 grid @ `0x705D0` | `FUN_1400705d0` ✓ |
| `ReadNestedSave` @ `0x6D5C0` | `FUN_14006d5c0` ✓ |
| Gene pack `0x6D3B0` / `0x6D2A0` | Inside `0x6EF80` / `0x6EC40` ✓ |
| 413×352 inventory region | Write loop 48 pointers × nested; on-disk **352 B cadence** is per `WriteNestedSave` blob size, not pointer count |
| `save1.dat` = 204386 B | Produced by `Save_Write` → `0x6FD90` ✓ |

## Still variable (Ghidra does not name)

- Per-component **`vtable+0x48`** / **`+0xB8`** payload layouts (main nested 343 entries, footer).  
- Exact meaning of each **`SaveRow13`** / **`SaveSlot6`** field (offsets known, gameplay labels not in exe strings).

## Artifacts to use together

| Artifact | Purpose |
|----------|---------|
| This doc | Ghidra ↔ RVA ↔ ctx offsets |
| [SaveLoadPath.md](SaveLoadPath.md) | Stream API table |
| [SaveContext.h](SaveContext.h) | C struct sketch |
| [SaveSemanticsCoverage.md](SaveSemanticsCoverage.md) | Section-level completeness |
| `save_buffer_dump.bin` | Ground truth bytes |
| `RE_Tools/src/horse_save/` | C loader (`horse_save_parse_stream`, `horse_save_gene_unpack`) |
| `save_inventory_genes_all.json` | All **413** inventory gene packs (Python) |
