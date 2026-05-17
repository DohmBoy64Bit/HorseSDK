# `Font_DrawString` @ `0x80D10`

**Verified:** Capstone on `Game/Horsey.exe`; Frida `frida_font_draw.py`.

## Signature (inferred)

```c
// rcx=font*, rdx/ymm=position, r8d=flags, stack=color, r12=char* text
void Font_DrawString(Font *font, ..., const char *text /*r12*/, int flags /*r9*/);
```

**Callers:** 102 sites (UI, menus, in-world labels). Often preceded by `ClampInt3` @ `0xC12D0` for layout.

## Glyph runtime object (`0x118` bytes each)

Built from `.crf` section1 by parse loop @ **`0x7FC90`** — see [CrfGlyphParse.md](CrfGlyphParse.md).

| Offset | Set @ parse | Used @ draw |
|--------|-------------|-------------|
| `+0x10`..`+0x1c` | float metrics (÷ line height) | layout |
| `+0x20` | advance (dword) | cursor += on draw |
| `+0x24`..`+0x27` | bytes | — |
| `+0x28` | kerning byte | add to cursor when prior glyph matches |
| `+0x2320` | space width (font header) | `dl==0x20` |

## Draw loop (@ `0x80D90`)

1. `movzx eax, cl` — next char from `r12`.
2. Index via **`[rip + 0x262e50]`** (charset / codepage).
3. Width class via **`[rip + 0x310620]`**:
   - **`0x20`** — space → add `font+0x2320`
   - **`0x00`** — skip
   - **`0xFF`** — extended glyph run (`0x80E17`)
   - else — use glyph index `r8d`, metrics from `font + index*0x118`

## Font globals (data)

| Global RVA | Font |
|------------|------|
| `0x313538` | `habit_mono` |
| `0x313540` | `quip` |
| `0x313548` | `capy_bold` |

Set @ `GameState_InitMain` (`0x97493`, `0x9752B`, …). UI draw cluster uses **`habit_mono`** @ `0x35624`–`0x35D27`.

## Related

- [FontLoad.md](FontLoad.md) — `0x7F8A0`
- [CrfGlyphParse.md](CrfGlyphParse.md) — 8-byte record → glyph struct
