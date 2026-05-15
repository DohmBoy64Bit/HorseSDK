# `.crf` section-1 opcode semantics (Capstone + data scan)

**Script:** `crf_opcode_trace.py` · **Artifact:** `RE_Tools\analysis\crf_opcode_trace.json`

Container layout: [DataFileFormats.md](DataFileFormats.md) / `crf_font.py`.

## Record markers (verified scan)

Records begin with **u16 length** + **tag byte** (`0xF8` / `0xF9`):

| Prefix (hex) | Tag |
|--------------|-----|
| `09 00 f8` | `0xF8` glyph_run_f8 |
| `09 00 f9` | `0xF9` glyph_run_f9 |
| `07 00 f8/f9` | shorter variant |

## Per-font tag stats

### `capy_bold.crf`

- **0xf9** `glyph_run_f9`: 19 records, len 7–976 (avg 98.7)
- **0xf8** `glyph_run_f8`: 2 records, len 8–215 (avg 111.5)
- **0x0** `unknown`: 1 records, len 289–289 (avg 289.0)

### `habit_mono.crf`


### `habit_narrow_bold.crf`

- **0xf8** `glyph_run_f8`: 9 records, len 8–55 (avg 20.1)
- **0xf9** `glyph_run_f9`: 64 records, len 7–769 (avg 30.3)
- **0x0** `unknown`: 1 records, len 57–57 (avg 57.0)

### `quip.crf`

- **0xf8** `glyph_run_f8`: 8 records, len 8–55 (avg 21.8)
- **0xf9** `glyph_run_f9`: 64 records, len 7–4440 (avg 86.6)
- **0x0** `unknown`: 3 records, len 8–57 (avg 29.7)

### `snuggle.crf`

- **0xf8** `glyph_run_f8`: 8 records, len 8–55 (avg 21.8)
- **0xf9** `glyph_run_f9`: 62 records, len 7–1223 (avg 36.0)
- **0x0** `unknown`: 6 records, len 8–65 (avg 29.8)

### `virtue_narrow_bold.crf`

- **0xf8** `glyph_run_f8`: 8 records, len 8–55 (avg 21.6)
- **0xf9** `glyph_run_f9`: 67 records, len 7–1375 (avg 37.0)
- **0x0** `unknown`: 4 records, len 17–57 (avg 34.5)

## Exe loader cluster (`0xBF200`)

- `0xbf104` → `0xe9cd0`
- `0xbf10f` → `0x225410`
- `0xbf118` → `0x27920`
- `0xbf1b8` → `0x27830`
- `0xbf210` → `0x82500`
- `0xbf24b` → `0x21e450`
- `0xbf287` → `0x21e450`
- `0xbf2c6` → `0x6f3c0`
- `0xbf2e0` → `0x27830`
- `0xbf30a` → `0xc0900`
- `0xbf345` → `0x21e450`
- `0xbf381` → `0x21e450`
- `0xbf3cd` → `0x21e450`
- `0xbf3e6` → `0x225894`
- `0xbf3f6` → `0x27920`

## Status

Interpreter @ font draw path **UNVERIFIED** — marker/record boundaries only.
Next: hook `0x6F3C0` / CRF loader callees under Frida when drawing text.
