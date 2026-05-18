# Mod capabilities (current SDK state)

**Status:** 2026-05-17 · verified against `Game/Horsey.exe`, `ModLoader/`, `SDK/`, `horse_save`, `horse_data`.

This document describes what kinds of mods HorseSDK can support **today**, not the long-term roadmap.

---

## 1. In-game DLL mods (mod loader)

**Flow:** `horse_inject.exe` → `HorseModLoader.dll` → `mods/*.dll`.

Each mod exports `HorseMod_GetInfo`, `HorseMod_Init`, `HorseMod_Shutdown`. The host provides:

| Host API | Purpose |
|----------|---------|
| `game_base` | `Horsey.exe` module base |
| `resolve(rva)` | `base + RVA` from catalog |
| `hook_install` / `hook_remove` | MinHook detours (`horse_hook_install`) |
| `log` | Async debug console line |

**Reference:** `SDK/include/horse/mod_api.h`, `ModLoader/mods/example_mod/example_mod.c`.

### Proven today

- `example_mod` logs and forwards **GainMoney** (3-arg) and **SpendMoney** (4-arg: `ctx`, `cost`, `show_ui`, `str_variant`).
- Wrong detour arity **crashes** (shop buy) — see disasm @ `0x10AC94` / `0x10ACAB`, catalog `SpendMoney` parameters.

### Realistic in-game mod types now

| Type | Mechanism | Confidence |
|------|-----------|------------|
| **Economy** | Hook `GainMoney` / `SpendMoney` — free shop, multiply payouts, block debits | High |
| **Save triggers** | Hook `Save_Write` / `Save_Load` — log, backup, block autosave | Medium (avoid heavy work in detour) |
| **Race tracing** | Hook `RaceAdvanceSim`, `ClampInt3` | Medium–low (hot paths; score at `[race_ctx+0x450]`) |
| **General tracing** | Any of ~42 `HORSE_FN_*` typedefs in `game_function_types.h` | Varies — must match calling convention |

**Loader hook catalog** (`game_function_hooks.h`): GainMoney, SpendMoney, Save_Write, Save_Load, RaceAdvanceSim, ClampInt3. Console: `hook on Save_Write`, `resolve Save_Write`.

**Catalog also names** (hook at your own risk): `BuyItem`, `RaceStateMachine`, `HorseRaceScore`, `SimRandMod`, `GrabHorse`, `Game_UpdateWorld`, etc. — see [GameplayFunctions.md](GameplayFunctions.md).

### Not ready in-game

| Gap | Why |
|-----|-----|
| In-game UI (menus, HUD) | No ImGui/SDL overlay integration |
| Asset packs | No renderer / asset injection |
| Script mods (Lua) | Phase 6 — not started |
| Reliable race rigging | Sim documented; PRNG/seed path still open ([RaceMechanics.md](RaceMechanics.md)) |
| Live genetics editor | Runtime `GeneticsApply` @ `0xAE470` — [SaveFutureWork.md](SaveFutureWork.md) |
| Map editing in-game | TMX parser is offline only |
| C# / BepInEx | C DLL + manual inject only |
| Exe updates | RVAs break when `Horsey.exe` changes |

---

## 2. Offline / external tools (no injection)

| Tool | API | Use |
|------|-----|-----|
| **Save editor / trainer** | `horse_save_*` in `RE_Tools/src/horse_save/include/horse_save.h` | v12 read/write: grid, inventory gene packs (`0xF0`), footer |
| **Data inspectors** | `horse_data_*` — genes.dat, horsey.tmx, bmfont, atlas | Build external editors; does not patch running game |

**CLI:** `horse_save_cli`, `horse_data_cli`, `save_editor.py` (`info`, `backup`, `roundtrip`).

---

## 3. RE / validation tooling

| Script | Role |
|--------|------|
| `frida_gameplay_hooks.py` | Attach; log shop/race/spawn while you play |
| `verify_modloader_static.py` | Static checks (e.g. SpendMoney 4-arg prologue) without running game |
| `build_game_function_catalog.py` | Regenerate `HORSE_RVA_*` / typedefs |

---

## Practical summary

| Ready now | Not ready without more RE |
|-----------|---------------------------|
| C DLL hooks (economy, save hooks, logging) | Content mods, in-game UI, scripting |
| External save + data file tools | Easy race/horse cheats |
| Frida + catalog for dev tracing | Version-agnostic mods |

**Best player-facing mods today:** economy hooks + save file editing.  
**Best dev mods today:** trace hooks + console `resolve` / `hook on`.

---

## Related docs

- [Phase3_SDK.md](Phase3_SDK.md) · [Phase4_ModLoader.md](Phase4_ModLoader.md)
- [ModLoaderSmokeTest.md](ModLoaderSmokeTest.md) — manual + static validation
- [README.md](../../README.md) — roadmap
