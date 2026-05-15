# Phase 1 exe notes (static + Frida)

**Binary:** `Game/Horsey.exe` · **Image base:** `0x140000000`  
**Policy:** [SOURCES.md](SOURCES.md) — verify on binary; repomix is reference only.

**Artifacts:**

| File | Script |
|------|--------|
| `analysis/disasm_phase1.txt` | `disasm_phase1.py` |
| `analysis/phase1_string_xrefs.json` | `phase1_string_xrefs.py` (Capstone RIP) |
| `analysis/phase1_pointer_xrefs.json` | `phase1_pointer_xrefs.py` (VA scan) |
| `analysis/frida_gameloop.json` | `frida_gameloop.py` |
| `analysis/frida_save.json` | `frida_save.py` (needs in-game save) |
| `analysis/frida_font.json` | `frida_font.py` (CreateFile/fopen; may be 0 if custom VFS) |
| `analysis/save_buffer_dump.bin` | `frida_dump_save_buffer.py` (heap save blob @ `Save_Write` leave) |

---

## 1. `GameMain_InitAndLoop` @ `0xBE0F0`

**Full doc:** [GameLoop.md](GameLoop.md) · **Map JSON:** `analysis/phase1_gamemain_loop_map.json` (`map_gamemain_loop.py`)

**Capstone** (`phase1_capstone_analyze.py` → `analysis/phase1_gamemain_loop.json`):

| Item | RVA | Notes |
|------|-----|--------|
| Function span | `0xBE0F0`–`0xBED82` | ~3.7 KB |
| Steam restart | `0xBE106` | `SteamAPI_RestartAppIfNecessary` |
| Early exit | `0xBE11A`, `0xBE148` | Restart / SDL init failure |
| Frame loop back | **`0xBECE7`** | 5 back-edges (main tick) |
| Poll first | `0xBEA8A` | `SDL_PollEvent` |
| Poll drain | `0xBEAA5` | inner queue loop |
| Swap | `0xBEAF0` | `SDL_GL_SwapWindow` |
| Quit branch | `0xBEAE7` → `0xBECE7` | `je` when shutdown flag set |

**Frida:** poll/swap order in [Frida_GameLoop.md](Frida_GameLoop.md). **Quit save** calls `Save_Write` from **`0xBED11`** (see §2).

---

## 2. `Save_Write` @ `0x6DAB0`

**Signature (Frida):** `Save_Write(void* ctx /*rcx*/, int mode /*edx*/)` — observed **`edx = 1`** for load, auto-save, and quit.

**Callers (E8):** `0x9828C`, `0x10A2C2`, `0x10A822`.

| Trigger | Site | Backtrace (RVA) |
|---------|------|-----------------|
| Startup load | `103B84` | `BE7C6` → `96F59` → `103B84` → `6EAB9` |
| Auto-save | **`10A2C2`** | `876FA` → `98392` → `10AB67` → `BEAD9` |
| Flush pair | **`10A822`** | right after `10A2C2` |
| Quit | **`BED11`** | exit from main loop |

**Path:** `Game\save\` built with std::string append @ **`6DB9A`** / **`6E2F4`** (`0x6F3C0`). Format string **`save%d.dat`** @ **`0x263830`**; flag **`_saving_`** @ **`0x263820`**.

**Capstone chain:** `6DB7E` → `88000` → `6DB95` → **`6F3C0`** → stream writers `6FD40` / `6FE10`.

**On disk:** `save_format_probe.json` — version `12` @ 0, **`Dale`** @ `0x18`.

**Frida:** `frida_phase1.py` → `frida_phase1.json` (startup + auto-save, no manual save).

**In-memory buffer dump (verified):** `frida_dump_save_buffer.py` hooks `Save_Write` on leave, reads heap base @ **`0x310418`** and write cursor @ **`0x310410`**, size = `writePtr - bufBase`. Output: `analysis/save_buffer_dump.bin` + `.json`. **Byte-identical** to `Game/save/save1.dat` (196328 bytes, headers match). Serialization uses incremental writers, not one `WriteFile` blob.

| RVA | Role |
|-----|------|
| `0x6FD40` | `StreamOpen` — reserve `ecx = 0x3d090` |
| `0x6FE10` | `WriteU32` |
| `0x6FEF0` | `WriteU8` |
| `0x6FF10` | `WriteF32` |
| `0x6FDF0` | `GetBufferSize` (mid-serialize; not full file size) |
| `0x310418` | buffer base pointer |
| `0x310410` | write cursor (end of serialized data) |

**First fields after `StreamOpen`** (`disasm_phase1_extended.txt` @ `0x6DCBB`):

| Order | Call | Source (ctx = `rdi`) |
|-------|------|----------------------|
| 1 | `WriteU32(12)` | format version → file `0x00` |
| 2 | `0x0C3100` | helper |
| 3 | `GetBufferSize` | |
| 4+ | `WriteU32` / `WriteU8` / `WriteF32` | `[rdi+0x254]`, `[rdi+0x314]`, `[rdi+0x268]`, `[rdi+0x114]` f32, … |

---

## 3. `SettingsLoader` @ `0x711B0`

**Caller:** `0xBE562` from `GameMain`.

**Strings (verified RVAs):** `horsey.tmx` `0x263850`, `settings.xml` `0x263860`.

**Ghidra:** Decompile `0x711B0`; confirm TinyXML/load order.

---

## 4. Font loaders (`.crf` / `n64.fnt`)

| Asset | Exe string RVA | Notes |
|-------|----------------|--------|
| `quip.crf` | `0x980DE` | |
| `n64.fnt` | `0x2658A8` | |
| `n64_0.png` | `0x265A80` | runtime texture name |
| `c64_0.png` | — | only inside BMF page block in `n64.fnt` |

**Capstone:** no direct `lea`/`mov` to those RVAs in `.text` — paths built like saves (string table @ `0xBF200`–`0xBF900`, calls **`0x6F3C0`** @ `0xBF2C6`, `0xBF56E`, `0xBF903`). See `analysis/phase1_crf_loader.json`.

**`.crf` format:** 16-byte header + section1 opcode stream — `crf_opcode_trace.json` (markers `09 00 f8`, `07 00 f9`, …).

**Frida:** `CreateFile`/`fopen` hooks log **0** font paths — fonts loaded via same C++ path layer as save, not Win32 A/W APIs.

---

## 5. Wrong repomix RVAs (do not hook)

| Claim | Result |
|-------|--------|
| `RenderFrame` @ `0x11E0F0` | **0 direct calls**; tail thunk only |
| Real frame path | Inside **`0xBE0F0`**, swap **`0xBEAF0`** |

---

## Capstone / Frida checklist

- [x] `0xBE0F0` loop back `0xBECE7`, exit `0xBEAE7`, quit save `0xBED11`  
- [x] `0x6DAB0` callers + startup/auto-save backtraces (Frida)  
- [x] Save path `save\` + format `save%d.dat` @ `0x263830`  
- [x] Font path builder cluster `0xBF2xx` → `0x6F3C0`  
- [ ] `0x711B0` settings loader (Capstone only — extend `disasm_phase1_extended.txt`)  
- [ ] `.crf` opcode VM semantics (need deeper trace or emulator on section1 bytes)
