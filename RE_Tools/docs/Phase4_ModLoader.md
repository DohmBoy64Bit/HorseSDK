# Phase 4 — Mod loader (skeleton)

**Status:** skeleton + sample mods (2026-05-17)  
**Depends on:** [Phase3_SDK.md](Phase3_SDK.md), `horse_sdk`, [game_function_hooks.json](../analysis/game_function_hooks.json)

---

## Components

| Artifact | Role |
|----------|------|
| `ModLoader/HorseModLoader.dll` | Injected into `Horsey.exe`; loads `mods/*.dll` |
| `ModLoader/horse_inject.exe` | `CreateRemoteThread` + `LoadLibraryA` injector |
| `mods/example_mod.dll` | Sample mod exporting `HorseMod_*` |
| `mods/minimap_mod.dll` | Atlas map window — [MinimapMod.md](MinimapMod.md) |
| `horse/mod_api.h` | Mod ↔ host ABI |

---

## Deploy layout

```
Game/
  Horsey.exe
  HorseModLoader.dll
  horse_inject.exe
  HorseModLoader.ini
  mods/
    example_mod.dll
    minimap_mod.dll
```

---

## Mod exports

```c
const HorseModInfo *HorseMod_GetInfo(void);
int HorseMod_Init(const HorseModHost *host);
void HorseMod_Shutdown(void);
```

`HorseModHost` provides `resolve`, `hook_install`, `hook_remove`, `log`.

**minimap_mod** also exports `HorseMod_MapToggle()` (used by loader console **`map`**).

---

## Build & deploy

```bat
cmake -S ModLoader -B build/modloader -DCMAKE_BUILD_TYPE=Release
cmake --build build/modloader --config Release
python RE_Tools\tools\scripts\deploy_modloader.py
```

Copies into `Game/` (next to `Horsey.exe`):

- `HorseModLoader.dll`
- `horse_inject.exe`
- `mods\example_mod.dll`
- `mods\minimap_mod.dll`
- `HorseModLoader.ini` (from `.example` on first deploy)

Also runs at end of `sdk_ci.py` (unless `--skip-deploy`).

## Inject

1. Start `Horsey.exe` (windowed is easier — fullscreen can hide the second console).
2. Run `horse_inject.exe` from the `Game\` folder.
3. **Alt-tab** to **"Horsey Mod Loader"** — that console is attached to the game, not PowerShell.

Commands: `help`, `mods`, `base`, `clear`, **`map`** (toggle minimap if `minimap_mod.dll` loaded).

### DebugView (optional)

[DebugView](https://learn.microsoft.com/en-us/sysinternals/downloads/debugview) shows `OutputDebugString` (`[HorseModLoader] ...`) if you prefer logging without a console. Run as Administrator, enable **Capture Global Win32**.

---

## Config (`HorseModLoader.ini`)

| Key | Default | Meaning |
|-----|---------|---------|
| `console` | 1 | AllocConsole on game process |
| `overlay` | 0 | `0`=off, `1`=topmost popup, `2`=in-game child of Horsey window |
| `load_example_mod` | 1 | Load `mods\example_mod.dll` |
| `auto_hook_gain` | 0 | Legacy: enables GainMoney+SpendMoney loader hooks |
| `auto_hooks` | (empty) | Comma list, e.g. `Save_Write,Save_Load` |
| `mods_order` | (empty) | Load only these DLLs, in order (e.g. `example_mod.dll,minimap_mod.dll`) |
| `mod_<stem>` | (default on) | `mod_example_mod=0` disables that mod |

Copy from `ModLoader/HorseModLoader.ini.example` — `deploy_modloader.py` installs it on first deploy.

## Hooks

- **example_mod** installs `GainMoney` + `SpendMoney` on load (MinHook).
- **SpendMoney** is **4 arguments** (`ctx`, `cost`, `show_ui`, `str_variant`) — disasm @ `0x10AC94`/`0x10ACAB`. A 2-arg detour will crash on shop buy.
- **minimap_mod** hooks `Game_DispatchSdlEvent` (M key), `Game_UpdateWorld` (dot refresh), `Save_Write` (ctx cache).
- Console: `hooks`, `hook on GainMoney`, `hook off GainMoney`, `resolve Save_Write`, **`map`**.

## Next

- [ ] ImGui in-game overlay — hook site @ `Game_PostSwapHook`; use `setup_imgui.ps1` ([ImGuiOverlay.md](ImGuiOverlay.md))
- [x] In-game GDI log overlay (`overlay=2`)
- [x] Mod load order / per-mod enable in INI (`mods_order`, `mod_<stem>`)
- [x] Built-in log detours for full `g_horse_hook_catalog` (throttled where noisy)
- [x] **`minimap_mod`** — static TMX atlas map ([MinimapMod.md](MinimapMod.md))
- [ ] Live player dot on map (RE open — [MapViewPosition.md](MapViewPosition.md))

See [ModCapabilities.md](ModCapabilities.md) · [ModLoaderSmokeTest.md](ModLoaderSmokeTest.md).
