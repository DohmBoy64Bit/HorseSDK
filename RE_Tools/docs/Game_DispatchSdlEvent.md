# `Game_DispatchSdlEvent` @ `0xC0430`

**Ghidra:** `FUN_1400c0430` · **Caller:** `GameMain` @ `0xBEA9B`  
**Convention:** `rcx` = game context, `rdx` = `SDL_Event*` (copied to `rbx` in prologue)

**Source:** user Ghidra listing → [`ghidra_exports/Game_DispatchSdlEvent.c.txt`](ghidra_exports/Game_DispatchSdlEvent.c.txt)

---

## Summary pseudocode

```c
void Game_DispatchSdlEvent(GameContext *ctx, SDL_Event *ev) {
    uint32_t type = ev->type;
    switch (type) {

    case 0x100:  // SDL_QUIT
        g_sdl_quit = 1;              // byte @ 0x318A50
        return;

    case 0x303:  // SDL_TEXTINPUT
        PathJoin(ctx, ev->text.text); // strlen + tail-call FUN_140027f70 @ 0xC0472
        return;

    case 0x300:  // SDL_KEYDOWN (cmp edx, 0x300 branch)
        if (ev->key.repeat) return;
        handle_key_down(ev);         // keysym [+0x14], scancode [+0x10], mod [+0x18]
        // tables @ 0x312830, 0x312930, 0x3128b0, 0x3129b0, 0x312bb0, 0x312ab0
        // F4+mod -> also g_sdl_quit @ 0x318A50; Enter(0xD)+mod -> g_key_enter @ 0x318A52
        return;

    case 0x301:  // SDL_KEYUP
        handle_key_up(ev);
        return;

    case 0x400:  // SDL_WINDOWEVENT
        if (g_window_mode != -1) return;  // dword @ 0x2F25B8 must be -1
        g_last_win_event = ev->window;    // @ 0x312CE0..0x312CEC
        return;

    case 0x401:  // SDL_SYSWMEVENT — uses ev[+0x10] as window sub-type
        if (g_window_mode != -1) return;
        switch (ev->padding_10) {
        case 1: g_focused = 1; break;     // 0x312CB8, 0x312CC0
        case 3: g_unfocused = 1; break;   // 0x312CBC, 0x312CC4
        }
        return;

    case 0x402:  // SDL_WINDOWEVENT_LEAVE (SDL2)
        // sub-type [+0x10]: 1 = leave, 3 = ...
        return;

    case 0x403:  // SDL_WINDOWEVENT_ENTER
        // data1 [+0x14]: sets 0x312BFB or 0x312BFE
        return;

    case 0x200:  // SDL_DISPLAYEVENT (not APP_TERMINATING — uses [+0xc] display id)
        switch (ev->display.event) {
        case 0x0C: g_display_state = 1; break;  // 0x318A51
        case 0x0D: g_display_state = 0; break;
        case 0x05:  // orientation / resize
            SDL_GL_GetDrawableSize();
            Game_FrameFinalize();       // 0xC3A70
            if (!g_size_init_done)      // byte @ 0x2F14CC
                cache w/h @ 0x2F14D8, 0x2F14DC;
            break;
        case 0x04:
            SDL_GetWindowPosition();    // if !g_size_init_done
            break;
        }
        return;

    case 0x651:  // game-specific SDL user event
        if (ev->user.code < 0x10)
            g_user_event_code = ev->user.code;  // dword @ 0x318AB4
        return;

    default:
        return;
    }
}
```

---

## Globals (Ghidra names → RVA)

| Ghidra DAT | RVA | Role |
|------------|-----|------|
| `DAT_140318a50` | `0x318A50` | **`g_sdl_quit`** — SDL_QUIT + some key chords |
| `DAT_140318a51` | `0x318A51` | Display event state (`0x200` sub `0x0C`/`0x0D`) |
| `DAT_140318a52` | `0x318A52` | Enter-key chord flag |
| `DAT_140318ab4` | `0x318AB4` | Last user event code (`type == 0x651`) |
| `DAT_1402f14cc` | `0x2F14CC` | Window size cache init gate |
| `DAT_1402f14d8` | `0x2F14D8` | Cached drawable width |
| `DAT_1402f14dc` | `0x2F14DC` | Cached drawable height |
| `DAT_1402f25b8` | `0x2F25B8` | Window mode; must be **-1** to process `0x400`/`0x401` |
| `DAT_1402f14eb` | `0x2F14EB` | **Main loop quit** (`cmp` @ `0xBEAE1`) — link TBD |
| `DAT_140312ce0`…`cec` | `0x312CE0` | Last `SDL_WINDOWEVENT` fields |

Keyboard bitmap bases (indexed by scancode/keysym): `0x312830`, `0x312930`, `0x3128b0`, `0x3129b0`, `0x312bb0`, `0x312ab0`.

---

## SDL2 type reference (matched in binary)

| Value | Name | Handler RVA |
|-------|------|-------------|
| `0x100` | SDL_QUIT | `0xC043B` |
| `0x200` | SDL_DISPLAYEVENT | `0xC06C1` |
| `0x300` | SDL_KEYDOWN | `0xC0477` |
| `0x301` | SDL_KEYUP | `0xC052C` |
| `0x303` | SDL_TEXTINPUT | `0xC044F` |
| `0x400` | SDL_WINDOWEVENT | `0xC05A6` |
| `0x401` | SDL_SYSWMEVENT | `0xC05DE` |
| `0x402` | SDL_WINDOWEVENT_LEAVE | `0xC0648` |
| `0x403` | SDL_WINDOWEVENT_ENTER | `0xC0693` |
| `0x651` | (user) | `0xC0754` |

---

## Callees

| RVA | Name |
|-----|------|
| `0x027F70` | `PathJoin` (tail-call from TEXTINPUT) |
| `0x0C3A70` | `Game_FrameFinalize` |
| `0x123850` | `SDL_GL_GetDrawableSize` |
| `0x123660` | `SDL_GetWindowPosition` (tail jmp) |

---

## Quit flag link (Ghidra Task C)

`g_sdl_quit@0x318A50` does **not** copy to `0x2F14EB`. Instead `GameMain` @ **`0xBEA58`** tests `0x318A50` and **`jnz 0xBED0C`** (shutdown + `Save_Write@0xBED11`). See [GameMain_InitAndLoop.md](GameMain_InitAndLoop.md).

## Mod hook (`minimap_mod`)

`minimap_mod` detours this function for **SDL_KEYDOWN** (`type == 0x300`): scancode @ `ev+0x10`, sym @ `ev+0x14` — **M** toggles the map window. See [MinimapMod.md](MinimapMod.md).

## Still open
- [ ] Rename `FUN_140027f70`, `FUN_1400c3a70` in Ghidra if not done
- [ ] Confirm `0x200` branch: Ghidra types as APP_TERMINATING but code uses **display** sub-events `0x0C`/`0x0D`/`0x05`/`0x04`
