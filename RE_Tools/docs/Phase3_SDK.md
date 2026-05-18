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
| `horse_hook_install` (minimal x64 JMP) | done (Windows) |
| CMake package config (`HorseSDKConfig.cmake`) | done |
| Typed typedefs per catalog function | done (`game_function_types.h`) |
| Hook catalog metadata | done (`game_function_hooks.h`, `game_function_hooks.json`) |
| Data parsers (TMX, genes) | done (`horse_data` lib) |
| CI: build SDK + smoke test | done (`sdk_ci.py`, wired in `phase1_ci.py`) |

---

## Layout

```
SDK/
  CMakeLists.txt
  include/horse/
    sdk.h
    version.h
    module.h
    hook.h
    game_functions.h    # generated — do not edit
  src/
    module.c
    hook.c
  examples/
    resolve_rvas.c
RE_Tools/src/horse_save/   # linked as subdirectory (promote later)
```

Regenerate RVAs:

```bat
python RE_Tools\tools\scripts\build_game_function_catalog.py
```

Writes both `RE_Tools/docs/GameFunctions.h` and `SDK/include/horse/game_functions.h`.

---

## ABI policy (v0.1)

- **RVAs** change when the game exe updates — bump SDK minor when regenerating catalog for a new `Horsey.exe` build.
- **Save format** version `HORSE_SAVE_FORMAT_VERSION` (12) is independent; document in [SaveFormat.md](SaveFormat.md).
- **Hooks:** 5-byte detour only at function entries; not safe for mid-instruction sites (see [GameplayFunctions.md](GameplayFunctions.md)).
- **C API** is C11 (`extern "C"` headers); C++ wrappers optional later.

---

## Phase 4 handoff

See [Phase4_ModLoader.md](Phase4_ModLoader.md) — skeleton injector + `HorseModLoader.dll` + `example_mod`.

---

## Next implementation tasks

1. Expand catalog `parameters` for more `HORSE_FN_*` typedefs (render, UI, physics).
2. `horse_data`: bmfont / texture atlas parsers (Python reference in `RE_Tools/tools/parsers/`).
3. C++ wrapper headers (optional) over C API.
