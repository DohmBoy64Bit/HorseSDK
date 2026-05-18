# SimStartRace — caller scan

## Why string xrefs mislead

`SimStartRace` @ `.rdata` `0x25BB70` is referenced by **movups** inside dispatch stubs
(`0x32FA3`, `0x5F372`) — those sites copy the tag into a message object, they are **not**
the function entry that starts a race. Ghidra `RaceCluster` export was empty for the same
reason: **no function starts** in `0x90E00`–`0x92000`; race UI lives in `RaceStateMachine` @ `0x8F2B0`.

## E8 callers into dispatch regions

| Region | RVA range | Role |
|--------|-----------|------|
| `sim_spawn_dispatch` | `0x33000`–`0x35000` | Spawn / early sim (incl. `SimSpawnDisk` @ `0x33A20`) |
| `sim_mid_dispatch` | `0x5F000`–`0x61000` | Mid sim handlers |

Total E8 hits (byte scan): **7**

### Top call targets

- **0x5f78e** — 1 caller(s)
  - from `0x5f77a` (fn `0x5e0c2`)
- **0x5f7f6** — 1 caller(s)
  - from `0x5f7e2` (fn `0x5e0c2`)
- **0x5f869** — 1 caller(s)
  - from `0x5f855` (fn `0x5e0c2`)
- **0x5f900** — 2 caller(s)
  - from `0x103fc3` (fn `0x102dc2`)
  - from `0x1050d5` (fn `0x103244`)
- **0x60540** — 2 caller(s)
  - from `0x5ff07` (fn `0x5e0c2`)
  - from `0x6db6b` (fn `0x6c912`)

### Top caller functions (by E8 count)

- `0x5e0c2` — 4 call(s) into regions
- `0x6c912` — 1 call(s) into regions
- `0x102dc2` — 1 call(s) into regions
- `0x103244` — 1 call(s) into regions

## String xref sites (tag load only)

- **SimStartRace** @ `0x32fa3` → entry guess `0x3166b`
- **SimStartRace** @ `0x5f372` → entry guess `0x5e0c2`
- **SimSpawnDisk** @ `0x342f0` → entry guess `0x32330`

## Frida

See [Frida_Gameplay.md](Frida_Gameplay.md) — attach, then start a race yourself; check
`racego_hits` and `sim_calls` in `RE_Tools/analysis/gameplay_frida.json`.
