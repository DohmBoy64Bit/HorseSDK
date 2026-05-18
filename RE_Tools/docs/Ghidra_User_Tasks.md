# Ghidra / x64dbg — optional (automation-first)

**Default workflow:** `pefile` + **Capstone** (`RE_Tools/tools/scripts/*.py`) + **Frida** on `Game/Horsey.exe`. Scripts write `RE_Tools/analysis/*.json` and update `docs/*.md`.

**Use Ghidra/x64dbg only when:**
- Capstone cannot resolve indirect calls / vtables without runtime
- A function is too large for readable disasm-only docs (switch tables, STL)
- You want to double-check a controversial calling convention

When you do paste decompiler text into:

`RE_Tools/docs/ghidra_exports/<FunctionName>.c.txt`

(or reply in chat). We merge confirmed facts into `GameLoop.md` / `ReverseEngineeringProgress.md` with a `[KNOWLEDGE UPDATE]` block.

**Image base:** `0x140000000` · **VA = 0x140000000 + RVA**

---

## Quick setup

### Ghidra

1. Import `Game/Horsey.exe`, analyze (default + Decompiler).
2. Memory Map → set image base `0x140000000` if not already.
3. `Window → Bytes: Create label` or `L` at each RVA below.
4. Import labels (optional): copy the table from [GameLoop.md](GameLoop.md) § “Ghidra label sheet”.
5. For each task: go to VA, press `F` (create function) if needed, then `Decompile`.

### x64dbg

1. File → Open `Game/Horsey.exe` (or attach after launch).
2. Breakpoints use **`Horsey.exe+RVA`** (module base may differ — check `lm` / Modules).
3. When a break hits: note **RCX/RDX/RSI/RDI**, stack `[rsp]`, and **call stack** (right panel).

---

## Priority tasks (game loop) — do these first

### Task A — Label `GameMain` (5 min)

| | |
|--|--|
| **Ghidra GO** | `0x1400BE0F0` |
| **Name** | `GameMain_InitAndLoop` |
| **x64dbg** | Optional: `bp Horsey.exe+BE0F0` once at startup |

**Deliverable:** Screenshot or confirm labels applied. No paste required unless something disagrees with [GameLoop.md](GameLoop.md).

---

### Task B — `Game_DispatchSdlEvent` — **DONE**

| | |
|--|--|
| **Ghidra GO** | `0x1400C0430` |
| **Export** | [`ghidra_exports/Game_DispatchSdlEvent.c.txt`](ghidra_exports/Game_DispatchSdlEvent.c.txt) |
| **Merged doc** | [`Game_DispatchSdlEvent.md`](Game_DispatchSdlEvent.md) |

Optional follow-up: rename `FUN_140027f70` → `PathJoin`, `FUN_1400874b0` → `Game_BootstrapWorld`.

---

### Task C — `GameMain` (init + loop + shutdown) — **DONE**

| | |
|--|--|
| **Ghidra** | `FUN_1400be0f0` @ `0x1400BE0F0` |
| **Export** | [`ghidra_exports/GameMain_InitAndLoop.c.txt`](ghidra_exports/GameMain_InitAndLoop.c.txt) |
| **Merged doc** | [`GameMain_InitAndLoop.md`](GameMain_InitAndLoop.md) |

**Confirmed:** `g_sdl_quit@0x318A50` → **`jnz 0xBED0C`** @ `0xBEA66`; **`Settings_Save` @ `0x71F60`** @ `0xBED11` (not `Save_Write`); `Game_BootstrapWorld@0x874B0` @ `0xBE7C1`.

---

### Task D — Frame loop only (optional)

| | |
|--|--|
| **Ghidra** | `0x1400BEA7F` – `0x1400BED82` |
| **x64dbg** | `bp Horsey.exe+BEAF0` (every frame), `bp Horsey.exe+BEAE7` (quit skip render) |

**Paste:** `ghidra_exports/GameMain_FrameLoop.c.txt` if substantially different from [GameLoop_Static.md](GameLoop_Static.md).

---

## Secondary tasks (when A–C done)

| Function | Ghidra VA | x64dbg BP | Paste to |
|----------|-----------|-----------|----------|
| `SettingsLoader` | `0x1400711B0` | `+711B0` | **done** — [SettingsLoader.md](SettingsLoader.md) |
| `Game_BootstrapWorld` | `0x1400874B0` | `+874B0` | **done** — [Game_BootstrapWorld.md](Game_BootstrapWorld.md) |
| `Game_UpdateWorld` | `0x140087510` | `+87510` | **done** — [Game_UpdateWorld.md](Game_UpdateWorld.md) |
| `Loop_Helper_BEEA0` | `0x1400BEEA0` | `+BEEA0` | `Loop_Helper_BEEA0.c.txt` |
| `Save_Write` | `0x14006DAB0` | `+6DAB0` | **done** — [Save_Write.md](Save_Write.md) |

---

## Paste template

```text
# Function: Game_DispatchSdlEvent
# RVA: 0xC0430
# Ghidra: Horsey.exe @ 1400C0430
# Date: YYYY-MM-DD
# Notes: (anything odd — calling convention, globals renamed)

<paste decompiler here>
```

---

## Frida (automated — run locally)

Logs SDL event types when dispatch is hooked:

```bat
python RE_Tools\tools\scripts\frida_gameloop.py --frames 8
python RE_Tools\tools\scripts\frida_trace_sdl_events.py --seconds 15
```

Static refresh:

```bat
python RE_Tools\tools\scripts\map_gamemain_loop.py
python RE_Tools\tools\scripts\analyze_gamemain_functions.py
```

---

## Do not waste time on

| RVA | Reason |
|-----|--------|
| `0x11E0F0` | Repomix “RenderFrame” — **not called** (Frida 0 hits) |
| `0xBEA80` alone | Misaligned; real loop starts **`0xBEA7F`** / body **`0xBEA85`** |

---

## Gameplay export (scripted)

| | |
|--|--|
| **Script** | `RE_Tools/ghidra_scripts/ExportGameplayDecompile.java` |
| **Batch** | `RE_Tools/ghidra_scripts/run_export_gameplay.bat` |
| **Output** | `GainMoney.c.txt`, `SimSpawnDisk.c.txt`, `BuyItem.c.txt`, `RaceCluster.c.txt` |

RVAs: `0x10AB80`, `0x342F0`, `0x78B00`, race cluster `0x90E00`–`0x92000`.

---

## Checklist

- [ ] Task A — labels on `GameMain` + loop sites
- [x] Task B — decompile `0xC0430` + paste
- [x] Task C — decompile `GameMain` + paste
- [ ] Task D — (optional) frame loop decompile
- [x] `Game_BootstrapWorld@0x874B0` — [Game_BootstrapWorld.md](Game_BootstrapWorld.md)
