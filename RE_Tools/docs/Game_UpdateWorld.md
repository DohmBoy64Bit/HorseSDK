# `Game_UpdateWorld` @ `0x87510`

**Ghidra:** `FUN_140087510`  
**Callers:** `GameMain` frame loop @ **`0xBEAD4`**; `Game_PostSwapHook` @ **`0xC0196`** (`0xBFFA0`)  
**Raw listing:** [`ghidra_exports/Game_UpdateWorld.c.txt`](ghidra_exports/Game_UpdateWorld.c.txt)

Per-frame world update when the game is not quitting and `g_render_ok` allows the update path in `GameMain`.

---

## Signature (inferred)

```c
void Game_UpdateWorld(int year_or_frame_index /* RCX */);
```

`RCX` scales offsets: `LEA eax, [0x140 + rcx*2]` and `LEA eax, [0xb4 + rcx*2]` — likely **simulation year** or tick index into parallel tables.

---

## Flow

```c
void Game_UpdateWorld(int rcx) {
    Game_UpdatePrologue();              // 0x03F290
    if (!g_update_enabled)              // byte @ 0x312CF5
        return;                         // early out path not shown in snippet

    // Read last window rect (from SDL WINDOWEVENT @ 0xC05A6)
    float win_x = (float)dword@0x312CE0;
    float win_y = (float)dword@0x312CE4;
    float win_w = (float)dword@0x312CE8;
    float win_h = (float)dword@0x312CEC;

  const float REF_W = 960.0f;           // dword@0x2F1E20 = 0x3C0
  const float REF_H = 540.0f;           // dword@0x2F1E24 = 0x21C

    // Normalize window metrics → map-space floats (XMM0, XMM1)
    // Uses rcx in LEA: index = 0x140+2*rcx, 0xb4+2*rcx

    if (normalized_delta_x == 0 && normalized_delta_y == 0)
        goto light_tail;                // JZ @ 0x875F4 → 0x876E9

    Game_WorldSimStep();                // 0x088510
    // Broadcast XMM0/XMM1 into tables @ 0x312830..0x312920 (MOVUPS x many)
    FUN_140251850(); x3                  // 0x251850 — string/log helper?

    if (extra_ctx)
        FUN_140098040();                // 0x98040

    // More table updates + FUN_140251850 x2

light_tail:
    g_key_mod_shift = 0;                // 0x312CB0
    g_key_mod_ctrl = 0;                 // 0x312CB1
    g_key_mod_alt = 0;                  // 0x312CB3
    g_some_ptr = rbx;                   // 0x2F1E48
    *cursor_flag_ptr = bl;
    g_key_frame_counter++;              // INC dword@0x312CB4
}
```

---

## Globals

| RVA | Ghidra | Role |
|-----|--------|------|
| `0x312CF5` | `DAT_140312cf5` | Gate — must be non-zero to run body |
| `0x312CE0`–`CEC` | | Last window event rect (from `Game_DispatchSdlEvent` `0x400`) |
| `0x2F1E20` | | **`960`** (`0x3C0`) — reference width for DIVSS |
| `0x2F1E24` | | **`540`** (`0x21C`) — reference height for DIVSS |
| `0x312830`–`920` | | **Map/world float tables** (same family as SDL key tables) |
| `0x312CB0`/`CB1`/`CB3` | | Keyboard modifier flags cleared each tick |
| `0x312CB4` | | Counter incremented each call (reset in `Game_BootstrapWorld`) |
| `0x312CC0`/`CC8` | | Pointers cleared to `rbx` (0) |
| `0x2F1E48` | | Updated each frame |

**Note:** `960×540` is **2.4×** `400×225` (`horsey.tmx` grid size) — likely internal coordinate scale for window→tile mapping.

---

## Callees

| RVA | Suggested name |
|-----|----------------|
| `0x03F290` | `Game_UpdatePrologue` |
| `0x088510` | `Game_WorldSimStep` |
| `0x251850` | `Game_LogOrFormat` (6× in some paths) |
| `0x098040` | `Game_UpdateAux` (if `rcx` nonzero @ `0x876F0`) |

---

## Ghidra renames

| From | To |
|------|-----|
| `FUN_140087510` | `Game_UpdateWorld` |
| `FUN_140088510` | `Game_WorldSimStep` |
| `FUN_14003f290` | `Game_UpdatePrologue` |

---

## Still open

- [ ] Confirm meaning of **`RCX`** (year vs frame) — watch in x64dbg @ `0x87510` with `rcx` logged
- [x] Capstone **`0x088510`** — [Game_WorldSimStep.md](Game_WorldSimStep.md) (resize-gated; not per-frame)
- [ ] Tie **`0x312830`** table writes to TMX/grid (400×225) in docs
