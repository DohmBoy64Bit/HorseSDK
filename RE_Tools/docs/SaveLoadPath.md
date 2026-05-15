# Save load / save write I/O (Horsey.exe)

**Verified:** Capstone on `Game/Horsey.exe`, `save_buffer_dump.bin`, Frida `frida_phase1.json`.

## Top-level functions (Ghidra-confirmed)

| RVA | Ghidra | Role |
|-----|--------|------|
| **`0x6DAB0`** | `FUN_14006dab0` | **Save_Write** — `ctx` → stream → **`0x6FD90`** → `save%d.dat` |
| **`0x6E2B0`** | `FUN_14006e2b0` | **Save_Load** — open `save%d.dat`, full deserialize into `ctx` |
| **`0x6E643`** | (inner) | **Save_LoadFromBuffer** — same parser on **in-memory** read cursor (grid @ `0x6E700`) |

See [SaveGhidraCrossref.md](SaveGhidraCrossref.md) for full write/read order and `ctx` offsets.

Startup may call **`Save_Write` @ `0x9828C`** with `edx=1` in some paths; normal load uses **`0x6E2B0`** @ `0x103B7F`. Quit path **`0xBED11`** calls **`0x71F60`** (settings XML), not `0x6DAB0` — see [Save_Write.md](Save_Write.md).

## Load flow (`0x6E2B0` file path)

1. Allocate **`0x28` × (width×height)** grid @ `[ctx+0x270]` (`0x6E68D`).
2. **Grid read loop** @ **`0x6E700`** — uses **`ReadU8` @ `0x705D0`** (mirror of `0x6DF30` / `0x6FEB0`).
3. **`ReadPairVec` @ `0x6F838`** → `[ctx+0x420]`.
4. **`ReadNestedSave` @ `0x6D5C0`** (mirror **`0x6D440`**) — main + inventory slots.
5. Per-item **`ReadNestedItem` @ `0x6EF80`** (mirror **`0x6EC40`**).

Disasm reference: `RE_Tools/analysis/disasm_save_load_io.txt`

## Read / write stream pairs

Artifact: `save_read_write_pairs.json` · script: `map_save_read_write_pairs.py`

| Read | Write | Type |
|------|-------|------|
| `0x70320` | `0x6FE10` | u32 |
| `0x705D0` | `0x6FEB0` | u8 |
| `0x70450` | `0x6FE50` | u16 |
| `0x704F0` | `0x6FE70` | u64 |
| `0x70670` | `0x6FF10` | f32 |
| `0x70890` | `0x6FFF0` | std::string |
| `0x6D5C0` | `0x6D440` | nested save |
| `0x6EF80` | `0x6EC40` | nested item |

Globals: **write** cursor `0x310410` / base `0x310418`; **read** cursor separate RIP-relative pointers (`0x705D0` uses `rip+0x29fe09`).

## Grid cell encoding (items 3–4)

**Decode script:** `decode_grid_cells.py` → `save_grid_cells.json`

| Bytes | Meaning |
|-------|---------|
| `0x3F`, `N` | Next **N** cells → type **6** (empty) |
| `0x3B`…`0x3E` | Type **0**, layer = byte − `0x3B` + global base |
| `b0`, `b1` | `type = b0 & 0x3F`, flags in bits 6–7, `layer = b1` |
| `0x0F`, `0x09` | Common: type **15**, layer **9** |

## Inventory opaque (item 3)

**Pack:** `0x6D2A0` @ `WriteNestedItem` `+0x2B8` (**0xF0** packed bytes).  
**Unpack:** `0x6D3B0` @ `ReadNestedItem` `+0x2B8` → **480-byte** working buffer (two **0xF0** tracks).

Decoded content = **240 diploid gene picks** (allele indices **0..3** → `g0`..`g3` in `genes.xml`).  
Disasm: `RE_Tools/analysis/disasm_inventory_pack.txt` · genes: `save_inventory_genes.json`.

After unpack, **`0x6EF80`** reads u64/u32/u16/u8/f32/string, then optional sparse **`+0xCC`** gene overrides, then **`0xADB30`/`0xAE470`**.

## File I/O

| RVA | Role |
|-----|------|
| `0x6F3C0` | **Read** open `save%d.dat` (`Save_Load` prologue) |
| `0x6FB90` | Read OK check (load fails → return 0) |
| `0x6FD90` | **Write** flush after `Save_Write` |
| `0x6E643` | Parse global read buffer (same codec as `0x6E2B0` body) |

## Tools

| Tool | Role |
|------|------|
| `decode_all_inventory_genes.py` | **410** trace inventory blocks → `save_inventory_genes_all.json` |
| `nested_b8_codec.py` | Main nested b8: type-1 wire + compact tail (`0x6D6F5` / `0x70540`) |
| `save_global_registry.json` | Per-entry C3100 layout from trace |
| `save_write_codec.py` | Parse → `write_save_bytes()` → byte-identical round-trip |
| `encode_cell_stream()` | Grid u8 writer @ `0x6DF30` (in `decode_grid_cells.py`) |
| `probe_main_nested_b8.py` | Main nested b8: type-1 + 5×164 B type-2 + type-0 tail |
| `horse_save_get_main_nested()` | C API — b8 header vs on-disk slot accounting |
| `horse_save_get_grid_summary()` | C API — grid decode stats @ `0x6DF30` |
| `RE_Tools/src/horse_save/` | C loader — `horse_save_load_path`, trace-sized inventory blocks |
| [SaveNestedFormat.md](SaveNestedFormat.md) | `0x6D440` / `0x6D5C0` nested save + b8 components |

Build CLI (from repo root):

```bat
cmake -S RE_Tools/src/horse_save -B build/horse_save
cmake --build build/horse_save
build\horse_save\horse_save_cli.exe RE_Tools\analysis\save_buffer_dump.bin
```

## Regenerate

```bat
python RE_Tools\tools\scripts\map_save_read_write_pairs.py
python RE_Tools\tools\scripts\decode_grid_cells.py
python RE_Tools\tools\scripts\decode_inventory_opaque.py
python RE_Tools\tools\scripts\decode_all_inventory_genes.py
```
