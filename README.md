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
- [`RE_Tools/docs/SaveSemanticsCoverage.md`](RE_Tools/docs/SaveSemanticsCoverage.md) — save v12 section status (9/9 on-disk sections mapped)
- [`RE_Tools/docs/SOURCES.md`](RE_Tools/docs/SOURCES.md) — verification policy (exe + dump over repomix)

Save format deep dives: `SaveFormat.md`, `SaveNestedFormat.md`, `SaveFooterFormat.md`, `SaveFutureWork.md` under `RE_Tools/docs/`.

## Roadmap

High-level plan from [`SystemPrompt.md`](SystemPrompt.md). Near-term items track [`RE_Tools/docs/ReverseEngineeringProgress.md`](RE_Tools/docs/ReverseEngineeringProgress.md) and [`RE_Tools/docs/SaveFutureWork.md`](RE_Tools/docs/SaveFutureWork.md).

### Phase overview

| Phase | Goal | Status |
|-------|------|--------|
| **1** | Knowledge confirmation & RE expansion (formats, RVAs, codecs) | **In progress** — save v12 on-disk layout complete; exe/data RE ongoing |
| **2** | Modular **C++ SDK** (redistributable read/write APIs) | Planned |
| **3** | **Mod loader** + optional in-game debug console | Planned |
| **4** | **UI toolkit** — save editor, map editor, horse editor | Planned |
| **5** | **Scripting** layer (e.g. Lua) on top of the SDK | Future |

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
- [ ] **Docs/JSON:** `phase1_verify.py` + scripts refresh `analysis/*.json` on each confirmed RVA

### Phase 1 — save RE (deferred, not blocking loaders)

Pinned in [`SaveFutureWork.md`](RE_Tools/docs/SaveFutureWork.md) — revisit when runtime/editor behavior is needed:

| Item | Why deferred |
|------|----------------|
| `0xAE470` runtime genetics | Applies alleles **after load**; not serialized in `save1.dat` |
| Footer `vtable+0xB0` / `+0xB8` | Separate from on-disk gene packs; wire when write path needs it |
| Full 343× main-nested b8 payloads | Sampled types 0/1/2/tail; per-slot semantics still open |
| Ctx row field names (`SaveSlot6` / `SaveRow13`) | Offsets known in `SaveContext.h`; labels TBD |

### Phase 2 — SDK (planned)

- [ ] Top-level **`SDK/`** (or equivalent) for redistributable C/C++ libraries — promote `horse_save` from `RE_Tools/src/`
- [ ] Stable public headers, CMake package config, versioned ABI policy
- [ ] Memory-safe wrappers for game pointers (read-only first, then controlled write)
- [ ] Data file APIs: TMX, genes, atlases — built on verified parsers in `RE_Tools/tools/parsers/`

### Phase 3 — mod loader (planned)

- [ ] DLL injector: drop mods in `mods/`, load at game start
- [ ] Hook bootstrap using confirmed RVAs (init `0xBE0F0`, frame loop `0xBEAF0`, save `0x6DAB0`)
- [ ] Optional **debug console** (improve on in-game debug concept; toggleable, logs hooks/state)

### Phase 4 — editors (planned)

- [ ] **Save editor** — UI over SDK + `horse_save` (settings + track gene packs, grid, inventory)
- [ ] **Map editor** — TMX / tile GID tooling from `horsey.tmx` RE
- [ ] **Horse editor** — genetics UI once `0xAE470` / phenotype rules are understood

### Phase 5 — scripting (future)

- [ ] Lua (or similar) bindings designed into Phase 2 APIs
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
