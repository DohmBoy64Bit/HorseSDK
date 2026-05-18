# Phase 4 — Mod loader (skeleton)

**Status:** skeleton (2026-05-17)  
**Depends on:** [Phase3_SDK.md](Phase3_SDK.md), `horse_sdk`, [game_function_hooks.json](../analysis/game_function_hooks.json)

---

## Components

| Artifact | Role |
|----------|------|
| `ModLoader/HorseModLoader.dll` | Injected into `Horsey.exe`; loads `mods/*.dll` |
| `ModLoader/horse_inject.exe` | `CreateRemoteThread` + `LoadLibraryA` injector |
| `mods/example_mod.dll` | Sample mod exporting `HorseMod_*` |
| `horse/mod_api.h` | Mod ↔ host ABI |

---

## Deploy layout

```
Game/
  Horsey.exe
  HorseModLoader.dll
  horse_inject.exe
  mods/
    example_mod.dll
```

---

## Mod exports

```c
const HorseModInfo *HorseMod_GetInfo(void);
int HorseMod_Init(const HorseModHost *host);
void HorseMod_Shutdown(void);
```

`HorseModHost` provides `resolve`, `hook_install`, `hook_remove`, `log`.

---

## Build & inject

```bat
cmake -S ModLoader -B build/modloader
cmake --build build/modloader --config Release
copy build\modloader\Release\HorseModLoader.dll <game dir>
copy build\modloader\mods\Release\example_mod.dll <game dir>\mods\
build\modloader\Release\horse_inject.exe
```

Start `Horsey.exe` first. Check DebugView for `[HorseModLoader]` lines.

---

## Next (Phase 4 proper)

- [ ] Config file for mod load order / enable flags
- [ ] Debug console overlay (ImGui or in-game text)
- [ ] Install hooks from `g_horse_hook_catalog` with UI toggles
- [ ] Safer hook backend (MinHook) for functions > 5 bytes / rel32 out of range
