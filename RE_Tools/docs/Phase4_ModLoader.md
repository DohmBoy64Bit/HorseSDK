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

## Build & deploy

```bat
python RE_Tools\tools\scripts\deploy_modloader.py
```

Copies into `Game/` (next to `Horsey.exe`):

- `HorseModLoader.dll`
- `horse_inject.exe`
- `mods\example_mod.dll`

Also runs at end of `sdk_ci.py` (unless `--skip-deploy`).

## Inject

1. Start `Horsey.exe` (windowed is easier — fullscreen can hide the second console).
2. Run `horse_inject.exe` from the `Game\` folder.
3. **Alt-tab** to a new window titled **"Horsey Mod Loader"** — that console is attached to the game, not PowerShell.

Commands in the loader console: `help`, `mods`, `base`, `clear`.

### DebugView (optional)

[DebugView](https://learn.microsoft.com/en-us/sysinternals/downloads/debugview) is a separate free Sysinternals tool — it is **not** installed with HorseSDK. It shows `OutputDebugString` lines (`[HorseModLoader] ...`) if you prefer logging without a console window. Run DebugView as Administrator, enable **Capture Global Win32**.

---

## Config (`HorseModLoader.ini`)

| Key | Default | Meaning |
|-----|---------|---------|
| `console` | 1 | AllocConsole on game process |
| `overlay` | 0 | Topmost log window (set 1 for fullscreen-friendly duplicate log) |
| `load_example_mod` | 1 | Load `mods\example_mod.dll` |
| `auto_hook_gain` | 0 | Loader hooks GainMoney (use if example_mod off) |

Copy from `ModLoader/HorseModLoader.ini.example` — `deploy_modloader.py` installs it on first deploy.

## Hooks

- **example_mod** installs `GainMoney` + `SpendMoney` on load (MinHook).
- **SpendMoney** is **4 arguments** (`ctx`, `cost`, `show_ui`, `str_variant`) — disasm @ `0x10AC94`/`0x10ACAB`. A 2-arg detour will crash on shop buy.
- Console: `hooks`, `hook on GainMoney`, `hook off GainMoney`, `resolve Save_Write`.

## Next

- [ ] ImGui in-game overlay
- [ ] Mod load order / per-mod enable in INI
- [ ] More built-in log detours from `g_horse_hook_catalog`
