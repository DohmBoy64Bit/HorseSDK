# HorseSDK (Phase 3)

C11 library for Horsey modding: **verified RVAs** (Phase 2 catalog), **save-file I/O** (`horse_save`), and **hook helpers**.

## Build

```bat
python RE_Tools\tools\scripts\build_game_function_catalog.py
cmake -S SDK -B build/sdk -DCMAKE_BUILD_TYPE=Release -DHORSE_SDK_BUILD_DATA=ON
cmake --build build/sdk --config Release
```

`horse_map.c` is compiled into `horse_sdk` only when **`HORSE_SDK_BUILD_DATA=ON`** (default ON).

Artifacts:

| Target | Role |
|--------|------|
| `horse_sdk` | `horse_module_*`, `horse_hook_*` |
| `horse_save` | Offline save parse/write (no game required) |
| `horse_resolve_example` | Print resolved RVAs when `Horsey.exe` is loaded |

## Use in a mod DLL

```c
#include <horse/sdk.h>

void *gain = horse_resolve(HORSE_RVA_GainMoney);
/* or */
void *gain2 = horse_module_rva(horse_module_base(0), HORSE_RVA_GainMoney);
```

Hooks (5-byte JMP, same module or in-process only):

```c
static void my_gain_hook(void *ctx, int amount, int show_ui) { /* ... */ }

HorseHookSlot slot;
horse_hook_slot_init(&slot, horse_module_base(0), HORSE_RVA_GainMoney, (void *)my_gain_hook);
if (horse_hook_install(&slot) == HORSE_HOOK_OK) {
    /* call original via typedef cast to slot.trampoline */
}
```

## Headers

| Header | Content |
|--------|---------|
| `horse/sdk.h` | Umbrella |
| `horse/game_functions.h` | Auto-generated `HORSE_RVA_*` |
| `horse/game_function_types.h` | `HORSE_FN_*` / `HORSE_PTR_*` typedefs |
| `horse/game_function_hooks.h` | `g_horse_hook_catalog[]` for mod loader |
| `horse/mod_api.h` | Mod DLL exports (Phase 4) |
| `horse_save.h` | Save format API |
| `horse_data.h` | Umbrella: genes, TMX, bmfont, texture atlas |
| `horse_data/png_rgba.h` | PNG → RGBA (atlas sprites; stb in `ThirdParty/stb`) |
| `horse/horse_map.h` | `g_save_context`, TMX load, world→tile, view XY (`horse_map.c` + `horse_data`) |

**Do not** hardcode RVAs in mods — regenerate the catalog and rebuild.

### Map helpers (`horse_map`)

```c
#include <horse/sdk.h>

void *ctx = horse_map_get_save_context(host->game_base);
HorseMapView v;
if (horse_map_read_view(host->game_base, ctx, &v)) {
    int tx, ty;
    HorseDataTmxMap map;
    if (horse_map_load_tmx("...\\data\\horsey.tmx", &map) == HORSE_DATA_OK) {
        horse_map_world_to_tile(&map, v.world_x, v.world_y, &tx, &ty);
        horse_data_tmx_free(&map);
    }
}
```

Offsets and probe notes: [MapViewPosition.md](../RE_Tools/docs/MapViewPosition.md). Reference UI: `minimap_mod`.

## Docs

- [Phase3_SDK.md](../RE_Tools/docs/Phase3_SDK.md) — roadmap and ABI policy
- [GameFunctionCatalog.md](../RE_Tools/docs/GameFunctionCatalog.md) — Phase 2 source of truth

## Deferred (pinned)

Race follow-ups (seed→PRNG, vtable map, Frida score correlation): [RaceMechanics.md](../RE_Tools/docs/RaceMechanics.md) § Open RE.
