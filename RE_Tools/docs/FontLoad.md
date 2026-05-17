# Font load path (`.crf` / `.fnt`)

**Verified on `Game/Horsey.exe`** — Capstone + Frida (`frida_font_load.py`).

## Correction: `0x6F3C0` is not the read hook

| RVA | Role |
|-----|------|
| **`0x7F8A0`** | **`Font_LoadOrInit`** — opens font by `std::string` path, parses header via stream readers |
| **`0x6FB90`** | **`Stream_OpenRead`** — `fopen` path (`0x225894`), size via `0x226948`, buffer @ `0x31041C` region |
| `0x6F3C0` | **Write/append** stream (also `Save_Write` @ `0x6DB95`; font **path builder** @ `0xBF2C6`) |

Frida on `0x6F3C0` with `.crf` path filter logs **0 hits** because reads never go through that function.

## Init sequence (`GameState_InitMain` @ `0x97110`)

Capstone @ `RE_Tools/analysis/disasm_GameState_InitMain.txt`:

1. Build `std::string` stem (`habit_mono`, `quip`, …) via `0xC44C0`.
2. Append `".crf"` on stack (`0x97435`–`0x97467`).
3. **`call 0x7F8A0`** with font context + path (`0x97467`, `0x974FF`, …).
4. `operator_new(0x11810)` + `memset` — per-font heap object (~71 KiB max).

Example (exe strings @ disasm):

```text
0x97435  movabs rcx, 0x6672632e70697571  ; "quip.crf"
0x97467  call 0x14007f8a0                 ; Font_LoadOrInit
```

## `Font_LoadOrInit` @ `0x7F8A0` (tail)

| Step | RVA | Callee | Notes |
|------|-----|--------|-------|
| Path prefix | `0x7F91A` | `0x27830` | Prepends `data\`-like prefix when flag set |
| Open | `0x7FA31` | `0xBFB70` | VFS / path root |
| Concat | `0x7FA40` | `0x82240` | `std::string` append |
| Read file | `0x7FA4B` | **`0x6FB90`** | `fopen` + read into stream buffer |
| Parse | `0x7FA90`–`0x7FC44` | **`0x705D0` / `0x70670` / …** | Same readers as save ([SaveGhidraCrossref.md](SaveGhidraCrossref.md)) |

## Frida

```bat
python RE_Tools\tools\scripts\frida_font_load.py --seconds 20
```

Logs paths at **`0x7F8A0`** (load) and **`0x6FB90`** (fopen) — expect `quip.crf`, `habit_mono.crf`, etc.

## Related

- [CrfOpcodeSemantics.md](CrfOpcodeSemantics.md) — section-1 record envelopes
- [CrfLoaderVm.md](CrfLoaderVm.md) — `0xBF2xx` path **builder** → write stream `0x6F3C0`
- [DataFileFormats.md](DataFileFormats.md) — 16-byte `.crf` header
