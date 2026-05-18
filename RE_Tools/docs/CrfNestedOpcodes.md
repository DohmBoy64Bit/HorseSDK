# `.crf` nested opcodes (`0xF8`–`0xFF`)

**Verified:** `crf_nested_tlv.py` on `Game/data/*.crf`; loader RVAs on `Game/Horsey.exe`.

**Artifact:** `RE_Tools/analysis/crf_nested_tlv.json`

## TLV rule

Inside a top-level `F9` (or long `F8`) payload:

```
[u16 body_len][u8 tag][body_len bytes...]
```

`body_len` is the number of bytes **after** the tag byte (not including the 3-byte header).

Many records have a **4-byte prologue** before the first nested TLV (parent glyph index + 3 bytes).

## Tag meanings

| Tag | Typical `body_len` | Role | Exe correlation |
|-----|-------------------|------|-----------------|
| `0xF8` | 8 | Full glyph metric row | `CrfParse_GlyphEightByte` @ `0x7FC90` (from section2 buffer) |
| `0xF9` | 0 or nested | Sub-group container | Logical only; stream read via header loop |
| `0xFA` | 5 | Pair / metric patch | Section1 stream |
| `0xFB` | 5 | Metric patch | Section1 stream |
| `0xFC` | 1–5 | Advance override | Patches glyph `+0x20` |
| `0xFD` | 1 | Rare single-byte patch | Section1 stream |
| `0xFE` | 3 | Kerning triple `[value][glyph][extra]` | `CrfParse_KernThreeByte` @ `0x7FD60` → `glyph+0x28` |
| `0xFF` | varies | File extension sub-record | **Not** draw-time `dl==0xFF` @ `0x80E17` |

## Example (quip.crf `F8` payload, from artifact)

Prologue `05 2a 44 6b`, then:

- `05 00 F9` + 5 bytes — nested group
- `05 00 FA` + 5 bytes — pair patch
- `03 00 FE` + `04 2d 40` — kerning triple

## Loader order (exe)

1. **Section2** — `count×8` bytes via eight `ReadU8` @ `0x7FBB0` → glyph source for `0x7FC90`.
2. **Section1** — `count×3` header reads @ `0x7FC31` (`ReadU8`,`ReadU8`,`ReadU16`).
3. **Kern** — walk loaded triples @ `0x7FD60`.

See [CrfGlyphParse.md](CrfGlyphParse.md), [FontLoad.md](FontLoad.md).
