# `Game_SimStep` @ `0xC12D0`

**Capstone** on `Game/Horsey.exe` — primary per-frame / UI sim driver.

| Field | Value |
|-------|-------|
| **RVA** | `0xC12D0` |
| **Size** | ~`0x154` bytes |
| **E8 callers** | 24 (frame loop: 2) |

**Artifacts:** `RE_Tools\analysis\phase1_game_sim_step.json`, `RE_Tools\analysis\disasm_game_sim_step.txt`

## Frame loop sites (`0xBEA00`–`0xBEE00`)

- `0xbec53`
- `0xbec79`

## Top callees

| Callee | Count |
|--------|-------|
| `0x225020` | 1 |

## Frida (`frida_game_sim_step.py`)

Artifact: `RE_Tools/analysis/frida_game_sim_step.json`

| Metric | Value |
|--------|-------|
| Frames (swap) | 482 |
| `Game_SimStep` / frame (avg) | ~0.8 |
| Max burst (frame 0, init) | 388 |
| `Game_UpdateWorld` / frame (avg) | ~1.4 |

Init burst: `Horsey.exe+BE60C` (loop), `+714A8` / `+714D7` (settings region). Idle gameplay: **~0** sim steps per frame unless UI paths fire (e.g. `+A687A`).

Contrast: [Game_WorldSimStep.md](Game_WorldSimStep.md) @ `0x88510` is resize-gated (0 Frida hits with stable window).

| Ghidra rename |
|---------------|
| `FUN_1400c12d0` → `Game_SimStep` |
