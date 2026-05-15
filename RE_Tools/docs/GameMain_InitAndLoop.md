# `GameMain_InitAndLoop` @ `0xBE0F0`

**Ghidra:** `FUN_1400be0f0` · **Caller:** `0x21EE0D` (CRT)  
**Raw listing:** [ghidra_exports/GameMain_InitAndLoop.c.txt](ghidra_exports/GameMain_InitAndLoop.c.txt)

---

## Regions (Ghidra-confirmed)

| Region | RVA range | Role |
|--------|-----------|------|
| Prologue | `0xBE0F0`–`0xBE148` | Steam restart check, `SDL_Init(0x4020)` |
| Init body | `0xBE149`–`0xBEA6F` | Paths, settings, window, GL, **world bootstrap** |
| Frame loop | `0xBEA70`–`0xBED0B` | Poll → dispatch → update → swap → tick |
| Shutdown | `0xBED0C`–`0xBED81` | Teardown + **save** + SDL/Steam quit |

---

## Init pseudocode (`0xBE149`–`0xBEA6F`)

```c
int GameMain_InitAndLoop(void) {
    if (SteamAPI_RestartAppIfNecessary(0x36F88B)) return 0;     // 0xBE106
    if (SDL_Init(0x4020) != 0) return -1;                     // 0xBE128

    // Exe directory + game root paths (std::string + PathJoin @ 0x027F70)
    GetModuleFileNameExA(...);
    PathJoin(...);                                            // 0xBE1A5, 0xBE342
    FUN_140027830();                                          // 0xBE357
    Game_InitSubsystem_C0900(...);                            // 0xBE2DC, 0xBE40F, 0xBE505

    CreateDirectoryA(...);                                    // 0xBE55C
    SettingsLoader();                                         // 0xBE562 -> 0x711B0
    SDL_GetDesktopDisplayMode(0, &mode);                      // 0xBE56D

    // Pick client size from desktop (defaults 0xC80 x 0x708, clamp loop @ 0xBE5B1)
    // g_client_w @ 0x2F14D8, g_client_h related @ 0x2F14D4

    Game_SimStep(...);                                        // 0xBE607, 0xBE620, 0xBE69C, 0xBE6B9

    SDL_CreateWindow(title, flags, w, h);                     // 0xBE712
    SDL_GL_CreateContext(window);                             // 0xBE726
    SDL_ShowCursor(1);                                        // 0xBE735

    g_steam_callbacks_enabled = 0;                            // 0x318A54 @ 0xBE73C
    if (!SteamInternal_SteamAPI_Init()) {
        g_steam_callbacks_enabled = 1;                      // 0xBE75B
        // Steam context vtable calls @ 0xBE773, 0xBE789, 0xBE7B8
    }

    Game_BootstrapWorld();                                    // 0xBE7C1 -> 0x874B0 (see Game_BootstrapWorld.md)

    // Optional config table load @ 0xBE7E7..0xBEA3B (FUN_140225894, FUN_140231e14)
    if (g_vsync_flag) SDL_GL_SetSwapInterval(1);              // 0x2F14E1 @ 0xBEA53

    // Enter frame loop (ESI = SDL_GetTicks @ 0xBEA70)
    ...
}
```

---

## Quit / shutdown wiring (resolved)

```c
// Top of loop @ 0xBEA58 — links SDL dispatch to teardown
if (g_sdl_quit) {           // byte @ 0x318A50 (set by SDL_QUIT @ 0xC0442)
    goto shutdown;          // 0xBEA66 -> 0xBED0C
}

// Inside loop @ 0xBEACC / 0xBEAE1
if (g_loop_quit)            // byte @ 0x2F14EB
    ;                       // skips Game_UpdateWorld @ 0xBEAD4
else
    Game_UpdateWorld();     // 0xBEAD4 -> 0x87510

if (!g_render_ok)           // byte @ 0x2F14EA — je @ 0xBEAE7
    goto frame_tick;        // skip SDL_GL_SwapWindow

SDL_GL_SwapWindow(window);  // 0xBEAF0
// ... post-swap ...

frame_tick:
    SDL_GetTicks(); SDL_Delay(...);  // 0xBECE7

shutdown:                   // 0xBED0C
    Shutdown_Prep();        // 0x98680 — includes Save_Write (save%d.dat)
    Settings_Save(...);     // 0xBED11 -> 0x71F60 (settings.xml)
    if (g_steam_callbacks_enabled) SteamAPI_Shutdown();
    FUN_140087800();        // teardown helper
    SDL_GL_DeleteContext(); SDL_DestroyWindow(); SDL_Quit();
    return 0;
```

| Global | RVA | Set by | Effect |
|--------|-----|--------|--------|
| `g_sdl_quit` | `0x318A50` | `Game_DispatchSdlEvent` SDL_QUIT | **`jnz 0xBED0C`** @ `0xBEA66` — full shutdown |
| `g_loop_quit` | `0x2F14EB` | (other — TBD) | Skips `Game_UpdateWorld` when non-zero |
| `g_render_ok` | `0x2F14EA` | (TBD) | Zero → skip swap, go to frame tick |
| `g_steam_callbacks_enabled` | `0x318A54` | init @ `0xBE73C` | Gates `SteamAPI_RunCallbacks` @ `0xBEA7F` |

---

## Init call table (ordered)

| At | Callee | RVA / export |
|----|--------|----------------|
| `0xBE106` | `SteamAPI_RestartAppIfNecessary` | import |
| `0xBE128` | `SDL_Init` | `0x1248B0` |
| `0xBE186` | `K32GetModuleFileNameExA` | import |
| `0xBE1A5` | `PathJoin` | `0x027F70` |
| `0xBE2DC` | `Game_InitSubsystem_C0900` | `0x0C0900` |
| `0xBE55C` | `CreateDirectoryA` | import |
| `0xBE562` | **`SettingsLoader`** | `0x711B0` — see [SettingsLoader.md](SettingsLoader.md) |
| `0xBE56D` | `SDL_GetDesktopDisplayMode` | export |
| `0xBE607`+ | `Game_SimStep` | `0x0C12D0` |
| `0xBE712` | `SDL_CreateWindow` | export |
| `0xBE726` | `SDL_GL_CreateContext` | export |
| `0xBE7C1` | **`Game_BootstrapWorld`** | `0x874B0` |
| `0xBEA3B` | `FUN_140225a24` | config |
| `0xBEA53` | `SDL_GL_SetSwapInterval` | optional |

---

## Frame loop (same function)

See [GameLoop.md](GameLoop.md) — Ghidra confirms hook RVAs (`0xBEA8A`, `0xBEA9B`→`0xC0430`, `0xBEAF0`, `0xBECE7`).

---

## Rename suggestions for Ghidra

| Ghidra | Suggested |
|--------|-----------|
| `FUN_1400be0f0` | `GameMain_InitAndLoop` |
| `FUN_1400874b0` | `Game_BootstrapWorld` |
| `FUN_1400711b0` | `SettingsLoader` |
| `FUN_140071f60` | `Save_Write` |
| `FUN_140098680` | `Game_ShutdownPrep` |
| `FUN_140087800` | `Game_ShutdownCleanup` |
| `DAT_140318a50` | `g_sdl_quit` |
| `DAT_1402f14eb` | `g_loop_quit` |
| `DAT_1402f14ea` | `g_render_ok` |
