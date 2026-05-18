# SimStartRace — handler, dispatch, and tags

**Source:** `Game/Horsey.exe` · Capstone on `Game/`

---

## Summary

| Item | RVA | Role |
|------|-----|------|
| Tag string `SimStartRace` | `0x25BB70` | 16-byte sim message name |
| **Handler** | **`0x5F020`** | **`RaceSimHandler`** — posts tag when `[race+0xE0]==7` @ **`0x5F365`** |
| Race object ctor | `0x5F900` | `RaceSimObject_Init` — **not** the start-race handler |
| `SimMessageDispatch` @ `0x5E0C2` | — | **Misleading** — small stub (string cleanup), not sim hub |
| Tag loads only | `0x32FA3`, `0x5F372`, `0x3311D` | `movdqu` into message blobs |

---

## SimStartRace body (`RaceSimHandler` @ `0x5F020`)

When race UI state **`[ctx+0xE0] == 7`**:

1. Zero stack message @ `rbp-0x40`
2. **`movdqu` @ `0x5F36C`** — copies **SimStartRace** @ `0x25BB70`
3. **`call 0x40CE0`** — `BuildSimMessageBlob` (duration `0x64`, z `-50`)
4. **`[ctx+0x258] = 1`** — race-active flag
5. Message posted via sim layer (`SimPostMessage` @ `0xD6DF0` on other paths)

When **`[ctx+0x258] != 0`** first (lines `0x5F035`+): posts finish/cleanup tags then clears flag.

**Ghidra export:** [ghidra_exports/RaceSimHandler.c.txt](ghidra_exports/RaceSimHandler.c.txt)

---

## `RaceSimObject_Init` @ `0x5F900`

Constructor for race sim object:

- Initializes arrays @ `[obj+0x278]`, `[obj+0x280]`, horse count @ `[obj+0x298]`
- Sets `[obj+0x250] = 0x9C4`
- Copies short tag `"start"` @ `0x5F9D1` into child widget

Called from save/type-1 paths (`0x103FC3`, `0x1050D5`) — **not** the in-race “go” message.

---

## E8 scan (spawn / mid sim regions)

See [analysis/sim_start_race_callees.json](../analysis/sim_start_race_callees.json).

`find_sim_start_race.py` lists E8 into `0x33000`–`0x35000` and `0x5F000`–`0x61000`; those are **internal** callees, not `SimStartRace` entry points.

---

## Horse score vtable (related)

Sim handler function pointers @ **`0x267368`**:

| Offset | RVA |
|--------|-----|
| +0 | `0xE2B80` `HorseRaceScore` |
| +8 | `0xE3F10` |

See [RaceMechanics.md](RaceMechanics.md).

---

## Analysis / Frida

```bat
python RE_Tools/tools/scripts/analyze_race_mechanics.py
python RE_Tools/tools/scripts/frida_gameplay_hooks.py --attach
```

- `race_advance_sim` logs `[race_ctx+0x450]` (`race_score_450`) vs finish slots during races
- Use `--no-race-sim` to reduce volume
