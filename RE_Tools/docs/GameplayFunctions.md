# Gameplay functions (race / shop / spawn / economy)

**Source:** `Game/Horsey.exe` string xrefs · **31** function entries

Regenerate xrefs: `python RE_Tools/tools/scripts/find_gameplay_functions.py`

Decompile (Ghidra): `RE_Tools/ghidra_scripts/run_export_gameplay.bat` or `ExportGameplayDecompile.java` → `ghidra_exports/`

## Ghidra exports (`ghidra_exports/`)

| File | Entry RVA | Verified signature / role |
|------|-----------|---------------------------|
| [GainMoney.c.txt](ghidra_exports/GainMoney.c.txt) | **`0x10AB80`** | `void GainMoney(ctx, amount, show_ui)` — `[ctx+0x308]+=amount` |
| [SimSpawnDisk.c.txt](ghidra_exports/SimSpawnDisk.c.txt) | **`0x33A20`** | Large spawn FSM; `SimSpawnDisk` string @ `0x342F0` inside |
| [BuyItem.c.txt](ghidra_exports/BuyItem.c.txt) | **`0x787D0`** | Shop buy/dialog dispatch |
| [Race_91148.c.txt](ghidra_exports/Race_91148.c.txt) | **`0x8F2B0`** | Race state machine (~12 KB); `RaceGo` xref @ `0x91148` |

`RaceCluster.c.txt` had **0 functions** because no function **starts** in `0x90E00`–`0x92000` — race logic lives inside **`RaceStateMachine`** @ `0x8F2B0`.

### Why we missed race logic at first

| Approach | What it found | Why it failed |
|----------|----------------|---------------|
| String xref scan | Code at `0x91148`, `0x90E1B`, … | Those are **mov** into message blobs inside a 12 KB FSM, not function entries |
| Ghidra `RaceCluster` range export | 0 functions in `0x90E00`–`0x92000` | Ghidra lists functions by **entry**; the cluster is all mid-function |
| `SimStartRace` string xref | `0x32FA3`, `0x5F372` | Tag **load** sites only; real sim dispatch hub is **`SimMessageDispatch` @ `0x5E0C2`** ([SimStartRace.md](SimStartRace.md)) |

### SimStartRace body (E8 scan)

See [SimStartRace.md](SimStartRace.md): **`0x5E0C2`** calls into `0x5F78E`, `0x5F900`, `0x60540`, …; spawn region `0x33000` has **no** external E8 callers (internal tail calls only).

## Pinned (Capstone string xref)

| String RVA | Name | Category | Summary |
|------------|------|----------|---------|
| `0x10AB80` | **GainMoney** | economy | Entry = function start (matches Ghidra) |
| `0x342F0` | **SimSpawnDisk** | spawn | String inside `FUN_140033a20` |
| `0x78B00` | **BuyItem** | shop | String inside `FUN_1400787d0` |
| `0x91148` | **RaceGo** | race | Xref inside race FSM @ `0x8F2B0` |

## By category (auto xref)

### breeding

| RVA | Name | Strings |
|-----|------|---------|
| `0x56892` | `StatusFoal` | StatusFoal |
| `0xdbc1f` | `StatusFoal` | StatusFoal |
| `0xe90ea` | `Studs` | Studs |

### economy

| RVA | Name | Strings |
|-----|------|---------|

### horse

| RVA | Name | Strings |
|-----|------|---------|
| `0x76149` | `LerpHorse` | LerpHorse |
| `0xd3c50` | `DropHorseFail` | DropHorseFail |
| `0xd9158` | `GrabHorse_dispatch` | GrabHorse, DropHorseFail |

### race

| RVA | Name | Strings |
|-----|------|---------|
| `0x2cfe0` | `Betting` | Betting |
| `0x2dae7` | `RaceGetSet_dispatch` | RaceGetSet, RaceGo, CrossFinishLine |
| `0x32fa3` | `SimStartRace` | SimStartRace |
| `0x334e5` | `SimHorseFinished` | SimHorseFinished |
| `0x5f068` | `SimHorseFinished` | SimHorseFinished |
| `0x5f372` | `SimStartRace` | SimStartRace |
| `0x8a62f` | `OnYourMark` | OnYourMark |
| `0x8f523` | `OnYourMark` | OnYourMark |
| `0x8fce4` | `Betting` | Betting |
| `0x908bd` | `BetMore_dispatch` | BetMore, BetMax |
| `0x90e1b` | `RaceGetSet_dispatch` | RaceGetSet, RaceGo, Betting |
| `0x912f9` | `CrossFinishLine_dispatch` | CrossFinishLine, Racing |
| `0x9177b` | `WonRace` | WonRace |
| `0x91dde` | `WonRace` | WonRace |

### shop

| RVA | Name | Strings |
|-----|------|---------|
| `0x785a0` | `Shopkeep` | Shopkeep |
| `0x7ac8e` | `HorseMart` | HorseMart |
| `0x10ac60` | `BuyItem_dispatch` | BuyItem, LoseMoney |

### spawn

| RVA | Name | Strings |
|-----|------|---------|
