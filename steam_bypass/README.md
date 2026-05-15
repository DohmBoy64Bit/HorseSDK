# Steam API Bypass (Minimal `steam_api64.dll`)

Replacement `steam_api64.dll` for **Horsey Game** so the executable runs without the Steam client. Intended for local modding / SDK development when you own the game.

## Quick start

```bat
cd steam_bypass
build.bat
```

This builds `build\steam_api64.dll` and copies it plus `steam_appid.txt` into `..\Game\` next to `Horsey.exe`.

Run the game from `Game\` (same folder as `Horsey.exe`, `data\`, `save\`).

## Requirements

- Windows x64
- [WinLibs](https://github.com/brechtsanders/winlibs_mingw) / MinGW `g++` on `PATH` (see `build.bat`)
- `Horsey.exe` in `Game\` (not shipped in this repo)

## App ID

| Source | Value |
|--------|--------|
| `steam_appid.txt` | `3602570` |
| `ColdClientLoader.ini` (repomix / prior RE) | `AppId=3602570` |
| `SteamAPI_RestartAppIfNecessary` immediate in exe | `ecx = 0x36F88B` (3602571) at RVA `0xBE106` |

The stub ignores the restart check (`returns false`). Use `3602570` in `steam_appid.txt` to match the shipped app id file.

## What Horsey.exe imports (verified)

PE import table on `Game\Horsey.exe` (via `pefile`, May 2026):

| Export | Role in stub |
|--------|----------------|
| `SteamAPI_RestartAppIfNecessary` | Returns `false` — do not relaunch via Steam |
| `SteamInternal_SteamAPI_Init` | Returns `true` — init succeeds offline |
| `SteamInternal_FindOrCreateUserInterface` | Returns stub interfaces (see below) |
| `SteamInternal_ContextInit` | Returns static context holder for utils vtable calls |
| `SteamAPI_GetHSteamUser` | Returns `1` |
| `SteamAPI_RegisterCallback` | No-op, returns `1` |
| `SteamAPI_UnregisterCallback` | No-op, returns `1` |
| `SteamAPI_RunCallbacks` | No-op |
| `SteamAPI_Shutdown` | No-op |
| `SteamAPI_ManualDispatch_Init` | No-op |

No other symbols are imported from `steam_api64.dll`.

## Steam interfaces the game requests

`SteamInternal_FindOrCreateUserInterface` call sites (Capstone / PE scan on `Game\Horsey.exe`):

| RVA | Interface version string |
|-----|-------------------------|
| `0x379D8` | `STEAMUSERSTATS_INTERFACE_VERSION013` |
| `0xC09B8` | `STEAMAPPS_INTERFACE_VERSION008` |
| `0xC09E2` | `SteamUtils010` |

### Achievements (UserStats)

Repomix / string dump (x64dbg `x64dbg_strings.csv`):

- `"Cheevo %s not found!"` — RVA `0x25D910`
- `"got cheevo: %s"` — RVA `0x25D928`

Stub vtable patches (Steamworks-style indices for v013):

| Index | Stub |
|-------|------|
| 0 | `RequestCurrentStats` → `true` |
| 7 | `SetAchievement` → `true` |
| 8 | `GetAchievement` → `true`, `*achieved = false` |
| 11 | `StoreStats` → `true` |

### Apps

| Index | Stub |
|-------|------|
| 0 | `BIsSubscribed` → `true` |
| 5 | `BIsSubscribedApp` → `true` |

### Utils

| Index | Notes |
|-------|--------|
| 5 | `BIsSteamRunning` (typical layout) → `true` |
| 10 | Called at vtable `+0x50` (RVA `0xBE773`) → no-op |
| 34 | Called at vtable `+0x110` (RVA `0xBE789`) → returns `true` |
| 3 | `GetAppID` fallback → `3602570` |

All other vtable slots use a safe `false` stub.

## Init flow in the executable

| RVA | Behavior |
|-----|----------|
| `0xBE0F0` | Main game init: `SteamAPI_RestartAppIfNecessary` |
| `0xBE74A` | `SteamInternal_SteamAPI_Init` with `RCX` → `"SteamUtils010"` |
| `0xBE762`+ | `SteamInternal_ContextInit` + vtable calls on utils |

With the stub, `SteamInternal_SteamAPI_Init` succeeds and the game does not take the early-exit restart path.

## Project layout

```
steam_bypass/
  README.md           ← this file
  build.bat
  exports.def         ← linker export list (must match game imports)
  steam_appid.txt
  src/
    steam_api64.cpp
  build/
    steam_api64.dll   ← output
```

Deploy next to `Horsey.exe`:

```
Game/
  Horsey.exe
  steam_api64.dll     ← stub from build.bat
  steam_appid.txt
  data/
  save/
```

## Alternative: Cold Client Loader

Prior RE (repomix) also documented:

- `ColdClientLoader.ini` — `exe=Horsey.exe`, `AppId=3602570`, `steamclient64.dll`
- Official `steam_api64.dll` in the install (1000+ exports) plus emulator `steamclient*.dll`

This project’s stub replaces only `steam_api64.dll` and is smaller and easier to audit for SDK work.

## Testing

After `build.bat`, a short launch test was done: `Horsey.exe` stayed running for several seconds without the Steam client.

If the game crashes on startup:

1. Confirm `steam_api64.dll` in `Game\` is the stub (small DLL, ~10 exports only — check with `dumpbin /exports` or the `pe_recon` script in `RE_Tools`).
2. Confirm `steam_appid.txt` contains `3602570`.
3. If a vtable call crashes, note the crash RVA in x64dbg and extend vtable stubs in `src/steam_api64.cpp`.

## References

- `repomix-output-DohmBoy64Bit-Horsey-Game.xml` — PE notes, RE progress, `ColdClientLoader.ini`, achievement strings
- `SystemPrompt.md` — project phases (Steam bypass is a prerequisite for offline Phase 1 RE)
- Source comments in `src/steam_api64.cpp` — RVAs and interface names

## Legal

Use only with a legitimate copy of Horsey Game. This does not distribute game binaries or Steamworks SDK files.
