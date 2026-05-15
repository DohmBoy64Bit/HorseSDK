# Save footer (841 B @ `0x31B19`)

**Verified:** `Game/Horsey.exe`, `save_buffer_dump.bin`, `save_writer_trace.json`

## Write path

| RVA | Role |
|-----|------|
| `0x6E103` | `WriteNestedSave` on global object **`DAT_14031a660`** |
| `0x6E112` | `vtable+0xB0` extra serializer (bytes not separately traced) |
| `0x6E11C` | `FUN_14006fd90` — flush stream |

Inside **`WriteNestedSave`** when `[nested+0x150] != 0`:

| RVA | Role |
|-----|------|
| `0x6D587` | `WriteU32` gene flag |
| `0x6D598` | `FUN_14006d2a0` pack **0x1E0** → **0xF0** wire bytes |
| `0x70220` | Bulk write **0xF0** B (Frida compact trace shows as **gap**, not per-byte `WriteU8`) |

Read mirror: `ReadNestedSave` @ **`0x6D7F5`** reads **0xF0** + unpack @ **`0x6D840`** (same as inventory **`0x6D3B0`**).

## Layout (sample `save1.dat`)

| File offset | Size | Kind | Meaning |
|-------------|------|------|---------|
| `0x31B19` | 8 | gap | Untraced prefix (`03 00 04 00 ff 00 00 10`) |
| `0x31B21` | … | traced | Settings stub (empty name, vec2, u32…) |
| **`0x31B41`** | **240** | **gene pack** | **`footer_gene_settings`** — `0x6D2A0` / `0xF0` |
| `0x31C48` | … | traced | Track panel (`Old Abandoned Track`, coords…) |
| **`0x31CE6`** | **240** | **gene pack** | **`footer_gene_track`** — after `"unknown"` + `u32 1` |
| `0x31DED` | … | traced | Epilogue floats + flags |

The former **“opaque 240 B blob”** is **not** unknown binary — it unpacks with **`inventory_pack_codec.unpack_6d3b0`** to **240×2** diploid gene indices (`0..3` → `genes.xml`).

## Semantics (sample)

| Field | Value | Source |
|-------|-------|--------|
| `track_display_name` | `"Old Abandoned Track"` | `WriteStdString` @ `0x31CC0` |
| `world_vec2` | `(176, 7056)` | `WriteVec2F32` @ `0x31C90` |
| `camera_vec2` | `(4240, 4016)` | `WriteVec2F32` @ `0x31CD3` |
| Settings gene pack | 240 B @ `0x31B41` | `decode_footer_gene_packs.py` |
| Track gene pack | 240 B @ `0x31CE6` | same codec as inventory `+0x51` |

**Runtime only:** `FUN_1400AE470` applies unpacked genes to horse parts after load — **not** stored in the pack. Pinned in [SaveFutureWork.md](SaveFutureWork.md).

## Tools

| Script | Output |
|--------|--------|
| `decode_save_footer_fields.py` | `save_footer_layout.json` |
| `decode_footer_gene_packs.py` | `save_footer_gene_packs.json` |

## C loader

`horse_save_parse_footer()` — track name, vec2s, and both **0xF0** gene packs via `horse_save_gene_unpack()`.
