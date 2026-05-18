# HorseSDK (Phase 3)

C11 library for Horsey modding: **verified RVAs** (Phase 2 catalog), **save-file I/O** (`horse_save`), and **hook helpers**.

## Build

```bat
python RE_Tools\tools\scripts\build_game_function_catalog.py
cmake -S SDK -B build/sdk -DCMAKE_BUILD_TYPE=Release
cmake --build build/sdk --config Release
```

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
| `horse_data.h` | `genes.dat` + `horsey.tmx` parsers |

**Do not** hardcode RVAs in mods — regenerate the catalog and rebuild.

## Docs

- [Phase3_SDK.md](../RE_Tools/docs/Phase3_SDK.md) — roadmap and ABI policy
- [GameFunctionCatalog.md](../RE_Tools/docs/GameFunctionCatalog.md) — Phase 2 source of truth

## Deferred (pinned)

Race follow-ups (seed→PRNG, vtable map, Frida score correlation): [RaceMechanics.md](../RE_Tools/docs/RaceMechanics.md) § Open RE.
