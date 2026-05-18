# Race betting UI — odds / payout RE

**Game:** `Horsey.exe` · **Status:** 2026-05-15 (bet table dump + gate RE complete)  
**Related:** [RaceMechanics.md](RaceMechanics.md) · [RacePredictorMod.md](RacePredictorMod.md) · [Race_91148.c.txt](ghidra_exports/Race_91148.c.txt)

---

## Summary

| Question | Answer (verified) |
|----------|-------------------|
| Does the betting UI show `HorseRaceScore` power per lane? | **No evidence** — UI uses **bet stake math** and **message blobs**, not `[race_ctx+0x450]`. |
| Where does BetMore/BetMax text come from? | `RaceStateMachine` @ `0x8F2B0`, UI `ctx+0xe0==0x1a` — payout preview formula @ **`0x860`**. |
| Where is stake min/max set? | Table **`DAT_140263ba0`** → `ctx+0x2c4` / `ctx+0x2c8` @ **`0x1186`**. |
| Can we call full `HorseRaceScore` on betting screen safely? | **Not cleanly** — early-outs + **`CanScoreHorse`** @ `0xD6DC0`; **rand** in formula advances **`g_prng_state`** @ `0x2F2700`. |
| Safe ranking today | **`race_predictor_mod` v0.1.3** — `nice*years` estimate (no PRNG). |

---

## Betting UI flow (RaceStateMachine)

| `ctx+0xe0` | Role (Ghidra) |
|------------|----------------|
| **0x1a** | BetMore / BetMax — adjust `ctx+0x2c0`, show payout preview |
| **0x18 / 0x19** | Pick 1st/2nd/3rd; **`SpendMoney`** @ `0x912` with `ctx+0x2c0` |
| **0x1b** | Pre-start setup (reset slots @ `0x872`+) |
| **-1** (`0xFFFFFFFF`) | Transition (seen in mod logs on screen entry) |

**Phase:** `ctx+0x3d4` (e.g. **6** on entry) — mod treats `1..8` as in race venue.

---

## Payout preview (not per-horse win%)

When `e0==0x1a` and bet amount `ctx+0x2c0` changes ([Race_91148.c.txt](ghidra_exports/Race_91148.c.txt) `0x835`–`0x862`):

```c
// iVar10 = current bet @ ctx+0x2c0 after clamp helpers @ 0xC0FA0
payout_preview = (float)iVar10 * DAT_14025b31c / (float)*(int *)(ctx + 0x2c4)
                 + DAT_1402bfb48;
// passed to BuildSimMessage @ 0x40CE0 — tag "BetMore" or "BetMax"
```

| Field | Offset | Role |
|-------|--------|------|
| Current bet | `+0x2c0` | Stake (also debited @ `SpendMoney` on race start) |
| Bet cap / divisor | `+0x2c4` | Loaded from `DAT_140263ba0 + index*0xC` |
| Secondary limit | `+0x2c8` | Paired dword from `DAT_140263b9c + index*0xC` |
| Exotic weights | `+0x2d4`, `+0x2d8` | Used in payout @ `0x913`–`0x915` after race |

**Conclusion:** On-screen “odds” during betting are **stake → payout** messaging, not `(rand+nice+record)*years` per horse.

---

## Bet preset table

@ **`0x1186`** (race setup when `ctx+0x250==0xc`, `ctx+0x254==0x10`):

```c
idx = (ctx+0x268 != 1) ? 1 : 0;
ctx+0x2c4 = *(u32*)(0x140263ba0 + idx * 0xC);
ctx+0x2c8 = *(u32*)(0x140263b9c + idx * 0xC);
```

Exported: **`RE_Tools/analysis/race_bet_presets.json`** (`python RE_Tools/tools/scripts/dump_race_bet_presets.py`).

| `idx` | `ctx+0x2c8` | `ctx+0x2c4` | Notes |
|-------|-------------|-------------|--------|
| **0** | 1 | 20 | `ctx+0x268 == 1` (standard) |
| **1** | 5 | 100 | `ctx+0x268 != 1` (alternate) |
| 2 | 25 | 500 | Extra row in `.rdata` (not selected by `0x1186` ternary) |
| 3 | 100 | 10000 | Third dword at `+8` is padding/garbage in dump |

Payout preview uses **`0.25 / (float)ctx+0x2c4 + 0.75`** (`DAT_14025b31c`, `DAT_1402bfb48`).

---

## Lane / horse UI (pick screen)

| Item | Evidence |
|------|----------|
| Horse list | `ctx+0x130` .. `+0x138` (qword per lane) |
| Highlight index | `ctx+0x2ac` — used @ `0x1173` (`FUN_1400b3ce0`) |
| Lane cursor | `ctx+0x2a8` — stride **0x10** table @ `[ctx+0x278]+0x298` @ `0x1195` |
| Horse message arg | `horse+0x284` @ `0x1234` → `FUN_1400678f0` |

No xref found from betting UI to **`HorseRaceScore`** or **`[ctx+0x450]`** per lane.

Flavor strings (*"shure fire winner"*, *"odds are slim"*) @ `0x730` — NPC text only.

---

## HorseRaceScore on betting screen

### Early-out gates (Capstone @ `0xE2B80`)

| Gate | RVA | Effect |
|------|-----|--------|
| `[ctx+0x258]==0` | `0xE2BE8` | Return — race not active |
| `horse == [ctx+0x148]` | `0xE2BF5` | Skip player horse |
| `CanScoreHorse(horse)` | `0xE2BFB` → `0xD6DC0` | Return if false |

### CanScoreHorse @ `0xD6DC0` (disasm)

Full dump: [disasm_CanScoreHorse_gate.txt](../analysis/disasm_CanScoreHorse_gate.txt).

```c
// rcx = horse at call site in HorseRaceScore
void *sub = *(void **)((uint8_t *)horse + 0x148);
if (!sub) return 0;
// FUN_1400b2110 @ 0xB2110 — only 7 bytes on this call path:
return *(int *)((uint8_t *)sub + 0x1c) < 4;
```

| Check | Meaning |
|-------|---------|
| `[horse+0x148] != NULL` | Sub-object (gene/world link — same field family as nice sum in `HorseRaceScore`) must exist |
| `[sub+0x1c] < 4` | Type/state dword must be below 4 |

Betting lanes often fail here when the sub-pointer is null or type ≥ 4 — **independent** of `ctx+0x258`. Forcing `ctx+0x258=1` alone still yields garbage scores if `CanScoreHorse` is false.

### FUN_1400b3ce0 @ `0xB3CE0` (lane highlight)

Called from [Race_91148.c.txt](ghidra_exports/Race_91148.c.txt) @ `0x1171` when `ctx+0x250==0xb`, `ctx+0x254==0x10`, `ctx+0x2f0!=0`, `ctx+0x2a5!=0`:

```c
horse = *(void **)(ctx + 0x130 + (ctx + 0x2ac) * 8);
FUN_1400b3ce0(horse);
```

Sets `horse+0x205` highlight word and, if `horse+0x1c == 1`, jumps to **`0xB3A50`** to set `horse+0x1c = 0` (visual idle). **Does not** read `horse+0x450`, `HorseRaceScore`, or **`horse+0x220`**.

### Single score dword

Even when scoring runs, only **`[race_ctx+0x450]`** is written (`0xE2FBD`) — **one** int per call, overwritten each lane. Mod must capture after each call into its own array.

---

## PRNG — safe full scorer?

**State:** one **`uint64_t`** @ **`g_prng_state` `0x2F2700`** ([SimRandSeed.c.txt](ghidra_exports/SimRandSeed.c.txt), [RaceMechanics.md](RaceMechanics.md)).

`HorseRaceScore` calls **`SimRandMod`** / gene loop (`0xE2D60`, `0xC1900`) — **variable** number of draws per horse.

### Snapshot restore (theoretical)

```c
uint64_t saved = *(uint64_t *)(base + 0x2F2700);
int saved258 = *(int *)(race_ctx + 0x258);
*(int *)(race_ctx + 0x258) = 1;
for (i = 0; i < n; i++) {
    HorseRaceScore(race_ctx, i);
    scores[i] = *(int *)((uint8_t *)race_ctx + 0x450);
}
*(uint64_t *)(base + 0x2F2700) = saved;
*(int *)(race_ctx + 0x258) = saved258;
```

| Pros | Cons |
|------|------|
| Race PRNG stream unchanged after probe | **`CanScoreHorse`** may still block all lanes on betting UI |
| No permanent desync if restore is exact | Captured **rand** terms are discarded on restore — ranking uses draws that **won't replay** at race start |
| | Each probe still mutates other globals (deco path, strings) — **not verified safe** |

**Recommendation:** Keep **estimate path** for betting. For full formula + rand, hook **`HorseRaceScore`** only when game calls it (race active, `ctx+0x258!=0`) or run offline clone of formula with saved gene tables.

### When game does call HorseRaceScore

Via sim vtable **`0x267368` slot 0** during race sim — after **`SimStartRace`** sets `ctx+0x258=1` ([RaceSimHandler.c.txt](ghidra_exports/RaceSimHandler.c.txt) `0x5F365`).

---

## Frida probe

```bat
python RE_Tools\tools\scripts\frida_race_betting_probe.py --attach --seconds 45
python RE_Tools\tools\scripts\frida_race_betting_probe.py --attach --wait-process 120 --seconds 45
```

Hooks **`RaceStateMachine`** @ `0x8F2B0` via `Process.findModuleByName('Horsey.exe').base` (required — do not hardcode `0x140000000` under ASLR).

Output: [race_betting_probe.json](../analysis/race_betting_probe.json) — `ctx+0xe0`, `0x2c0`, `0x2c4`, `0x2c8`, `0x450`, `0x258`, per-horse `+0x284` / `+0x220`, `g_prng_state`.

### Capture 2026-05-15 (103 samples, race venue idle)

| Field | Observed |
|-------|----------|
| `e0` | **-1** (transition) all samples — no BetMore `0x1a` / pick `0x18`/`0x19` in this run |
| `phase` | **6** |
| `race_active` (`+0x258`) | **0** |
| `bet_cap` / `bet_cap2` | **100 / 5** (matches preset idx 1 — [race_bet_presets.json](../analysis/race_bet_presets.json)) |
| `score450` | **1** (stale while `+0x258==0`) |
| `horse+0x220` | **30–41** at rest (not sim-driven on betting FSM) |

---

## RE completed (static + probe hook validated)

- [x] Dump **`DAT_140263ba0`** → [race_bet_presets.json](../analysis/race_bet_presets.json) (`dump_race_bet_presets.py`)
- [x] **`FUN_1400b2110`** — returns `[sub+0x1c] < 4` where `sub = [horse+0x148]`
- [x] **`FUN_1400b3ce0`** — highlight / `horse+0x1c` state only (see above)
- [x] **`horse+0x220`** — **no** access in `RaceStateMachine`; only **`RaceAdvanceSim`** @ `0x8C9E0`
- [x] Frida hook works — [race_betting_probe.json](../analysis/race_betting_probe.json) (103 samples @ `e0==-1`)

---

## Pinned — next (betting UI Frida)

- [ ] Re-run probe while interacting: **BetMore** (`e0==0x1a`), lane pick (`0x18`/`0x19`), confirm `bet` / `bet_cap` / `bet_cap2` track UI
- [ ] Capture `e0==0x1a` with `race_active==0` — confirm `score450` still garbage vs estimate path in mod
- [ ] Optional: correlate `horse+0x284` with UI flavor / lane index @ `Race_91148` `0x1234`
- [ ] **Do not** enable PRNG snapshot scorer in mod until `CanScoreHorse` true on all lanes during a scripted capture

---

## race_predictor_mod policy

| Mode | When | Method |
|------|------|--------|
| **Estimate** | Pre-race screen (`e0` 0x1a/1b/18/19, phase&lt;9) | `nice*years` — **no PRNG** |
| **Live score** | `HorseRaceScore` hook fires with valid `+0x450` | Use game dword |

Do **not** enable PRNG snapshot scoring in the mod until `CanScoreHorse` + side effects are validated on `Game/Horsey.exe` (see **Pinned** above).
