# RE_Tools — Phase 1 & 2

Scripts and docs for reverse engineering **Horsey Game** (`Game/Horsey.exe`).

**Phase 2 — function catalog:** [docs/GameFunctionCatalog.md](docs/GameFunctionCatalog.md)

## Quick commands

```bat
cd E:\games\HorseSDK

python RE_Tools\tools\scripts\inventory_data.py
python RE_Tools\tools\scripts\phase1_verify.py
python RE_Tools\tools\scripts\pe_recon.py Game\Horsey.exe
python RE_Tools\tools\scripts\frida_renderframe.py
python RE_Tools\tools\scripts\frida_gameloop.py --frames 4
python RE_Tools\tools\scripts\analyze_gamemain_functions.py
python RE_Tools\tools\scripts\frida_trace_sdl_events.py --seconds 15
python RE_Tools\tools\parsers\genes.py

REM Phase 2: game function catalog (RVAs for SDK)
python RE_Tools\tools\scripts\build_game_function_catalog.py
python RE_Tools\tools\scripts\disasm_catalog_function.py --all-known

REM Minimap / save-context view RE (game running, farm view)
python RE_Tools\tools\scripts\frida_map_view_probe.py --attach --seconds 45
```

Outputs: `RE_Tools/analysis/phase1_verify.txt`, `map_view_probe.json`, etc.

## Docs

| File | Purpose |
|------|---------|
| `docs/SOURCES.md` | **Repomix is reference only — verification policy** |
| `docs/DataFileFormats.md` | **All `Game/data/` files (verified counts)** |
| `docs/Data/README.md` | Data docs index |
| `docs/ReverseEngineeringProgress.md` | Living RE log + checklist |
| `docs/GameLoop.md` | Main loop @ `0xBE0F0` — labels, hooks, pseudocode |
| `docs/GameFunctionCatalog.md` | Phase 2 — master function list for SDK hooks |
| `docs/GameFunctions.h` | Auto-generated `HORSE_RVA_*` macros |
| `docs/RacePredictorMod.md` | `race_predictor_mod` — pre-race lane ranking |
| `docs/RaceBettingOdds.md` | Betting payout UI vs `HorseRaceScore` / PRNG |
| `docs/MinimapMod.md` | `minimap_mod` — atlas map, controls, architecture |
| `docs/MapViewPosition.md` | `g_save_context` @ `0x31A660`, view XY candidates |
| `docs/ModCapabilities.md` | What mods can do today |
| `docs/Phase3_SDK.md` / `docs/Phase4_ModLoader.md` | SDK + mod loader |
| `docs/Ghidra_Phase1.md` | Ghidra/x64dbg tasks with RVAs |
| `../steam_bypass/README.md` | Offline Steam stub |

## Layout

```
RE_Tools/
  analysis/          # generated reports (map_view_probe.json, catalog, save, …)
  docs/
  src/
    horse_save/
    horse_data/      # TMX, genes, atlas, png_rgba
  tools/
    core/paths.py    # Game/, data/, save/ paths
    scripts/         # pe_recon, phase1_verify, frida_*, deploy_modloader
    parsers/         # XML/TMX parsers
```
