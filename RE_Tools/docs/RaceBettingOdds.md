# Race betting UI — odds / payout RE

**Game:** `Horsey.exe` · **Status:** 2026-05-17 (initial pin)  
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

Dump in Ghidra: **`DAT_140263ba0`** (two 12-byte records). Not yet exported to JSON.

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

```c
// rcx = horse at call site in HorseRaceScore
void *sub = *(void **)((uint8_t *)horse + 0x148);
if (!sub) return 0;
return SomeCheck_0xB2110(sub);  // @ 0xD6DD0
```

So betting-time failure is often **`CanScoreHorse`**, not only `ctx+0x258`.

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

## Frida probe (optional)

```bat
python RE_Tools\tools\scripts\frida_race_betting_probe.py --attach --seconds 30
```

On betting screen: logs `ctx+0xe0`, `0x2c0`, `0x2c4`, `0x450`, per-horse `+0x284`, and `g_prng_state`. Output: `RE_Tools/analysis/race_betting_probe.json`.

---

## Open RE (next)

- [ ] Dump **`DAT_140263ba0`** preset table to `race_bet_presets.json`
- [ ] Decompile **`FUN_1400b2110`** (CanScoreHorse gate) — when does it return true on betting screen?
- [ ] Trace **`FUN_1400b3ce0`** @ `0x1171` — lane highlight vs power
- [ ] Confirm whether any UI reads **`horse+0x220`** (speed) on betting screen

---

## race_predictor_mod policy

| Mode | When | Method |
|------|------|--------|
| **Estimate** | Pre-race screen (`e0` 0x1a/1b/18/19, phase&lt;9) | `nice*years` — **no PRNG** |
| **Live score** | `HorseRaceScore` hook fires with valid `+0x450` | Use game dword |

Do **not** enable PRNG snapshot scoring in the mod until `CanScoreHorse` + side effects are validated on `Game/Horsey.exe`.
