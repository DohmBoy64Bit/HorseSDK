# Complete save file format (204386-byte aligned capture)

**Game:** Horsey.exe · **Writer:** `Save_Write` @ `0x6DAB0`

Regenerate: `python RE_Tools/tools/scripts/build_save_complete_map.py`

## Coverage

| Metric | Value |
|--------|-------|
| File size | **204386** bytes |
| Sections accounted | **204386** bytes (100%) |
| Field-level mapped | **100.0%** |
| Grid U8 encoding (structure known) | **0** bytes |

## Section map

| Offset | Size | Section | Status | Insn |
|--------|------|---------|--------|------|
| `0x0000` | 4 | format_version | mapped | `0x6DCBB` |
| `0x0004` | 16 | global_header | mapped | `0xC3100` |
| `0x0014` | 2373 | global_horse_registry | mapped | `0xC3100 loop` |
| `0x0959` | 228 | ctx_main_block | mapped | `0x6DCCA..0x6DDC9` |
| `0x0A3D` | 28 | horse_u16_vector | mapped | `0x6DDF9/0x6DE30` |
| `0x0A59` | 8 | fields_278_27c | mapped | `0x6DEA9/0x6DEB7` |
| `0x0A61` | 802 | grid_prefix | encoded | `0x6DF30` |
| `0x0D83` | 53540 | grid_main_u8 | decoded_cells | `0x6DF30` |
| `0xDEA7` | 36 | pair_vector | mapped | `0x6E043` |
| `0xDECB` | 1134 | nested_main | mapped_traced | `0x6E0A6 → 0x6D440` |
| `0xE339` | 145376 | nested_inventory | mapped_template | `0x6E0D6 → 0x6D440` |
| `0x31B19` | 841 | footer_globals | mapped_partial | `0x6E103/0x6E112` |

## Nested tail

- **Pairs** @ `0xDEA7`: 36 B (`0x6E043`)
- **Main nested** @ `0xDECB`: 1134 B — `unknown' (`0x6E0A6`)
- **Inventory** @ `0xE339`: 413 × 352 B (`0x6E0D6`)
- **Footer** @ `0x31B19`: 841 B — global `0x6E103` / `0x6E112`

See also: [SaveFieldLayout.md](SaveFieldLayout.md), [SaveFormat.md](SaveFormat.md)
