# Frida — gameplay hooks

Hooks verified RVAs from Ghidra / Capstone (`GameFunctions.h`).

## Script (you trigger gameplay)

```bat
python RE_Tools\tools\scripts\frida_gameplay_hooks.py --attach
```

1. Start **Horsey.exe** and **load a save** (stay in the farm / world).
2. Run the command above — it attaches and waits until you **press Enter** (event count every 5s).
3. While it runs, in-game:
   - **Shop** — buy items (`SpendMoney` debits; `BuyItem` UI tick)
   - **Farm** — place a horse (`GrabHorse` @ `0xD6340`, `SpawnEntity` @ `0x30492`)
   - **Race** — start a race (`RaceStateMachine`)
4. Press **Enter** in the terminal when done — then open `RE_Tools/analysis/gameplay_frida.json`.

`RaceStateMachine` may tick on the main menu too; focus on rows that appear **when you perform the action**.

Optional: `--seconds 120` for a timed run instead of Enter. `--full-events` to keep every raw event in the JSON.

## Hooks

| RVA | Symbol | When it fires |
|-----|--------|----------------|
| `0x10AB80` | `GainMoney` | Credits (race prize, rewards) |
| `0x10AC60` | `SpendMoney` | Debits (shop buy — see `BuyItem.c.txt` → `FUN_14010ac60`) |
| `0x30492` | `SpawnEntity` | Calls `SpawnPlace` @ `0x30B52` |
| `0x32330` | `SpawnPlace` | Sim spawn callee |
| `0xD6340` | `GrabHorse` | Horse grab/place (12 callers; not `0xD71DF`) |
| `0xD3C50` | `DropHorseFail` | Invalid tile drop |
| `0x787D0` | `BuyItem` | Shop UI handler (throttled; fires often while shop open) |
| `0x8F2B0` | `RaceStateMachine` | Race UI (`--no-race` to skip menu noise) |
| `0x8C9E0` | `RaceAdvanceSim` | Per-frame race sim — logs `[race_ctx+0x450]` vs finish slot (`--no-race-sim` to skip) |

**Do not hook `0x91274` (RaceGo)** or **`0xE2C00`** (mid `HorseRaceScore`) — crashes / wrong entry.

`from_buy: true` on `spend_money` means backtrace through `BuyItem`.

## Race sim output (`race_advance_sim`)

Each sampled tick (250 ms throttle) includes:

- `snapshot.race_score_450` — `[race_ctx+0x450]` from `HorseRaceScore` (`0xE2FBD`)
- `snapshot.horses[]` — `finish_place` (slot `+0x0C`, `-1` = racing), `timer`, `progress`, `speed_220`
- `g_settings_seed` @ `0x2F1587`, `g_prng_state` @ `0x2F2700`

Enable `log_races` in `settings.xml` to also hit the score formula `printf` @ `0xE3021` in-game.

## Related

- [RaceMechanics.md](RaceMechanics.md) — score formula, sim vs betting
- [GameplayFunctions.md](GameplayFunctions.md) — why race strings ≠ function entries
- [SimStartRace.md](SimStartRace.md) — E8 caller scan for sim dispatch
