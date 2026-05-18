# Nested save format (`0x6D440` / `0x6D5C0`)

**Verified:** `Game/Horsey.exe`, `save_writer_trace.json`, `save_buffer_dump.bin`

## WriteNestedSave order (`FUN_14006d440`)

1. `WriteStdString` @ object+`0x18` (name)
2. `WriteU32` ptr-vector count `(end+0x138 - beg+0x130) >> 3`
3. Per ptr: `WriteNestedItem` @ `0x6EC40`
4. `WriteU32` merge run index (`0x6D4F1`)
5. `WriteU32` b8-vector count `(end+0xC0 - beg+0xB8) >> 3`
6. Per b8 entry: `WriteU32` `[component+8]` (type tag) + vcall **`+0x48`** payload
7. `WriteVec2F32` @ object+`0x0C`
8. `WriteU32` flag (`[obj+0x150] != 0`)
9. If flag: `0x6D2A0` gene pack (`0xF0` bytes) @ `+0x150`

## ReadNestedSave (`FUN_14006d5c0`)

Mirrors write; b8 read uses type dispatch (`0`, `1`, `3`, other) then vcall **`+0x50`**.

## Inventory on disk

- Anchored by `WriteStdString` @ caller **`0x6E0D6`**
- **Not** fixed 352 B for every slot (e.g. slot 50 = **434 B** in trace)
- Gene pack @ record+**`0x51`** (`0x6D3B0` unpack)
- Parser table: `save_inventory_blocks.json` / `horse_save_inventory_blocks.inc` (**410** trace `WriteStdString` spans, contiguous 145376 B)
- **413** = `145376 / 352` only; not an on-disk slot count
- Some spans are **name-only** (e.g. 10 B `"Bubber"` @ `0x2F58A`); round-trip keeps each span as `raw_block` bytes

## Main world nested

- Caller **`0x6E0A6`**, sample name **`unknown`**, **1134 B**
- b8 count **343**; blob **1079 B** + **32 B** tail (vec2 + flag)
- b8 wire (`nested_b8_codec.py`, `probe_main_nested_b8.py`):
  - **Type 1** @ `0xDEE2`: `u32(1)` + 57 B — **15 B active** (`packed` + 3×`u32` + 2×`u8` @ obj `+0xA0..+0xAC`) — `0x102DC0`/`0x102E20` — [save_type1_b8.json](../analysis/save_type1_b8.json)
  - **Implicit EOF (124 slots):** `ReadU32` returns 0 @ `0x6D6F5` → default `operator_new(0xC8)` in memory, no file bytes — [SaveSemantics.md](SaveSemantics.md)
  - **Type 2 blocks**: **164 B** = `u32(2)` + **4×40 B** inner props
  - **Tail**: one **type-0 packed u8** per byte (`0x6D8C0`); 198 B in sample
  - Header **343** = in-memory slots; **on_disk** ≈ 219 + **implicit_eof** ≈ 124 @ `ReadU32` `0x70540`
  - Type-2 **inner 40 B** (`FUN_14006d8c0` / `0x0A30F0` component):
    | Off | Field | Disasm |
    |-----|--------|--------|
    | +0 | `packed_u8` | packed flags from `[+0x10]`, `[+0x11]`, `[+0x38]` |
    | +1 | `cell_flag_c` | `[obj+0x0C]` u8 @ **0x6D8EF** — same offset as `SaveGridCell.flag_c` |
    | +2 | `grid_cell_type_id` | `[obj+0x48]` @ **0x6D8F8**; ctor default **0x17** → type **23** = **GrassLand** (`0x1167B0` table) |
    | +3 | pad | full write also emits `word [+0x44]` @ **0x6D901** |
    | +4..+0xB | zeros | |
    | +0xC | `coord8[8]` | tile key bytes |
    | +0x14 | `f32[4]` | `[+0x28..0x34]` |
    | +0x24 | `link_u32` | often 2 |
    See `grid_type_lookup.json` (`grid_type_lookup.py`) for type-id names. Aliases `byte_obj_0x0C` / `ext_*` kept in JSON.

## Footer

- Starts @ file **203545** (`0x31B19`)
- **841 B** total (303 + 421 + 117) — **not** a normal `WriteStdString` header at offset 0

## Code

| Artifact | Role |
|----------|------|
| `nested_save_codec.py` | Python read/write |
| `save_file_codec.py` | Full-file parse (EOF-checked) |
| `RE_Tools/src/horse_save/` | C loader |
