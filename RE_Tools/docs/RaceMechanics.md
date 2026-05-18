# Race mechanics — simulation vs betting

**Source:** `Game/Horsey.exe` (image base `0x140000000`) · Capstone + Ghidra `Race_91148.c.txt` · repomix cross-check only where noted.

**Automation:** `python RE_Tools/tools/scripts/analyze_race_mechanics.py` → [race_mechanics.json](../analysis/race_mechanics.json) + `RE_Tools/analysis/disasm_race_*.txt`

---

## Summary

| Question | Answer (verified) |
|----------|-------------------|
| Is the winner fixed before the race? | **No** — score uses **rand + horse stats**, then sim advances positions with RNG checks. |
| Do horse stats matter? | **Yes** — `nice`, `record`, `years`, `deco`, genetic distance (`gdist`) feed the score. |
| Is there randomness? | **Yes** — explicit `rand` term, `SimRandMod` @ `0xC1900`, and post-score jitter @ `0xE3068`+. |
| Is the on-screen race real sim? | **Partially** — `RaceAdvanceSim` @ `0x8C9E0` updates per-horse **0x70** race records and entity speed; `LerpHorse` is a **sim message tag** for movement interpolation (not the score function). |
| Betting | Separate UI in `RaceStateMachine` @ `0x8F2B0` — `SpendMoney` / `GainMoney`; player can pick 1st/2nd/3rd for exotic bets. |

NPC lines like *"%s is a shure fire winner!"* are flavor text, not proof of a scripted winner.

---

## Race score formula (exe string + disasm)

### Debug format string

| Field | RVA |
|-------|-----|
| Format | `0x2674E0` |
| Text | `%s = (%d rand + %d nice + %d record) * %d years + %d deco   gdist=%.3f` |
| Print xref | `0xE3021` → `call 0xBEE80` when `log_races` (or related flag @ `0x3128E0`) is set |

Repomix documents the same string @ `0x41074E0` (VA) in [repomix-output-DohmBoy64Bit-Horsey-Game.xml](../../repomix-output-DohmBoy64Bit-Horsey-Game.xml).

### Computation (Capstone @ `0xE2C2C`–`0xE2FE2`)

Per horse in a loop (`0xE2D52` … `0xE2F99`, stride **4** on a side table):

| Step | RVA | What it does |
|------|-----|----------------|
| **years** | `0xE2C29`–`0xE2C3A` | `ClampInt3` @ `0xC12D0` on age fields → `[rbp-0x55]` |
| **nice** | `0xE2C47`–`0xE2C77` | Sum of gene table @ `horse+0x2A8` + world @ `[rcx+0x148]+0x2A8`, **mod 11**, then **+5** → `[rbp-0x21]` |
| **record** | `0xE2CB0`–`0xE2CEE` | If genetic distance `xmm6` &lt; threshold: `call 0xC1500` → `[rbp+0x7f]` |
| **gdist** | `0xE2CA8` | `call 0x9DAD0` (parent/child gene distance) → `xmm6` for log |
| **rand** | `0xE2D52`+ | Loop builds `edi` (rand component); see `call 0xC2200` @ `0xE2FD5` |
| **deco** | `0xE2FB5` | `[rbp+0x67]` equipment bonus |
| **score** | `0xE2FAC`–`0xE2FBD` | `eax = record + nice + rand`; `eax *= years`; `ecx = eax + deco (+5 if flag @ horse+0x205)` |
| **store** | `0xE2FBD` | `mov [rsi+0x450], ecx` — **race power** on **race context** (`rsi` = `rcx` @ `0xE2BA4`) |
| **clamp** | `0xE2FD5`–`0xE2FE2` | `call 0xC2200(2)` then `max` with floor |

Pseudocode (matches disasm, not a decompiler name):

```c
// horse = r13, race ctx = rsi (= rcx), score_out = [ctx+0x450] (single dword, not per-horse)
years  = clamp(age_delta, 0, 11);           // 0xC12D0
nice   = (sum_genes % 11) + 5;
record = genetics_record_score(gdist);      // 0xC1500 if gdist low enough
rand   = ...;                               // loop + 0xC2200
deco   = equipment_bonus;
score  = (record + nice + rand) * years + deco;
if (!horse[0x205]) score += 5;
[ctx+0x450] = max(score, RaceFloor(2));     // 0xC2200; rsi=rcx @ 0xE2BA4
```

### Post-score randomness (same function, `0xE2FE5`+)

When race type @ `[rsi+0x258] == 4` and entity type @ `[rax+0x1C] == 2`:

| RVA | Effect |
|-----|--------|
| `0xE3068` | `SimRandMod(4)` — quartering |
| `0xE307E` | `SimRandMod(0x28)` — 1-in-40 “skip” style branch |
| `0xE308F` | `SimRandMod(0x2710)` added to score |

So even after the formula, **sumo/normal race mode 4** can nudge effective power.

---

## PRNG (`SimRandMod` @ `0xC1900`)

- Updates global state @ `0x3128D8` (xor-shift style), returns `edx = state % ecx`.
- Overload @ `0xC1940`: random in `[ecx, edx]` inclusive.
- Used heavily in `RaceStateMachine` (e.g. pick horse index: `FUN_1400c1900(horse_count)` @ Ghidra `0x91244`) and genetics.

**Settings:** repomix lists `seed` and `log_races` in `settings.xml` — seed likely feeds this PRNG path (exact write site not fully traced).

---

## Race simulation (movement / finish order)

### `RaceStateMachine` @ `0x8F2B0`

Ghidra export: [ghidra_exports/Race_91148.c.txt](ghidra_exports/Race_91148.c.txt).

Each frame when `log_races`/demo flags set @ `0x2F155B` / `0x31299E`:

- `RaceAdvanceSim` @ `0x8C9E0`
- `RaceUpdateHorses` @ `0x8CC10`
- `RaceInitLayout` @ `0x8A850`

### `RaceAdvanceSim` @ `0x8C9E0`

Walks `param_1+0x280` → array of **0x70-byte** race slots per horse:

| Offset in slot | Use (from disasm / Ghidra) |
|----------------|----------------------------|
| `+0x0C` | Finish place (**-1** = still racing) |
| `+0x10` | Progress / segment |
| `+0x14` | Timer (thresholds `0x12C`, `0x168`, `0x258`, `0xB4`) |
| `+0x24` | Speed factor (mul/div with `@ [horse+0x220]`) |

Updates **`[horse+0x220]`** (speed) from progress — not a cosmetic-only animation.

### Finish detection (Ghidra ~`0x912F9` / `0x1299`–`0x1316`)

- When progress float crosses `param_1+0x2F8`, set `slot+0x0C` to place index, fire `CrossFinishLine` message via `0x40CE0`.
- Periodic RNG @ frame `0x254 % 0x3C == 0`: `SimRandMod(10)==0` then pick random horse to advance (`FUN_140092e40`).

**Conclusion:** finish order emerges from **sim state + RNG**, not a single pre-selected winner.

### `LerpHorse` (sim tag @ `0x262830`)

- String xref @ **`0x76149`** / message build @ **`0x76229`** — loads tag into `0x40CE0` blob (same pattern as `SimStartRace`).
- Actual position delta @ **`0x761F4`–`0x7620D`**: subtract current from target, store to `[horse+0x1E4]` / `[horse+0x1E8]`.

Do **not** hook `0x76149` (mid-instruction). Prefer sim dispatch or `RaceAdvanceSim`.

### `SimStartRace` (tag @ `0x25BB70`)

- Tag loads: `0x32FA3`, `0x5F372` (not function entries).
- Dispatch hub: **`SimMessageDispatch` @ `0x5E0C2`** — see [SimStartRace.md](SimStartRace.md).
- Mid-handler snippet @ `0x5F365`–`0x5F3EC`: builds message, sets `[rbx+0x258]=1`, returns.

---

## Betting & payouts (UI layer)

Inside `RaceStateMachine` (Ghidra):

- **Bet debit:** `SpendMoney` @ `0x10AC60` with amount `[param_1+0x2C0]`.
- **Win credit:** `GainMoney` with payout derived @ `0x913`–`0x915` from bet fields `0x2D4`, `0x2D8`, `0x2C0`.
- UI strings: pick 1st / 2nd / 3rd, `Betting`, `StartNextRace`.

Frida-confirmed: `spend_money` on bet, `gain_money` +50 on win (`from_buy: false`).

---

## Function map (SDK hooks)

| RVA | Symbol | Role |
|-----|--------|------|
| `0x8F2B0` | `RaceStateMachine` | Race UI FSM |
| `0x8C9E0` | `RaceAdvanceSim` | Per-frame sim step |
| `0x8CC10` | `RaceUpdateHorses` | Horse list sync during race |
| `0x8A7F0` | `RacePhaseDispatch` | Phase transitions |
| `0x8A850` | `RaceInitLayout` | Race setup |
| `0xC1900` | `SimRandMod` | `rand % n` (and range overload) |
| `0xC2200` | `RaceScoreFloor` | Only caller from score path @ `0xE2FD5` |
| `0xE2B80` | `HorseRaceScore` | `(rand+nice+record)*years+deco` → `[ctx+0x450]`; vtable `0x267368[0]` |
| `0x5F020` | `RaceSimHandler` | **SimStartRace** post @ `0x5F365` when `[ctx+0xE0]==7` |
| `0x5F900` | `RaceSimObject_Init` | Race sim object ctor (not the start-race handler) |
| `0xD6DF0` | `SimPostMessage` | Tag strcmp + sim message routing |
| `0x2F1587` | `g_settings_seed` | Parsed from `settings.xml` key `seed` @ `0x71BCE` |
| `0x2F2700` | `g_prng_state` | `SimRandMod` / `SimRandSeedFromFloat` state |
| `0x10AB80` / `0x10AC60` | `GainMoney` / `SpendMoney` | Economy |

---

## HorseRaceScore @ `0xE2B80`

**Entry:** `0xE2B80` (prologue @ `0xE2B85`; do not hook `0xE2C00` — gate test only).

**Signature:** `void HorseRaceScore(RaceContext *ctx /*rcx*/, int horse_index /*edx*/);`

**Dispatch:** no direct `E8` callers; invoked via **sim handler vtable** @ **`0x267368`** slot 0.

| Vtable RVA | Handler RVA | Role |
|----------|-------------|------|
| `0x267368`+0 | `0xE2B80` | `HorseRaceScore` |
| `0x267368`+8 | `0xE3F10` | (next sim handler) |

**Ghidra export:** [ghidra_exports/HorseRaceScore.c.txt](ghidra_exports/HorseRaceScore.c.txt)

---

## SimStartRace handler @ `0x5F020` (`RaceSimHandler`)

**Not** `SimMessageDispatch` @ `0x5E0C2` (that function is a small string dtor stub).

**Not** `RaceSimObject_Init` @ `0x5F900` (race struct constructor only).

| RVA | Behavior |
|-----|----------|
| `0x5F020` | `RaceSimHandler` entry — race sim virtual tick |
| `0x5F365`–`0x5F3EC` | When `[ctx+0xE0] == 7`: build **SimStartRace** tag (`movdqu` from `0x25BB70`), `BuildSimMessage` @ `0x40CE0`, set `[ctx+0x258]=1` |
| `0x5F042` | Alternate path when `[ctx+0x258]!=0` (race wind-down messages) |
| `0x5F353` | `call [vtable+0x60]` — generic state dispatch |

Tag-only loads (not function entries): `0x32FA3`, `0x5F372`, `0x3311D`.

**Ghidra export:** [ghidra_exports/RaceSimHandler.c.txt](ghidra_exports/RaceSimHandler.c.txt)

---

## `settings.xml` seed → PRNG

| Item | RVA | Notes |
|------|-----|-------|
| Key string `"seed"` | `0x26254C` | Repomix / exe strings |
| Parse site | `0x71BCE` | `Settings_ApplyValue` @ `0x25750`, dest **`g_settings_seed`** @ **`0x2F1587`** |
| PRNG state | `0x2F2700` | Read/written by **`SimRandMod`** @ `0xC1900` |
| Reseed helper | `0xC2080` | `SimRandSeedFromFloat` — same xor-shift mix as `SimRandMod` |

**Verified:** `SettingsLoader` writes `g_settings_seed` via pointer (`lea r8` @ `0x71BBD`).

**Partial:** no static RIP-relative **read** of `0x2F1587` found; seed may be consumed through save-game load / world-gen (`0x3BBEB` calls `0xC2080` with stack coords). See [SettingsLoader.md](SettingsLoader.md#seed-and-prng).

**Ghidra export:** [ghidra_exports/SimRandSeed.c.txt](ghidra_exports/SimRandSeed.c.txt)

---

## Frida: `RaceAdvanceSim` snapshot

```bat
python RE_Tools\tools\scripts\frida_gameplay_hooks.py --attach
```

During a race, **`race_advance_sim`** rows in `gameplay_frida.json` include per horse:

| Field | Source |
|-------|--------|
| `race_score_450` | `[race_ctx+0x450]` from `HorseRaceScore` (`mov [rsi+0x450]` @ `0xE2FBD`) |
| `finish_place` | race slot `+0x0C` (`-1` = still running) |
| `timer` / `progress` | slot `+0x14` / `+0x10` |
| `g_settings_seed` | global @ `0x2F1587` |
| `g_prng_state` | global @ `0x2F2700` |

Use `--no-race-sim` to skip if too verbose; `--no-race` to skip FSM only.

---

## Related docs

- [GameplayFunctions.md](GameplayFunctions.md) — string xref pitfalls
- [SimStartRace.md](SimStartRace.md) — E8 caller scan
- [Frida_Gameplay.md](Frida_Gameplay.md) — live hooks
- [ClampInt3.md](ClampInt3.md) — used for `years` clamp in score path

---

## Open RE (pinned — deferred for Phase 3 SDK work)

- [ ] Static path: `g_settings_seed` → `g_prng_state` (no RIP read of `0x2F1587` yet)
- [ ] Map vtable index → tag name for all slots @ `0x267368`
- [x] Frida: read `[race_ctx+0x450]` as `race_score_450` (not `[horse+0x450]` — that offset is fill/garbage on horse objects)
- [ ] Run Frida race capture with `log_races=1` and correlate `race_score_450` vs `finish_place`
