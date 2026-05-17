# CRF glyph parse (inside `Font_LoadOrInit` @ `0x7F8A0`)

**Verified:** Capstone on `Game/Horsey.exe` — `disasm_crf_glyph_parse.py`

**Artifact:** `RE_Tools\analysis\crf_glyph_parse.json`

## On-disk vs in-memory

| Stage | Format |
|-------|--------|
| **File** section1 | Records: `u16` + `0xF8`/`0xF9` + payload ([CrfOpcodeSemantics.md](CrfOpcodeSemantics.md)) |
| **Loader** | Sequential stream read; **8-byte payload** → `0x118`-byte runtime glyph |

There is **no** `cmp al, 0xF8` in `.text` — tags are consumed as length-prefixed stream bytes, not immediate compares.

## Parse loops (RVA)

### 1. Section2 — `0x7FBB0` (8 bytes × N)

Alloc `count×8` buffer; each entry = eight `ReadU8` calls. Source: section2 blob after header.

### 2. Section1 — `0x7FC31` (3 bytes × M)

Triples via `ReadU8`,`ReadU8`,`ReadU16` — auxiliary table (kerning index / char map).

### 3. Glyphs — `0x7FC90` (8 bytes × G) ← **maps `F9` payload**

For each 8-byte run at stream cursor `r8`:

| Byte(s) | → `glyph + 0x118 * index` |
|---------|---------------------------|
| `[0]` | glyph index |
| `[1]` | float @ `+0x10` (÷ line height from header) |
| `[2]` | float @ `+0x18` |
| `[1]+[3]` | float @ `+0x14` |
| `[2]+[4]` | float @ `+0x1c` |
| `[3..6]` | bytes @ `+0x24`..`+0x27` |
| `[7]` + header | dword advance @ `+0x20` |

**Example** (`quip.crf` record @ +8): `07 00 f9 03 22 17 35 05 …` → eight payload bytes after tag align with this layout (`03` index, metrics follow).

### 4. Kern — `0x7FD60` (3 bytes × K)

`[0]` = glyph index, `[1]` → byte @ `glyph+0x28`.

## Draw — `Font_DrawString` @ `0x80D10`

- `rcx` = font object (`g_font_*` @ `0x313538`..`0x313548`)
- `r12` = text bytes
- Charset / width: `rip+0x262e50`, `rip+0x310620`
- `dl==0x20` → space (`font+0x2320`); `dl==0xFF` → extended layout path
- Per-glyph advance: `dword [glyph+0x20]`; optional `byte [glyph+0x28]` kerning

Frida: `frida_font_draw.py`

See also: [FontLoad.md](FontLoad.md), [FontDraw.md](FontDraw.md)
