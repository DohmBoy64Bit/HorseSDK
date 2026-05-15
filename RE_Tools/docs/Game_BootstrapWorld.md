# `Game_BootstrapWorld` @ `0x874B0`

**Ghidra:** `FUN_1400874b0` · **Caller:** `GameMain_InitAndLoop` @ **`0xBE7C1`**  
**Evidence:** `Game/Horsey.exe` + user Ghidra listing → [`ghidra_exports/Game_BootstrapWorld.c.txt`](ghidra_exports/Game_BootstrapWorld.c.txt)

Runs **once** after SDL window/GL context exist and optional Steam init — before the main frame loop @ `0xBEA70`.

---

## Call chain (in order)

| Order | RVA | Suggested name | Role |
|-------|-----|----------------|------|
| 1 | `0xC1850` | `Game_InitCore` | Core subsystems |
| 2 | — | — | `dword@0x312CB4` ← 0 (keyboard state table reset) |
| 3 | `0xC3C10` | `Game_InitRender` | Render pipeline setup |
| 4 | `0xC3A70` | `Game_FrameFinalize` | One-time finalize (same as resize path in SDL dispatch) |
| 5 | `0x3EE50` | `Game_LoadAssets` | Load game assets from `data/` |
| 6 | `0x21E414` | `operator_new` | `ecx = 0x30` (48 bytes) |
| 7 | `0x96D20` | `GameState_Ctor` | Construct object on heap |
| 8 | — | — | `qword@0x313720` ← instance pointer (`g_game_state`) |
| 9 | `0x97110` | `GameState_InitMain` | **Tail call** — does not return to `GameMain` until later |

**Function shape:** `0x874B0`–`0x87500`, ends with **`jmp 0x97110`** (not `ret`).

---

## Pseudocode

```c
void Game_BootstrapWorld(void) {
    Game_InitCore();                    // 0xC1850
    g_key_state_base = 0;               // dword @ 0x312CB4 (SDL key tables)
    Game_InitRender();                  // 0xC3C10
    Game_FrameFinalize();               // 0xC3A70
    Game_LoadAssets();                  // 0x3EE50

    void* obj = operator_new(0x30);     // 0x21E414
    if (obj)
        g_game_state = GameState_Ctor(obj);  // 0x96D20 -> rbx
    else
        g_game_state = NULL;          // qword @ 0x313720

    GameState_InitMain(g_game_state);   // tail jmp 0x97110
}
```

---

## Globals touched

| RVA | Ghidra | Set value |
|-----|--------|-----------|
| `0x312CB4` | `DAT_140312cb4` | `0` |
| `0x313720` | `DAT_140313720` | `g_game_state` pointer (or NULL) |

Keyboard tables @ `0x312830` family are cleared indirectly via `0x312CB4` (see [Game_DispatchSdlEvent.md](Game_DispatchSdlEvent.md)).

---

## Ghidra renames

| From | To |
|------|-----|
| `FUN_1400874b0` | `Game_BootstrapWorld` |
| `FUN_1400c1850` | `Game_InitCore` |
| `FUN_1400c3c10` | `Game_InitRender` |
| `FUN_14003ee50` | `Game_LoadAssets` |
| `FUN_140096d20` | `GameState_Ctor` |
| `FUN_140097110` | `GameState_InitMain` |
| `DAT_140313720` | `g_game_state` |

---

## Still open

- [x] Capstone **`0x97110`** — [GameState_InitMain.md](GameState_InitMain.md)
- [x] Capstone **`0x3EE50`** — [Game_LoadAssets.md](Game_LoadAssets.md)
- [ ] Xref **`g_game_state@0x313720`** — who reads it in `Game_UpdateWorld` / loop
