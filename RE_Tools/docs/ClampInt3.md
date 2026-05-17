# `ClampInt3` @ `0xC12D0` (was mislabeled `Game_SimStep`)

**Verified on `Game/Horsey.exe`** — Capstone `map_clamp_int_callers.py`.

**Artifact:** `RE_Tools\analysis\clamp_int_callers.json`

## Signature

```c
// Horsey.exe+0xC12D0
int ClampInt3(int value /*ecx*/, int lo /*edx*/, int hi /*r8d*/) {
    if (value < lo) return lo;
    if (value > hi) return hi;
    return value;
}
```

Same RVA region also holds small **SSE helpers** (`MinSS` @ `0xC12F0`, float lerp @ `0xC1310`).

## Why Frida showed `rcx=0x64` / `0x500`

Hooks logged **`rcx` only**. At `SettingsLoader` (`0x714A3` / `0x714D2`) the **third** argument is the cap:

| Call site | `edx` (lo) | `r8d` (hi) | Meaning |
|-----------|------------|------------|---------|
| `0x714A3` | `0` | **`0xC8` (200)** | cap setting to 200 |
| `0x714D2` | `0` | **`0x64` (100)** | cap setting to 100 |

Frame loop @ `0xBE607` / `0xBE620`:

| Site | `edx` | `r8d` |
|------|-------|-------|
| `0xBE607` | **`0x140` (320)** | `r12d` |
| `0xBE620` | **`0xB4` (180)** | `r15d` |

These match half-resolution UI bounds (320×180 vs 960×540 reference).

## Post-swap loop

`0xBEC53` / `0xBEC79` clamp scroll/offset globals before `call 0x125E70` (render helper).

Rename in Ghidra: `FUN_1400c12d0` → **`ClampInt3`**. Do not hook as per-frame sim.
