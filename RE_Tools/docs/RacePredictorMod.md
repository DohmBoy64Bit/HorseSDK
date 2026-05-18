# Race predictor mod

**Status:** 2026-05-17 · **Mod version:** 0.1.3 · **Game:** `Horsey.exe`

Pre-race **power ranking** from the same score the exe computes in `HorseRaceScore` @ `0xE2B80`, stored at **`[race_ctx+0x450]`** ([RaceMechanics.md](RaceMechanics.md), [HorseRaceScore.c.txt](ghidra_exports/HorseRaceScore.c.txt)).

## What it predicts (and what it does not)

| Does | Does not |
|------|----------|
| Rank lanes by **power score** after `HorseRaceScore` runs | Guarantee the winner (sim uses **RNG** in `RaceAdvanceSim` / `SimRandMod`) |
| Print **before** the race animation if scores are captured on the betting/setup screen | Read the betting UI or auto-place bets |
| Optional post-race line: how many top-3 power picks matched `finish_place` | Replace handicapping / flavor NPC text |

Formula (exe): `(rand + nice + record) * years + deco` → `[ctx+0x450]`.

## Usage

1. Build + deploy: `python RE_Tools/tools/scripts/deploy_modloader.py`
2. `HorseModLoader.ini`:

```ini
mods_order=example_mod.dll,race_predictor_mod.dll
```

3. Inject → go to **race / betting** screen → wait for score lines in the loader console.

**RE / probe:** [RaceBettingOdds.md](RaceBettingOdds.md) (static RE done; Frida capture pinned for `e0==0x1a` BetMore).

**Betting vs race scoring:** On the betting screen, `HorseRaceScore` usually **early-outs** (`[ctx+0x258]==0`, `CanScoreHorse` @ `0xD6DC0`) so `[ctx+0x450]` is garbage. **v0.1.3** estimates as soon as the **pre-race screen** is up — UI `ctx+0xe0` **0x1a** (BetMore/BetMax) or **0x1b** before the **0x18** state that runs `SpendMoney` on the race button ([Race_91148.c.txt](ghidra_exports/Race_91148.c.txt) @ `0x912`). Estimate: `nice * years (+5)` from disasm @ `0xE2C29`–`0xE2F77` via `ClampInt3` @ `0xC12D0`. Labels show `(est)`.

4. **Auto:** when ≥2 lanes are scored, prediction prints once (usually within ~1s on betting screen).
5. **Manual:** press **P** (farm/race focus, not loader console) to re-print.
6. After the race finishes, one summary line compares top-3 power pick vs `finish_place` @ slot `+0x0C`.

## Hooks

| RVA | Symbol | Role |
|-----|--------|------|
| `0xE2B80` | `HorseRaceScore` | Record `[ctx+0x450]` per `horse_index` |
| `0x8F2B0` | `RaceStateMachine` | Pre-race probe (`e0` 0x1a/1b/18/19, `+0x3d4`&lt;9) |
| `0x8C9E0` | `RaceAdvanceSim` | Detect race start + all `finish_place` set |
| `0xC0430` | `Game_DispatchSdlEvent` | **P** re-print |

## Race context (verified)

| Offset | Use |
|--------|-----|
| `+0x130` / `+0x138` | Horse pointer vector |
| `+0x298` | Horse count (Frida `readRaceSnapshot`) |
| `+0xe0` | UI state (**0x1a** bet UI, **0x18/19** picks, **0x1b** setup; **-1** `0xFFFFFFFF` seen on entry with `+0x3d4==6`) |
| `+0x3d4` | Race venue phase (&lt; 9) |
| `+0x2b0` | Betting-flow flag |
| `+0x258` | Race active (**0** during betting; scorer no-ops) |
| `+0x450` | Power score dword after each `HorseRaceScore` |
| `+0x280` + `i*0x70` | Per-horse race slot; `+0x0C` = `finish_place` |

## Source

`ModLoader/mods/race_predictor_mod/` — `race_predictor_mod.c`, `race_predictor.c`

## Roadmap

- [ ] Horse display names (lane # only today)
- [ ] Full `HorseRaceScore` on betting — blocked; see [RaceBettingOdds.md](RaceBettingOdds.md)
- [ ] Overlay line on race UI (`overlay=2` or ImGui)

## Related

- [RaceMechanics.md](RaceMechanics.md) · [Frida_Gameplay.md](Frida_Gameplay.md)
- [ModLoaderSmokeTest.md](ModLoaderSmokeTest.md)
