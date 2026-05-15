# Horsey Game — Reverse Engineering Progress

Living document for **Phase 1** (HorseSDK). All RVAs below are verified against `Game/Horsey.exe` unless marked *repomix-only* (needs Ghidra/x64dbg confirmation).

**Reference (not truth):** `repomix-output-DohmBoy64Bit-Horsey-Game.xml` — see [SOURCES.md](SOURCES.md)  
**Automation:** `python RE_Tools/tools/scripts/phase1_verify.py`  
**Data inventory:** `python RE_Tools/tools/scripts/inventory_data.py` → [DataFileFormats.md](DataFileFormats.md)  
**Offline play:** `steam_bypass/README.md`

---

## Phase 1: Knowledge Confirmation & RE Expansion

### 1.1 Layout (confirmed)

| Path | Purpose |
|------|---------|
| `Game/Horsey.exe` | Target binary |
| `Game/data/` | TMX, XML atlases, genes, sound defs |
| `Game/save/` | `settings.xml`, save games |
| `steam_bypass/` | Minimal `steam_api64.dll` for no-Steam runs |

### 1.2 PE header (confirmed — `pe_recon.py`)

| Field | Value |
|-------|--------|
| Image base | `0x140000000` |
| Entry point RVA | `0x21EE80` |
| Machine | AMD64 |
| Packing | Low entropy sections (not packed) |

Entry sequence (*repomix §1.6*): `0x21EE80` → CRT init → `0x21ED0C` (CRT/main) → game init.

### 1.3 Steam (confirmed)

See `steam_bypass/README.md`. Summary:

- 10 imports from `steam_api64.dll` only
- Interfaces: `STEAMUSERSTATS_INTERFACE_VERSION013`, `STEAMAPPS_INTERFACE_VERSION008`, `SteamUtils010`
- App ID file: `3602570`
- Achievement strings: `"got cheevo: %s"` @ `0x25D928`, `"Cheevo %s not found!"` @ `0x25D910`

### 1.4 Engine (repomix + import check)

- **SDL2:** statically linked (no `SDL2.dll` import; 800+ `SDL_*` exports in PE)
- **OpenGL:** `OPENGL32.dll` import
- **Physics / XML:** Box2D, TinyXML (*string evidence in repomix — not re-verified here*)

### 1.5 Core function RVAs

| Name | RVA | Status |
|------|-----|--------|
| CRT / main trampoline | `0x21ED0C` | Repomix + entry flow |
| Main game init | `0xBE0F0` | **Confirmed:** caller `0x21EE0D`; Steam @ `0xBE106` |
| Settings loader | `0x711B0` | **Confirmed:** caller `0xBE562` (inside main init) |
| Save writer | `0x6DAB0` | **Confirmed:** callers `0x9828C`, `0x10A2C2`, `0x10A822` |
| ~~RenderFrame~~ `0x11E0F0` | **Debunked (Frida):** tail thunk (`call` + `jmp [rip+disp]`), **0 hits** in live loop |
| Per-frame loop (swap) | `0xBEAF0` / `0xBEAF5` | **Frida:** `SDL_GL_SwapWindow` returns to `0xBEAF5` every frame |
| Main game (init + loop) | `0xBE0F0` | Contains frame loop; called from `0x21EE0D`; stack return `0x21EE12` |

**Image base + RVA → VA:** `0x140000000 + RVA`

### 1.6 Data formats (**verified** on `Game/data/` — 49 files)

See [DataFileFormats.md](DataFileFormats.md) and [analysis/data_inventory.json](../analysis/data_inventory.json).

| Asset | Verified count |
|-------|----------------|
| `genes.xml` | 240 genes |
| `pop.xml` | 23 variants |
| `horsey.tmx` | 400×225, 90k tiles, 56 unique GIDs |
| `sound.xml` | 23 music + 476 sounds |
| `sprites.xml` | 294 sprites |
| `furniture.xml` | 137 sprites |
| `terrain.xml` | 42 sprites |
| `locs.xml` | 34 sprites |
| `names.txt` | 5000 lines |

**Data (verified 2026-05-15):** GID→sprite map, `genes.dat` name index, `.crf` 16-byte header + 2 sections, `n64.fnt` BMF v3, sound paths, exe string xrefs — see `docs/DataFileFormats.md`.

**UNVERIFIED (data):** `.crf` glyph opcodes; `n64` page filename remap; Ghidra font loaders.

### 1.7 Phase 1 checklist

- [x] Steam bypass documented (`steam_bypass/README.md`) and built
- [x] PE header / entry / image base confirmed
- [x] Steam imports and call sites confirmed
- [x] Game/data/save paths confirmed
- [x] Call graph edges: entry→init, init→settings, save callers (`phase1_verify.py`)
- [x] `genes.xml` / `pop.xml` parser smoke test (`tools/parsers/genes.py`)
- [ ] **Ghidra:** decompile `0xBE0F0` (main init) — see `docs/Ghidra_Phase1.md`
- [x] **Frida:** per-frame path = `SDL_GL_SwapWindow` ← `0xBEAF0`, not `0x11E0F0` (`frida_renderframe.py`)
- [x] **Frida:** frame timeline — Poll @ `0xBEA8A`/`0xBEAA5` then swap @ `0xBEAF0` (`frida_gameloop.py`, see `docs/Frida_GameLoop.md`)
- [ ] **Ghidra:** apply labels from `Frida_GameLoop.md` and decompile `0xBE0F0` subregions
- [ ] **Ghidra:** decompile `0x6DAB0` (save), confirm write order vs repomix §A.5
- [ ] **x64dbg:** break `Horsey.exe+11E0F0`, capture call stack
- [x] Data inventory + parsers on all `Game/data/` files (`inventory_data.py`)
- [x] GID → `terrain.xml` / `locs.xml` sprite name map (`map_tile_gids.py`)
- [x] `genes.dat` name-index layout (`genes_dat.py`)
- [x] `.crf` container layout (`crf_font.py`); opcode stream still open
- [x] `n64.fnt` BMF v3 (`bmf_binary.py`)
- [x] `sound.xml` → `Game/sound/` path check (`verify_sound_paths.py`)
- [x] Data filename strings in exe (`xref_data_strings.py`)
- [x] Capstone disasm snippets (`disasm_phase1.py`)
- [x] `.crf` opcode marker trace (`crf_opcode_trace.py`)
- [x] `save1.dat` header probe (`probe_save_format.py`)
- [x] Capstone `0xBE0F0` loop (`phase1_gamemain_loop.json`) + Frida quit path `BED11`
- [x] Frida save/load/auto-save (`frida_phase1.py` — `edx=1`, callers `10A2C2`/`10A822`, path `Game\save\`)
- [x] Save heap buffer dump @ `Save_Write` leave (`frida_dump_save_buffer.py` — matches `save1.dat` byte-for-byte)
- [x] Font path builder cluster `0xBF2xx` → `0x6F3C0` (`phase1_crf_loader.json`)
- [ ] `.crf` opcode VM semantics (section1 interpreter)

---

## [KNOWLEDGE UPDATE] 2026-05-15

- HorseSDK uses `Game/` as game root (not `Horsey Game/` path from original repomix).
- `phase1_verify.py` automates PE + string + steam checks; output in `RE_Tools/analysis/phase1_verify.txt`.
- Steam bypass README: `steam_bypass/README.md`.
- **Call edges (E8, verified):** `0x21EE0D`→`0xBE0F0`, `0xBE562`→`0x711B0`, three sites→`0x6DAB0`.
- **Data strings (RVA):** `settings.xml` `0x263860`, `horsey.tmx` `0x263850`.
- **genes.xml:** 240 genes; **pop.xml:** 23 variants (parser run 2026-05-15).
- **SDL:** static link, 845 exports, no `SDL2.dll` import.
- **Frida (2026-05-15):** `SDL_GL_SwapWindow` return RVA `0xBEAF5`; backtrace `[1]=0x21EE12` (outer `call 0xBE0F0` return). Repomix `0x11E0F0` never executed. Report: `RE_Tools/analysis/frida_renderframe.txt`.
- **Data (2026-05-15):** Full `Game/data/` inventory — 49 files, parsers run. Doc: `DataFileFormats.md`. Policy: repomix not authoritative (`SOURCES.md`).
- **Save buffer (Frida 2026-05-15):** At `Save_Write` (`0x6DAB0`) return, serialized file is in heap: base `0x310418`, cursor `0x310410`, size = cursor − base. Dump `RE_Tools/analysis/save_buffer_dump.bin` identical to `Game/save/save1.dat` (196328 B). Writers: `0x6FD40` / `0x6FE10` / `0x6FEF0` / `0x6FF10` per `disasm_phase1_extended.txt` @ `0x6DCBB`.
- **Save layout (2026-05-15):** `0xC3100` writes file header (u64@4, count@0x10, global name strings). `SaveContext.h` + `SaveFieldLayout.md`. Per-writer offsets: `frida_trace_save_writers.py --compact` → `save_writer_trace.json`. Horse u16 vector @ file `0xA3D` count=3 (trace).
- **Save layout aligned (2026-05-15):** `run_save_layout_pipeline.py` — dump==trace==204386 B. Sections: global registry `0x14`–`0x958` (71 names), ctx `0x959`–`0xA3C`, vector@`0xA3D`, grid@`0xA61`+. Artifacts: `save_full_layout.json`, `save_global_names.json`.
