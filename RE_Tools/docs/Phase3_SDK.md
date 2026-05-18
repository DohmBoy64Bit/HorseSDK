# Phase 3 — Core C++ SDK

**Status:** v0.1 (2026-05-17)  
**Depends on:** [GameFunctionCatalog.md](GameFunctionCatalog.md) (Phase 2), `horse_save` (Phase 1)

Race mechanics RE is **pinned** — see [RaceMechanics.md](RaceMechanics.md) § Open RE (deferred).

---

## Goals

| Item | Status |
|------|--------|
| Top-level `SDK/` CMake project | done |
| Ship `horse_save` + generated `game_functions.h` | done |
| `horse_module_base` / `horse_resolve` | done |
| `horse_hook_install` (MinHook on Windows) | done |
| CMake package config (`HorseSDKConfig.cmake`) | done |
| Typed typedefs per catalog function | done (`game_function_types.h`) |
| Hook catalog metadata | done (`game_function_hooks.h`, `game_function_hooks.json`) |
| Data parsers (TMX, genes, atlas, PNG) | done (`horse_data` lib) |
| Map helpers (`horse_map_*`, `g_save_context`) | done (`horse_map.c` when `HORSE_SDK_BUILD_DATA=ON`) |
| CI: build SDK + smoke test | done (`sdk_ci.py`, wired in `phase1_ci.py`) |

---

## Layout

```
SDK/
  CMakeLists.txt
  include/horse/
    sdk.h                 # umbrella (module, hooks, game_functions, horse_map)
    version.h
    module.h
    hook.h
    horse_map.h           # TMX load, save ctx, view XY, world→tile
    game_functions.h      # generated — do not edit
    game_function_types.h
    game_function_hooks.h
    mod_api.h
  src/
    module.c
    hook.c
    hook_minhook.c        # when HORSE_USE_MINHOOK
    horse_map.c           # when HORSE_SDK_BUILD_DATA=ON
  examples/
    resolve_rvas.c

RE_Tools/src/
  horse_save/             # linked as subdirectory
  horse_data/
    include/horse_data/
      horse_data.h        # genes, tmx, bmfont, texture_atlas
      png_rgba.h          # stb_image PNG → RGBA (minimap atlases)
    png_rgba.c
    tmx_map.c
    texture_atlas.c
    ...
```

Regenerate RVAs:

```bat
python RE_Tools\tools\scripts\build_game_function_catalog.py
```

Writes both `RE_Tools/docs/GameFunctions.h` and `SDK/include/horse/game_functions.h`.

Map RE: [MapViewPosition.md](MapViewPosition.md) · reference mod UI: [MinimapMod.md](MinimapMod.md).

---

## ABI policy (v0.1)

- **RVAs** change when the game exe updates — bump SDK minor when regenerating catalog for a new `Horsey.exe` build.
- **Save format** version `HORSE_SAVE_FORMAT_VERSION` (12) is independent; document in [SaveFormat.md](SaveFormat.md).
- **Hooks:** 5-byte detour only at function entries; not safe for mid-instruction sites (see [GameplayFunctions.md](GameplayFunctions.md)).
- **C API** is C11 (`extern "C"` headers); C++ wrappers optional later.
- **`horse_map`:** requires `horse_data` + `HORSE_SDK_BUILD_DATA=ON` (default ON in `SDK/CMakeLists.txt`).

---

## Phase 4 handoff

See [Phase4_ModLoader.md](Phase4_ModLoader.md) — injector + `HorseModLoader.dll` + `example_mod` + `minimap_mod`.

---

## Next implementation tasks

1. C++ wrapper headers (optional) over C API.
2. More catalog `parameters` for I/O primitives (save stream writers).
3. Live minimap view XY once Frida scan closes ([MapViewPosition.md](MapViewPosition.md)).
