# `Game_WorldSimStep` @ `0x88510`

**Capstone** on `Game/Horsey.exe` · **Frida:** `frida_world_sim_step.py`

| Field | Value |
|-------|--------|
| **RVA** | `0x88510` |
| **Size** | `0xAB` bytes (`0x88510`–`0x885BB`) |
| **Caller** | `Game_UpdateWorld` @ **`0x875FA`** (sole E8 site) |
| **Artifacts** | `phase1_world_sim_step.json`, `disasm_world_sim_step.txt` |

---

## Role

**Window-resize / layout sim hook** — not the per-frame hot path.

`Game_UpdateWorld` only calls this when normalized window delta **≠ 0** (`JZ` @ `0x875F4` skips to `0x876E9`). With a stable window, Frida reports **`Game_UpdateWorld` every frame, `Game_WorldSimStep` 0 hits** (20 s run, 1183 frames).

---

## Disassembly summary

```c
void Game_WorldSimStep(void) {
    if (byte@0x312A4E || byte@0x312943)   // gate flags
        goto clear_flag_path;
    if (!byte@0x31294A)
        goto alt_path_B;

    // Path A: PathJoin two std::string globals, then clear byte@0x312C00
    PathJoin_027F70(...);
    byte@0x312C00 = 0;
    return;

alt_path_B:
    if (byte@0x312937 && qword@0x312978)
        jmp Game_SimHeavy_080B00;          // 0x080B00

    PathJoin variant → jmp FUN_140027830;  // 0x027830
}
```

| RVA | Instruction | Meaning |
|-----|-------------|---------|
| `0x88514` | `cmp byte [rip+0x29053a], 0` | Global gate |
| `0x8851D` | `cmp byte [rip+0x28a419], 0` | Second gate |
| `0x88526` | `cmp byte [rip+0x28a41e], 0` | Third gate |
| `0x88559` | `call 0x027F70` | `PathJoin` |
| `0x88588` | `jmp 0x080B00` | Heavy sim when layout buffer non-empty |
| `0x885B6` | `jmp 0x027830` | Lighter path |

---

## Integration

```text
GameMain @ 0xBEAD4
  → Game_UpdateWorld @ 0x87510
       → (if window delta != 0) Game_WorldSimStep @ 0x875FA
       → table broadcast @ 0x312830 (MOVUPS block)
```

See [Game_UpdateWorld.md](Game_UpdateWorld.md). Per-frame simulation elsewhere: **`Game_SimStep` @ `0xC12D0`** (called from settings load and other sites).

---

## Ghidra rename

| From | To |
|------|-----|
| `FUN_140088510` | `Game_WorldSimStep` |
