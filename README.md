# HorseSDK

Reverse-engineering toolkit and early native libraries for **Horsey** (Windows x64). This repository documents verified behavior against `Game/Horsey.exe` and ships Python codecs, analysis artifacts, and a C save parser — not the game binary or assets.

## What’s in the repo

| Path | Purpose |
|------|---------|
| [`RE_Tools/`](RE_Tools/) | Phase 1 RE: scripts, generated `analysis/`, and [`docs/`](RE_Tools/docs/) |
| [`RE_Tools/src/horse_save/`](RE_Tools/src/horse_save/) | C library + CLI for save format **v12** (read path) |
| [`steam_bypass/`](steam_bypass/) | Minimal `steam_api64.dll` stub for local offline runs |
| [`SystemPrompt.md`](SystemPrompt.md) | Project phases, evidence rules, and agent workflow |
| `repomix-output-*.xml` | Merged reference dump — **not** ground truth; see [`RE_Tools/docs/SOURCES.md`](RE_Tools/docs/SOURCES.md) |

## What’s not in the repo

The [`Game/`](Game/) directory (executable, `data/`, `save/`) is **gitignored**. Clone this repo next to your own copy of the game, or create `Game/` locally:

```
HorseSDK/
  Game/           ← you provide Horsey.exe, data/, save/
  RE_Tools/
  steam_bypass/
```

You must own the game to use these tools meaningfully.

## Prerequisites

- **Windows x64** (target platform)
- **Python 3.10+** for RE scripts (`RE_Tools/tools/scripts/`, `RE_Tools/tools/parsers/`)
- **CMake + MSVC** (or compatible toolchain) to build `horse_save`
- **Python + pefile + Capstone + Frida** for static/dynamic RE (primary)
- **Ghidra / x64dbg** only when automation stalls (large switches, failed decompile, live register proof)

## Quick start

From the repo root (with `Game/Horsey.exe` present locally):

```bat
cd E:\games\HorseSDK

REM Verify paths and baseline checks
python RE_Tools\tools\scripts\phase1_verify.py
python RE_Tools\tools\scripts\phase1_ci.py          # full gate: PE + save codec + horse_save + static RE
python RE_Tools\tools\scripts\phase1_ci.py --skip-frida   # faster (no spawn hooks)
python RE_Tools\tools\scripts\inventory_data.py

REM Save format: round-trip check on the checked-in dump
python RE_Tools\tools\scripts\save_write_codec.py

REM Build and run the C save CLI (uses RE_Tools\analysis\save_buffer_dump.bin)
cmake -S RE_Tools\src\horse_save -B build\horse_save
cmake --build build/horse_save --config Release
build\horse_save\Release\horse_save_cli.exe RE_Tools\analysis\save_buffer_dump.bin
```

Offline play without Steam: see [`steam_bypass/README.md`](steam_bypass/README.md).

## Documentation

Start here:

- [`RE_Tools/README.md`](RE_Tools/README.md) — layout and common commands
- [`RE_Tools/docs/GameLoop.md`](RE_Tools/docs/GameLoop.md) — main loop @ `0xBE0F0` (Ghidra labels, hooks)
- [`RE_Tools/docs/Ghidra_User_Tasks.md`](RE_Tools/docs/Ghidra_User_Tasks.md) — optional manual RE (automation-first; paste only if stuck)
- [`RE_Tools/docs/ReverseEngineeringProgress.md`](RE_Tools/docs/ReverseEngineeringProgress.md) — living RE log (RVAs, checklist)
- [`RE_Tools/docs/GameFunctionCatalog.md`](RE_Tools/docs/GameFunctionCatalog.md) — Phase 2 exe function catalog (RVAs, hooks, SDK)
- [`RE_Tools/docs/ModCapabilities.md`](RE_Tools/docs/ModCapabilities.md) — what mods the SDK can build today
- [`RE_Tools/docs/ModLoaderSmokeTest.md`](RE_Tools/docs/ModLoaderSmokeTest.md) — mod loader validation checklist
- [`RE_Tools/docs/SaveSemanticsCoverage.md`](RE_Tools/docs/SaveSemanticsCoverage.md) — save v12 section status (9/9 on-disk sections mapped)
- [`RE_Tools/docs/SOURCES.md`](RE_Tools/docs/SOURCES.md) — verification policy (exe + dump over repomix)

Save format deep dives: `SaveFormat.md`, `SaveNestedFormat.md`, `SaveFooterFormat.md`, `SaveFutureWork.md` under `RE_Tools/docs/`.

## Roadmap

High-level plan from [`SystemPrompt.md`](SystemPrompt.md). Near-term items track [`RE_Tools/docs/ReverseEngineeringProgress.md`](RE_Tools/docs/ReverseEngineeringProgress.md) and [`RE_Tools/docs/SaveFutureWork.md`](RE_Tools/docs/SaveFutureWork.md).

### Phase overview

| Phase | Goal | Status |
|-------|------|--------|
| **1** | Knowledge confirmation & RE expansion (formats, RVAs, codecs) | **Mostly complete** — save v12 on-disk 9/9; loop/save RVAs documented |
| **2** | **Game function catalog** — disasm, decompile, name, offsets for SDK hooks | **Started** — see [GameFunctionCatalog.md](RE_Tools/docs/GameFunctionCatalog.md) |
| **3** | Modular **C SDK** (read/write APIs + generated `game_functions.h`) | **Mostly complete** — see [Phase3_SDK.md](RE_Tools/docs/Phase3_SDK.md) |
| **4** | **Mod loader** + debug console + hooks | **Skeleton complete** — see [Phase4_ModLoader.md](RE_Tools/docs/Phase4_ModLoader.md), [ModCapabilities.md](RE_Tools/docs/ModCapabilities.md) |
| **5** | **UI toolkit** — save editor, map editor, horse editor | Planned |
| **6** | **Scripting** layer (e.g. Lua) on top of the SDK | Future |

### Phase 1 — done (representative)

- [x] Repo layout, verification policy (`SOURCES.md`), `Game/data/` inventory (49 files)
- [x] PE / Steam / call-graph baseline (`phase1_verify.py`, `steam_bypass/`)
- [x] Frida: frame loop @ `0xBEAF0`, save path, heap buffer dump == `save1.dat`
- [x] **Save format v12 (on disk):** 9/9 sections mapped, Python round-trip byte-identical (`save_write_codec.py`)
- [x] **C loader `horse_save`:** read path + CLI on `save_buffer_dump.bin`
- [x] Grid 400×225 (90k cells), inventory 410 blocks, footer gene packs (`0xF0`), nested b8 wire (sampled)

### Phase 1 — next (automation-first)

- [x] **Game loop + save writer:** Capstone/Frida + archived Ghidra where helpful — see `GameLoop.md`, `Save_Write.md`
- [x] **World sim:** [Game_WorldSimStep.md](RE_Tools/docs/Game_WorldSimStep.md) — resize-gated; Frida 0 hits with stable window
- [x] **Bootstrap tail:** [GameState_InitMain.md](RE_Tools/docs/GameState_InitMain.md), [Game_LoadAssets.md](RE_Tools/docs/Game_LoadAssets.md)
- [x] **Quit vs save:** [QuitSaveTrace.md](RE_Tools/docs/QuitSaveTrace.md) — `0x98680` + `Save_Write`, then `0x71F60` settings
- [x] **Settings persist:** [Settings_Save.md](RE_Tools/docs/Settings_Save.md) — Capstone `0x71F60` XML keys
- [x] **`.crf` font:** [CrfOpcodeSemantics.md](RE_Tools/docs/CrfOpcodeSemantics.md) — extended `crf_opcode_trace.py`
- [x] **horse_save:** C write API `horse_save_write_path` + `--roundtrip` / `HORSE_SAVE_ROUNDTRIP=1`
- [x] **Phase 1 CI:** `phase1_ci.py` — PE verify, `save_write_codec.py`, `horse_save` round-trip + structured write

### Phase 1 — save semantics (documented)

Hub: [`SaveSemantics.md`](RE_Tools/docs/SaveSemantics.md) · pipeline: `python RE_Tools/tools/scripts/run_save_semantics.py`

| Done | Artifact |
|------|----------|
| 343× b8 manifest + vcall+0x48 wire | `save_main_nested_b8_manifest.json`, `save_main_nested_vcall48.json` |
| Type-1 tile index | `save_type1_xref.json` |
| Footer B0/B8 (7 B) | `save_footer_extra_wire.json`, `horse_save` `HorseSaveFooterExtra` |
| Ctx write/load | `save_ctx_semantics.json`, `save_ctx_load_semantics.json` |
| Inventory alignment | `save_inventory_aligned.json` (ptr>8 = misread header) |
| Cross-save diff | `save_compare.json` (`save1.dat` vs `.prev`) |

Still deferred (runtime / labels): [`SaveFutureWork.md`](RE_Tools/docs/SaveFutureWork.md) — `0xAE470` phenotype apply, optional `--frida-genetics`, human-readable ctx row names.

### Phase 2 — game function catalog (exe RE for SDK)

**Hub:** [`GameFunctionCatalog.md`](RE_Tools/docs/GameFunctionCatalog.md)

Disassemble, decompile (Ghidra paste), and register **every Horsey.exe game routine** with RVA, VA, parameters, globals, and struct offsets so mods/SDK never hardcode addresses.

| Step | Command / artifact |
|------|-------------------|
| Build JSON + `GameFunctions.h` | `python RE_Tools/tools/scripts/build_game_function_catalog.py` |
| Capstone head disasm | `python RE_Tools/tools/scripts/disasm_catalog_function.py --all-known` |
| Decompile paste | `RE_Tools/docs/ghidra_exports/<Name>.c.txt` |
| Master list | `RE_Tools/analysis/game_function_catalog.json` |

- [x] Schema, workflow doc, seed catalog (~40+ verified RVAs: loop, save I/O, nested, settings, font)
- [x] Auto-generated [`GameFunctions.h`](RE_Tools/docs/GameFunctions.h) (`HORSE_RVA_*`)
- [x] **Gameplay strings:** race/shop/spawn (`find_gameplay_functions.py`) → [GameplayFunctions.md](RE_Tools/docs/GameplayFunctions.md)
- [ ] **Coverage:** grow catalog until all `FUN_140*` in hot paths are named (loop body, render, physics, UI)
- [x] Per-function struct offsets in catalog (seed: economy `ctx+0x308`, race score `race_ctx+0x450`)
- [x] CI: catalog build + RVA spot-check (`verify_catalog_rvas.py` in `sdk_ci.py`)

### Phase 3 — SDK

**Hub:** [`Phase3_SDK.md`](RE_Tools/docs/Phase3_SDK.md) · build from [`SDK/README.md`](SDK/README.md)

- [x] Top-level **`SDK/`** — `horse_sdk` + `horse_save` + `horse_data` + generated headers
- [x] `game_function_types.h`, `game_function_hooks.h` from catalog
- [x] `sdk_ci.py` (+ `phase1_ci.py --skip-sdk` to opt out)
- [x] bmfont / atlas in `horse_data` (genes + TMX + bmfont + TextureAtlas XML)

### Phase 4 — mod loader

**Hub:** [`Phase4_ModLoader.md`](RE_Tools/docs/Phase4_ModLoader.md)

- [x] `HorseModLoader.dll` + `horse_inject.exe` + `mods/example_mod`
- [x] Debug console + topmost log overlay + `HorseModLoader.ini`
- [x] MinHook backend (`ThirdParty/minhook`)
- [x] `example_mod` hooks `GainMoney` / `SpendMoney`; console `hook on` / `resolve`
- [ ] In-game ImGui overlay (fullscreen)
- [x] INI `mods_order` / `mod_*` enable + `auto_hooks` for catalog detours
- [x] Built-in detours: Save_Write, Save_Load (+ money); smoke doc [ModLoaderSmokeTest.md](RE_Tools/docs/ModLoaderSmokeTest.md)

### Phase 5 — editors (planned)

- [x] **Save editor skeleton** — `save_editor.py` (`info`, `backup`, `roundtrip`)
- [ ] **Save editor** — full UI over SDK + `horse_save`
- [ ] **Map editor** — TMX / tile GID tooling from `horsey.tmx` RE
- [ ] **Horse editor** — genetics UI once `0xAE470` / phenotype rules are understood

### Phase 6 — scripting (future)

- [ ] Lua (or similar) bindings designed into Phase 3 APIs
- [ ] Event hooks (frame, save/load, input) without recompiling core SDK

### How to pick up work

1. Choose a roadmap line item (or open checkbox in `ReverseEngineeringProgress.md`).
2. Confirm on `Game/Horsey.exe` or a captured dump — no repomix-only assumptions.
3. Land script + `RE_Tools/analysis/*.json` + doc update in the same change.

Details and agent rules: [`SystemPrompt.md`](SystemPrompt.md).

## Contributing

All offsets, layouts, and semantics must be backed by evidence on `Game/Horsey.exe` or captured dumps — no guessed structures. Regenerate analysis JSON via the scripts in `RE_Tools/tools/scripts/` and update the matching doc when behavior is confirmed.

## License

Game assets and `Horsey.exe` are not distributed from this repository. Tooling here is provided for research and modding by owners of the game; add a project license file if you intend to redistribute derived libraries.
