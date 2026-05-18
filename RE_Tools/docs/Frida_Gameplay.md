# Frida — gameplay hooks

Hooks verified RVAs from Ghidra / Capstone (`GameFunctions.h`).

## Script (you trigger gameplay)

```bat
python RE_Tools\tools\scripts\frida_gameplay_hooks.py --attach --seconds 120
```

1. Start **Horsey.exe** and **load a save** (stay in the farm / world).
2. Run the command above — it attaches and waits **120s** (prints a count every 5s).
3. While it runs, in-game:
   - **Shop** — buy something (`BuyItem` + often `GainMoney`)
   - **Farm** — place a horse (`SimSpawnDisk`)
   - **Race** — start a race through to “go” (`RaceGo_site`, `RaceStateMachine`)
4. When the timer ends, open `RE_Tools/analysis/gameplay_frida.json`.

`RaceStateMachine` may tick on the main menu too; focus on rows that appear **when you perform the action**.

Optional: `--full-events` to keep every raw event in the JSON.

## Hooks

| RVA | Symbol | When it fires |
|-----|--------|----------------|
| `0x10AB80` | `GainMoney` | Money changes (purchase payout, race prize, …) |
| `0x33A20` | `SimSpawnDisk` | Placing spawn / disk entities |
| `0x787D0` | `BuyItem` | Shop buy dialog dispatch |
| `0x8F2B0` | `RaceStateMachine` | Race UI tick (throttled) |
| `0x91274` | RaceGo site | Race “go” phase inside FSM |
| sim targets | from `sim_start_race_callees.json` | E8 dispatch stubs (`0x5F900`, …) |

`from_buy: true` on `gain_money` rows means backtrace passed through `BuyItem`.

## Related

- [GameplayFunctions.md](GameplayFunctions.md) — why race strings ≠ function entries
- [SimStartRace.md](SimStartRace.md) — E8 caller scan for sim dispatch
