# ~~`Game_SimStep`~~ → **`ClampInt3` @ `0xC12D0`**

**Correction (Capstone May 2026):** `0xC12D0` is **not** a simulation step. It is a 3-argument integer clamp helper in a utility cluster (also `MinSS` @ `0xC12F0`, float lerp @ `0xC1310`).

**See:** [ClampInt3.md](ClampInt3.md) — signature, all 24 callers, and why Frida logged `rcx=0x64` / `0xC8` (those were **`r8d` caps** at `SettingsLoader`, not sim modes).

Frida artifact `frida_game_sim_step.json` counts clamp calls during init/UI, not world sim.

**World / resize sim:** [Game_WorldSimStep.md](Game_WorldSimStep.md) @ `0x88510` (resize-gated).  
**Per-frame update:** [Game_UpdateWorld.md](Game_UpdateWorld.md) @ `0x87510`.
