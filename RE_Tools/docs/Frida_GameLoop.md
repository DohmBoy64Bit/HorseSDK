# Frida: main game loop map (`0xBE0F0`)

**Full map (static + labels):** [GameLoop.md](GameLoop.md)

Script: `RE_Tools/tools/scripts/frida_gameloop.py`  
Output: `RE_Tools/analysis/frida_gameloop.json`  
Static map: `map_gamemain_loop.py` → `analysis/phase1_gamemain_loop_map.json`

## How to run

```bat
cd E:\games\HorseSDK
python RE_Tools\tools\scripts\frida_gameloop.py --frames 4
python RE_Tools\tools\scripts\frida_renderframe.py
```

## Confirmed architecture

```
CRT entry 0x21EE80
  └─ call 0x21EE0D → GameMain 0xBE0F0  (init + blocking loop; returns only on quit)
       └─ per-frame body ~0xBEA80–0xBECE7
            ├─ SteamAPI_RunCallbacks @ 0xBEA7F  (periodic; may be sparse)
            ├─ SDL_PollEvent via 0xBEA8A (once) then 0xBEAA5 (inner poll loop)
            ├─ … game update / render …
            └─ SDL_GL_SwapWindow call @ 0xBEAF0 → returns @ 0xBEAF5
```

**Not used in live loop:** repomix `RenderFrame` @ `0x11E0F0` (0 Frida hits).

## Hook sites (static PE + Frida)

| Label | RVA | Role |
|-------|-----|------|
| `main_game_entry` | `0xBE0F0` | Game init + main loop function |
| `steam_run_callbacks` | `0xBEA7F` | `SteamAPI_RunCallbacks` call site |
| `sdl_poll_call_a` | `0xBEA8A` | First `SDL_PollEvent` in frame |
| `sdl_poll_call_b` | `0xBEAA5` | Inner event-drain loop (many hits/frame) |
| `sdl_swap_call` | `0xBEAF0` | `E8` → `SDL_GL_SwapWindow` |
| `loop_internal_call` | `0xBEDB4` | Calls helper @ `0xBEEA0` |
| `loop_event_dispatch` | `0xBEA9B` | `call 0xC0430` — see GameLoop.md |
| `loop_quit_save` | `0xBED11` | `call Save_Write` on quit |
| `sdl_swap_alt` | `0xC019E` | Second swap call site (other code path) |
| `SDL_PollEvent` | `0x1253B0` | Export |
| `SDL_GL_SwapWindow` | `0x1238D0` | Export |

## Per-frame event order (Frida, typical)

**Frame 0 (startup, many polls):**

1. `sdl_poll_call_a` @ `0xBEA8A`
2. `sdl_poll_call_b` @ `0xBEAA5` × N (event queue drain)
3. `sdl_swap_call` @ `0xBEAF0`
4. `SDL_GL_SwapWindow` export

**Frame 1+ (steady state, shorter):**

1. `sdl_poll_call_a`
2. `sdl_poll_call_b` × 1–2
3. `sdl_swap_call` → `SDL_GL_SwapWindow`

## Stack (from `frida_renderframe.py`)

After `SDL_GL_SwapWindow`:

- `[0]` `Horsey.exe+0xBEAF5`
- `[1]` `Horsey.exe+0x21EE12` (return from `call 0xBE0F0`)

## Ghidra labels (suggested)

| RVA | Suggested name |
|-----|----------------|
| `0xBE0F0` | `GameMain_InitAndLoop` |
| `0xBEA7F` | `Loop_SteamRunCallbacks` |
| `0xBEA8A` | `Loop_PollEvent_First` |
| `0xBEAA5` | `Loop_PollEvent_Drain` |
| `0xBEAF0` | `Loop_GL_SwapWindow` |
| `0xBECE7` | `Loop_Tick` (helper call cluster) |
| `0xBEEA0` | `Loop_Helper` (callee of `0xBEDB4`) |
