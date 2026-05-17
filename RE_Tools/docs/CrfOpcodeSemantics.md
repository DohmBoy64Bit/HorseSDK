# `.crf` section-1 opcode semantics

**Scripts:** `crf_opcode_trace.py`, `crf_record_decode.py`
**Artifacts:** `crf_opcode_trace.json`, `crf_record_decode.json`

Container: [DataFileFormats.md](DataFileFormats.md) / `crf_font.py`.

## Record envelope (verified scan)

| Field | Size | Notes |
|-------|------|-------|
| `prefix_u16` | 2 | Usually `7` or `9` (variant / BMFont-like size class) |
| `tag_byte` | 1 | `0xF8` = `glyph_run_f8`, `0xF9` = `glyph_run_f9` |
| `payload` | rest | Nested `u16` + tag bytes (`0xFA`–`0xFF` observed inside `F9` runs) |

## Embedded sub-tags (inside `F9` payloads, `quip.crf` sample)

- `0xf8`: 146 hits in scanned records
- `0xfb`: 93 hits in scanned records
- `0xfa`: 56 hits in scanned records
- `0xf9`: 52 hits in scanned records
- `0xfe`: 19 hits in scanned records
- `0xfc`: 14 hits in scanned records
- `0xff`: 11 hits in scanned records
- `0xfd`: 3 hits in scanned records

## Exe: not a separate VM

`.crf` files are read via **`Font_LoadOrInit` @ `0x7F8A0`** using the **same binary stream layer** as saves
(`ReadU8` @ `0x705D0`, `ReadU32` @ `0x70320`, `ReadF32` @ `0x70670` — [SaveGhidraCrossref.md](SaveGhidraCrossref.md)).
Section-1 **glyph records are not interpreted in a second pass** at load time in the traced path;
the game loads the file into a ~`0x11810`-byte heap object and consumes the **16-byte header** via stream readers @ `0x7FA90`–`0x7FC44`.

See [FontLoad.md](FontLoad.md) for path build + Frida hooks.
