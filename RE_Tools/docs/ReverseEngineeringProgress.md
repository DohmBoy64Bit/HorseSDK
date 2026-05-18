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
| `ClampInt3` | `0xC12D0` | **Not sim** — `int clamp(val,lo,hi)`; settings caps `0x64`/`0xC8` — [ClampInt3.md](ClampInt3.md) |
| `Font_LoadOrInit` | `0x7F8A0` | **Frida:** all 6 `.crf` @ init — [FontLoad.md](FontLoad.md) |
| `g_game_state` | `0x313720` | **Capstone:** 1 store @ `0x874F1`, 18 loads — [g_game_state.md](g_game_state.md) |
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

**UNVERIFIED (data):** nested `.crf` sub-opcodes (`0xFA`–`0xFF` in payloads); `n64` page filename remap.

### 1.7 Phase 1 checklist

- [x] Steam bypass documented (`steam_bypass/README.md`) and built
- [x] PE header / entry / image base confirmed
- [x] Steam imports and call sites confirmed
- [x] Game/data/save paths confirmed
- [x] Call graph edges: entry→init, init→settings, save callers (`phase1_verify.py`)
- [x] `genes.xml` / `pop.xml` parser smoke test (`tools/parsers/genes.py`)
- [x] **Game loop map:** `map_gamemain_loop.py` → `docs/GameLoop.md` + `phase1_gamemain_loop_map.json` (Frida + Capstone)
- [x] **SDL dispatch static:** `0xC0430` switch — `analyze_gamemain_functions.py` → `phase1_sdl_event_dispatch.json` (SDL_QUIT sets `0x318A50`)
- [x] **Init body static:** `0xBE149`–`0xBEA7E` call list → `phase1_gamemain_init.json`
- [x] **Ghidra (user):** Task B `0xC0430` → `ghidra_exports/Game_DispatchSdlEvent.c.txt`, `docs/Game_DispatchSdlEvent.md`
- [x] **Ghidra (user):** Task C `GameMain@0xBE0F0` → `GameMain_InitAndLoop.md`, `ghidra_exports/GameMain_InitAndLoop.c.txt`
- [x] **Frida:** per-frame path = `SDL_GL_SwapWindow` ← `0xBEAF0`, not `0x11E0F0` (`frida_renderframe.py`)
- [x] **Frida:** frame timeline — Poll @ `0xBEA8A`/`0xBEAA5` then swap @ `0xBEAF0` (`frida_gameloop.py`, see `docs/Frida_GameLoop.md`)
- [ ] **Ghidra:** apply labels from `GameLoop.md` / `Frida_GameLoop.md`
- [x] **Ghidra:** `SettingsLoader@0x711B0` — `SettingsLoader.md` (settings.xml keys, `g_loop_quit` cleared @ `0x71DF6`)
- [x] **Ghidra:** `Save_Write` @ `0x6DAB0` — [Save_Write.md](Save_Write.md) + [`ghidra_exports/Save_Write_decompiled.c.txt`](ghidra_exports/Save_Write_decompiled.c.txt)
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
- [x] `.crf` opcode markers + tag stats — [CrfOpcodeSemantics.md](CrfOpcodeSemantics.md)
- [x] Bootstrap tail Capstone — [GameState_InitMain.md](GameState_InitMain.md), [Game_LoadAssets.md](Game_LoadAssets.md)
- [x] Shutdown `jmp Save_Write` @ `0x9869A` — [Shutdown_Save_Callchain.md](Shutdown_Save_Callchain.md)
- [x] `horse_save` write API — `horse_save_write.c`, CLI round-trip
- [x] **`Game_SimStep` @ `0xC12D0`** — `disasm_game_sim_step.py`, `frida_game_sim_step.py`
- [x] **`g_game_state` @ `0x313720`** — `map_g_game_state_xrefs.py`
- [x] **Structured C save write** — `horse_save_write_structured()` + `--structured-roundtrip` (byte match on dump)
- [x] **CRF loader cluster** — `disasm_crf_vm.py`, `frida_font_trace.py` → [CrfLoaderVm.md](CrfLoaderVm.md)
- [x] **Phase 1 CI** — `phase1_ci.py` (PE verify + codec + horse_save + static scripts)

---

## [KNOWLEDGE UPDATE] 2026-05-15 (race mechanics — deep)

- **HorseRaceScore** entry **`0xE2B80`** (vtable `0x267368[0]`); export [HorseRaceScore.c.txt](ghidra_exports/HorseRaceScore.c.txt).
- **SimStartRace** handler **`RaceSimHandler` @ `0x5F020`**, post @ `0x5F365`; **`0x5F900`** is ctor only.
- **Seed:** `settings.xml` → **`g_settings_seed` @ `0x2F1587`** @ `0x71BCE`; PRNG **`g_prng_state` @ `0x2F2700`** via **`SimRandMod` @ `0xC1900`**.
- **Frida:** `RaceAdvanceSim` @ `0x8C9E0` logs `[race_ctx+0x450]` as `race_score_450` vs `finish_place` in `gameplay_frida.json`.
- **Doc:** [RaceMechanics.md](RaceMechanics.md) · [SimStartRace.md](SimStartRace.md).

## [KNOWLEDGE UPDATE] 2026-05-17 (Phase 4 mod platform)

- **MinHook** vendored @ `ThirdParty/minhook`; `horse_hook_install` uses MH_CreateHook.
- **Loader:** `HorseModLoader.ini`, debug console, topmost overlay, `hook on` / `resolve` commands.
- **example_mod v0.2:** hooks `GainMoney` + `SpendMoney` with console logging.
- **horse_data:** `bmfont_txt`, `texture_atlas` C parsers (mirrors Python).
- **Catalog:** `enrich_io_parameters` → 42 `HORSE_FN_*` typedefs.

## [KNOWLEDGE UPDATE] 2026-05-17 (Phase 3 complete + Phase 4 skeleton)

- **Typedefs:** `game_function_types.h` (`HORSE_FN_*`, `HORSE_PTR_*`) from catalog `parameters`.
- **Hooks JSON:** `game_function_hooks.json` + `game_function_hooks.h` (`g_horse_hook_catalog`).
- **horse_data:** C parsers for `genes.dat` + `horsey.tmx` (`RE_Tools/src/horse_data/`).
- **CI:** `sdk_ci.py` (catalog, SDK build, data smoke, modloader build).
- **Mod loader:** `ModLoader/HorseModLoader.dll`, `horse_inject.exe`, `mods/example_mod` — [Phase4_ModLoader.md](Phase4_ModLoader.md).

## [KNOWLEDGE UPDATE] 2026-05-17 (Phase 3 — SDK scaffold)

- **`SDK/`** CMake project: `horse_sdk` (`module.c`, `hook.c`), links **`horse_save`**, installs headers.
- **Generated:** `SDK/include/horse/game_functions.h` via `build_game_function_catalog.py` (dual-write with `GameFunctions.h`).
- **API:** `horse_module_base`, `horse_resolve`, `horse_hook_install` / `horse_hook_remove` (Windows x64 5-byte JMP).
- **Doc:** [Phase3_SDK.md](Phase3_SDK.md) · race RE **pinned** in [RaceMechanics.md](RaceMechanics.md).

## [KNOWLEDGE UPDATE] 2026-05-17 (Phase 2 — game function catalog)

- **New phase:** disasm + decompile + name all `Horsey.exe` game routines for SDK — [GameFunctionCatalog.md](GameFunctionCatalog.md).
- **Artifacts:** `game_function_catalog.json`, `GameFunctions.h`, `build_game_function_catalog.py`, `disasm_catalog_function.py`.
- **Seeded:** loop, save/load, nested I/O, settings, font, genetics, globals (`g_game_state`, quit flags).

## [KNOWLEDGE UPDATE] 2026-05-17 (save semantics)

- **343× b8:** 219 on-disk + **124 implicit** (EOF `ReadU32`→0 @ `0x6D6F5`, default `0xC8` component) — `save_main_nested_b8_manifest.json`.
- **vcall+0x48 wire:** per-slot handlers type0/1/2 — `save_main_nested_vcall48.json` (nested_main **complete**).
- **Type-1 b8:** 15-byte wire @ `0x102DC0`; tile index `0x1F00` → (19,336) on 400-wide grid — `save_type1_xref.json`.
- **Footer B0/B8:** `0x1017C0` / `0x101810` — 7 B @ footer rel 833 — `save_footer_extra_wire.json`.
- **Inventory:** ptr>8 = misaligned header; 372 compact + 1 opaque @ slot 361 — `save_inventory_aligned.json`.
- **Cross-save:** `save_compare.json` (dump vs `save1.dat.prev`).
- **Pipeline:** `run_save_semantics.py` · hub [SaveSemantics.md](SaveSemantics.md).

## [KNOWLEDGE UPDATE] 2026-05-15 (deeper RE — font / clamp / crf)

- **`0xC12D0` renamed `ClampInt3`:** `int clamp(ecx, edx, r8d)` — Frida `rcx=0x64` was **`r8d=100`** cap @ `SettingsLoader` `0x714D2`.
- **Font load:** `Font_LoadOrInit` @ **`0x7F8A0`**; `fopen` @ **`0x6FB90`** — Frida logs all 6 `.crf` (caller `0x97467`…`0x97839`, bootstrap `0xBE7C6`).
- **`.crf` opcodes:** record = `u16` + `F8`/`F9` + payload; **8-byte body → glyph @ `0x7FC90`** — [CrfGlyphParse.md](CrfGlyphParse.md); draw @ `0x80D10` — [FontDraw.md](FontDraw.md).

## [KNOWLEDGE UPDATE] 2026-05-15 (Phase 1 close — items 1–5)

- **`Game_SimStep` @ `0xC12D0`:** ~`0x154` B, 24 E8 callers; frame loop `0xBEC53`/`0xBEC79`; Frida init burst 388 hits then ~0/frame idle — [Game_SimStep.md](Game_SimStep.md).
- **`g_game_state` @ `0x313720`:** single store `0x874F1`, 18 RIP loads (save/update/UI) — [g_game_state.md](g_game_state.md).
- **`horse_save_write_structured`:** section-slice reassembly; `--structured-roundtrip` **match=yes** on `save_buffer_dump.bin` (204386 B).
- **CRF VM cluster:** `0xBF200` → `FileWrite_6F3C0` @ `0xBF2C6`; also save path `0x6DB95` — [CrfLoaderVm.md](CrfLoaderVm.md).
- **CI:** `python RE_Tools/tools/scripts/phase1_ci.py` (add `--skip-frida` for local quick runs).

## [KNOWLEDGE UPDATE] 2026-05-15 (game loop + SDL dispatch)

- **`Game_DispatchSdlEvent` @ `0xC0430` (Ghidra):** `ghidra_exports/Game_DispatchSdlEvent.c.txt`, `docs/Game_DispatchSdlEvent.md`.
- **`GameMain` @ `0xBE0F0`:** Quit: **`g_sdl_quit`** → **`0xBED0C`** → **`0x98680`** (prep, **includes `Save_Write`**) → **`0x71F60`** settings @ **`0xBED11`**. Frida: [QuitSaveTrace.md](QuitSaveTrace.md). Autosave: **`0x10A2C2`** / **`0x10A822`**.
- **`Settings_Save@0x71F60`:** [Settings_Save.md](Settings_Save.md) — Capstone XML keys written on quit.
- **`Game_WorldSimStep@0x88510`:** [Game_WorldSimStep.md](Game_WorldSimStep.md) — only when window delta ≠ 0; 0 Frida hits with stable window.
- **`Game_BootstrapWorld@0x874B0`:** `Game_BootstrapWorld.md` — chain `InitCore`→`InitRender`→`FrameFinalize`→`LoadAssets`→`GameState_Ctor(0x30)`→**`jmp 0x97110`**; **`g_game_state@0x313720`**.
- **`SettingsLoader@0x711B0`:** `SettingsLoader.md` — parses `settings.xml` keys (`fullscreen`, `winw`, `vsync`, `autosave`, …); **`g_loop_quit@0x2F14EB=0`** @ `0x71DF6`; parser **`0x72280`**.
- **`Game_UpdateWorld@0x87510`:** `Game_UpdateWorld.md` — window rect → normalized coords; ref **960×540**; tables `0x312830`; **`Game_WorldSimStep@0x88510`**.
- **Init body `0xBE149`–`0xBEA7E`:** `SettingsLoader` @ `0xBE562`, `SDL_CreateWindow` @ `0xBE712`, `SDL_GL_CreateContext` @ `0xBE726`, bootstrap **`0x874B0`** @ `0xBE7C1` — `phase1_gamemain_init.json`.
- **User Ghidra/x64dbg:** task list in `docs/Ghidra_User_Tasks.md`; paste decompiles to `docs/ghidra_exports/*.c.txt`.

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
