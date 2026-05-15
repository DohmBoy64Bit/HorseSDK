# Game loop — `GameMain_InitAndLoop` @ `0xBE0F0`

**Binary:** `Game/Horsey.exe` · **Image base:** `0x140000000`  
**Policy:** [SOURCES.md](SOURCES.md) — all RVAs verified on the exe (Capstone + Frida).

| Artifact | Script |
|----------|--------|
| [`GameMain_InitAndLoop.md`](GameMain_InitAndLoop.md) | Ghidra merge (Task C) |
| `analysis/phase1_gamemain_loop_map.json` | `map_gamemain_loop.py` |
| `analysis/disasm_gamemain_loop.txt` | same |
| `analysis/phase1_gamemain_init.json` | `analyze_gamemain_functions.py` |
| `analysis/phase1_sdl_event_dispatch.json` | same |
| `analysis/frida_gameloop.json` | `frida_gameloop.py` |
| `analysis/frida_sdl_events.json` | `frida_trace_sdl_events.py` |
| **Your Ghidra paste** | [Ghidra_User_Tasks.md](Ghidra_User_Tasks.md) → `ghidra_exports/` |

---

## Call graph (confirmed)

```
CRT @ 0x21EE80
  call 0x21EE0D
    GameMain_InitAndLoop @ 0xBE0F0   (blocks until quit; returns to 0x21EE12)
      init: Steam, SDL, SettingsLoader @ 0xBE562 -> 0x711B0
      loop @ 0xBEA7F..0xBED82:
        SteamAPI_RunCallbacks     @ 0xBEA7F
        SDL_PollEvent             @ 0xBEA8A / 0xBEAA5 (drain)
        Game_DispatchSdlEvent     @ 0xBEA9B -> 0xC0430
        [flags / pause gates]
        Game_UpdateWorld          @ 0xBEAD4 -> 0x87510
        if !quit: SDL_GL_SwapWindow @ 0xBEAF0 -> 0x1238D0
        [post-swap SDL + sim/render cluster 0xBEB00..0xBECC4]
        frame tick                @ 0xBECE7 -> 0x124330 (SDL_GetTicks)
      quit: Save_Write            @ 0xBED11 -> 0x6DAB0
```

**Debunked:** repomix `RenderFrame` @ `0x11E0F0` — tail thunk, **0** Frida hits. Do not hook.

---

## Regions inside `0xBE0F0`

| Region | RVA range | Role |
|--------|-----------|------|
| `init_prologue` | `0xBE0F0`–`0xBE148` | `SteamAPI_RestartAppIfNecessary` @ `0xBE106`; early `ret` on restart / `SDL_Init` fail |
| `init_body` | `0xBE149`–`0xBEA7E` | SDL/video setup, **`call 0x711B0`** @ `0xBE562` (settings + `horsey.tmx`), world bootstrap |
| `frame_loop` | `0xBEA7F`–`0xBED82` | Per-frame body until quit |

Function span (Capstone): **`0xBE0F0`–`0xBED82`** (~3.7 KB).

---

## Ghidra label sheet

Apply at **`Image base + RVA`**:

| RVA | Suggested name | Notes |
|-----|----------------|--------|
| `0xBE0F0` | `GameMain_InitAndLoop` | `rdi` = game context for loop |
| `0xBE106` | `Init_SteamRestartIfNecessary` | `ecx = 0x36F88B` |
| `0xBE11A` | `Init_EarlyReturn_SteamRestart` | |
| `0xBE148` | `Init_EarlyReturn_SDLInitFail` | |
| `0xBE562` | `Init_CallSettingsLoader` | `call 0x711B0` |
| `0xBEA7F` | `Loop_SteamRunCallbacks` | indirect Steam API |
| `0xBEA8A` | `Loop_PollEvent_First` | `SDL_PollEvent` |
| `0xBEA9B` | `Loop_EventDispatch` | `call 0xC0430` |
| `0xBEAA5` | `Loop_PollEvent_Drain` | inner `while (PollEvent)` |
| `0xBEAD4` | `Loop_UpdateWorld` | `call 0x87510` |
| `0xBEAD9` | `Loop_AutoSaveGate` | Frida: auto-save backtrace passes here |
| `0xBEAE1` | `Loop_CmpQuitFlag` | `g_quit` @ **`0x2F14EB`** |
| `0xBEAE7` | `Loop_QuitSkipRender` | `je 0xBECE7` — skip swap, go to tick |
| `0xBEAF0` | `Loop_GL_SwapWindow` | `SDL_GL_SwapWindow`; return @ `0xBEAF5` |
| `0xBEB00` | `Loop_PostSwapHook` | `call 0xBFFA0` |
| `0xBECE7` | `Loop_FrameTick` | `SDL_GetTicks` delta + optional delay |
| `0xBED11` | `Loop_QuitSave` | `call Save_Write` on shutdown |
| `0xBEDB4` | `Loop_CallHelper` | `call 0xBEEA0` |
| `0xC0430` | `Game_DispatchSdlEvent` | `rcx` = ctx, `rdx` = `SDL_Event*` |
| `0x87510` | `Game_UpdateWorld` | when not paused — [Game_UpdateWorld.md](Game_UpdateWorld.md) |
| `0x6DAB0` | `Save_Write` | see [Phase1_Exe_Notes.md](Phase1_Exe_Notes.md) |

---

## Frame pseudocode (static + Frida)

```c
// rdi = game context (window ptr passed to SDL_*)
while (!*(byte*)0x2F14EB) {   // cmp @ 0xBEAE1; je quit @ 0xBEAE7
    SteamAPI_RunCallbacks();    // 0xBEA7F

    SDL_Event ev;
    if (SDL_PollEvent(&ev)) {   // 0xBEA8A
        do {
            Game_DispatchSdlEvent(ctx, &ev);  // 0xBEA9B
        } while (SDL_PollEvent(&ev));       // 0xBEAA5
    }

    // 0xBEAAE..0xBEADF: byte flags (pause, mode) — see phase1_gamemain_loop_map.json
    if (should_tick_world)
        Game_UpdateWorld(ctx);  // 0xBEAD4

    if (quit) goto frame_tick;  // 0xBEAE7 -> 0xBECE7 (no swap)

    SDL_GL_SwapWindow(window);  // 0xBEAF0
    Game_PostSwapHook(ctx);     // 0xBEB00
    // 0xBEB05..0xBECC4: SDL window state, keyboard, 0x1243B0 render helper, 0xC12D0 sim steps

frame_tick:
    Loop_FrameTick();           // 0xBECE7 — timing / cap frame rate
}
Save_Write(ctx, mode);          // 0xBED11 (quit path)
```

---

## Per-frame order (Frida)

From `frida_gameloop.py` (`--frames 4`):

1. `Loop_PollEvent_First` @ `0xBEA8A`
2. `Loop_PollEvent_Drain` @ `0xBEAA5` × N (startup: many events; steady: 1–2)
3. `Loop_GL_SwapWindow` @ `0xBEAF0`
4. `SDL_GL_SwapWindow` export @ `0x1238D0`

Stack after swap (`frida_renderframe.py`): `[0]=0xBEAF5`, `[1]=0x21EE12`.

---

## Quit + save path

| Site | Evidence |
|------|----------|
| Quit flag | `cmp [0x2F14EB], bl` @ `0xBEAE1`; `je 0xBECE7` @ `0xBEAE7` skips render |
| Quit save | `call 0x6DAB0` @ **`0xBED11`** (Frida backtrace on shutdown) |
| Auto-save in loop | Caller chain includes **`0xBEAD9`** → `Save_Write` @ `0x10A2C2` |

---

## Mod hook candidates (Phase 3)

| Hook | RVA | When |
|------|-----|------|
| Pre-frame | `0xBEA7F` | Before Steam callbacks |
| Post-input | `0xBEAD4` | Before world update |
| Post-swap | `0xBEAF5` | After `SDL_GL_SwapWindow` returns |
| Frame tick | `0xBECE7` | Fixed timestep / FPS overlay |
| SDL events | `0xC0430` | Filter or log `SDL_Event` |

Prefer **Frida-validated** sites over repomix RVAs.

---

## Commands

```bat
cd E:\games\HorseSDK
python RE_Tools\tools\scripts\map_gamemain_loop.py
python RE_Tools\tools\scripts\frida_gameloop.py --frames 4
python RE_Tools\tools\scripts\frida_renderframe.py
```

---

## `Game_DispatchSdlEvent` @ `0xC0430` (Ghidra confirmed)

**Full write-up:** [Game_DispatchSdlEvent.md](Game_DispatchSdlEvent.md)  
**Raw Ghidra listing:** [ghidra_exports/Game_DispatchSdlEvent.c.txt](ghidra_exports/Game_DispatchSdlEvent.c.txt)

| `ev->type` | Action |
|------------|--------|
| `0x100` | `g_sdl_quit` @ **`0x318A50`** = 1 |
| `0x303` | `strlen` + tail-call **PathJoin** @ `0x027F70` on text @ `ev+0xC` |
| `0x300`/`0x301` | Key down/up → bitmaps @ `0x312830`… |
| `0x400`–`0x403` | Window events (if `dword@0x2F25B8 == -1`) |
| `0x200` | Display/window subcodes @ `ev+0xC` (resize → `SDL_GL_GetDrawableSize`, `0xC3A70`) |
| `0x651` | User event → `dword@0x318AB4` |

**Quit wiring (Ghidra):** `g_sdl_quit@0x318A50` → **`jnz 0xBED0C`** @ `0xBEA66` (full shutdown + save). Separate: `g_loop_quit@0x2F14EB` skips `Game_UpdateWorld`; `g_render_ok@0x2F14EA` skips swap. See [GameMain_InitAndLoop.md](GameMain_InitAndLoop.md).

---

## Init body (`0xBE149`–`0xBEA7E`) — static call chain

| Step | RVA | Callee |
|------|-----|--------|
| Settings + map | `0xBE562` | `SettingsLoader` @ `0x711B0` |
| Display mode | `0xBE56D` | `SDL_GetDesktopDisplayMode` |
| Window + GL | `0xBE712` / `0xBE726` | `SDL_CreateWindow` / `SDL_GL_CreateContext` |
| Bootstrap | `0xBE7C1` | **`0x874B0`** (name in Ghidra) |
| Sim warm-up | `0xBE607`+ | `Game_SimStep` @ `0xC12D0` |

Full list: `analysis/phase1_gamemain_init.json` · pseudocode: [GameLoop_Static.md](GameLoop_Static.md)

**Help us confirm:** [Ghidra_User_Tasks.md](Ghidra_User_Tasks.md) Task C.

---

## Still open (Phase 1)

- [ ] Ghidra decompile init + dispatch (paste into `docs/ghidra_exports/`)
- [ ] Name byte flags @ `0xBEAAE`–`0xBEADF` (pause, focus, `_saving_` interaction)
- [ ] Link `g_sdl_quit` @ `0x318A50` vs loop `g_quit` @ `0x2F14EB`
- [ ] Decompile **`0xBEEA0`** helper @ `0xBEDB4`
