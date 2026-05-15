# Ghidra / x64dbg — Phase 1 Tasks

**Collaboration guide (breakpoints + paste targets):** [Ghidra_User_Tasks.md](Ghidra_User_Tasks.md)

Use **image base `0x140000000`** (RVA + base = VA). Verified on `Game/Horsey.exe` via `phase1_verify.py`.

## 1. Entry → main init (confirmed call edge)

| From | To | Evidence |
|------|-----|----------|
| `0x21EE0D` | `0xBE0F0` | Direct `E8` call (`phase1_verify.py`) |

**Ghidra:** Go to `0x1400BE0F0`. This is main game init (SDL, Steam, settings). Confirm `SteamAPI_RestartAppIfNecessary` at `0x1400BE106`.

## 2. Settings loader (confirmed call edge)

| From | To |
|------|-----|
| `0xBE562` | `0x711B0` |

**Ghidra:** Decompile `0x1400711B0`. Confirm it opens `settings.xml` (string @ `0x263860`) and `horsey.tmx` (`0x263850`).

## 3. Save function (confirmed callers)

| Caller RVA | Target |
|------------|--------|
| `0x9828C` | `0x6DAB0` |
| `0x10A2C2` | `0x6DAB0` |
| `0x10A822` | `0x6DAB0` |

**Ghidra:** Decompile `0x14006DAB0`. Cross-check write order with repomix §A.5 (`repomix-output-DohmBoy64Bit-Horsey-Game.xml`).

## 4. Per-frame render loop — **confirmed via Frida** (repomix `0x11E0F0` is wrong)

**Frida result** (`python RE_Tools/tools/scripts/frida_renderframe.py`):

| Finding | RVA |
|---------|-----|
| `SDL_GL_SwapWindow` return address (after `E8`) | **`0xBEAF5`** |
| `call SDL_GL_SwapWindow` instruction | **`0xBEAF0`** |
| Outer stack frame (init caller return) | **`0x21EE12`** |
| Repomix “RenderFrame” hook @ `0x11E0F0` | **0 hits** — site is a tail (`call` + `jmp [rip+disp]`), not frame entry |

**Ghidra:** Decompile **`0x1400BE0F0`** (main game: init + frame loop). Focus region **`0xBEA80`–`0xBECE7`** (swap @ `0xBEAF0`, loop back @ `0xBECE7`).

**x64dbg:** Break `Horsey.exe+BEAF0` or `+1238D0` (`SDL_GL_SwapWindow` export).

## 5. Main loop (updated)

`0x21EE12` is the **return address** after `call 0xBE0F0` at `0x21EE0D` (CRT → game). The **per-frame loop runs inside `0xBE0F0`**, not via a separate `call` to `0x11E0F0`.

**Ghidra:** Xref export `SDL_GL_SwapWindow` — should show caller @ **`0xBEAF0`** (also @ `0xC019E` per static PE scan).

## 6. Achievements

Strings:

- `got cheevo: %s` @ `0x25D928`
- `Cheevo %s not found!` @ `0x25D910`

**Ghidra:** Find xrefs → locate `SetAchievement` / stats usage on `STEAMUSERSTATS` interface.

## 7. Save writer

| Item | RVA / path |
|------|------------|
| `Save_Write` | `0x6DAB0` |
| Callers | `0x9828C`, `0x10A2C2`, `0x10A822` |
| Callee candidates | `0x88000` (format), `0x6F3C0` (write) |
| Live save file | `Game/save/save1.dat` — probe: `probe_save_format.py` |
| Path strings | Cluster ~`0x263830` (`save`, `.dat`) — no `save1.dat` literal |

**Frida:** `frida_save.py` while triggering save in UI.

## 8. Fonts (`.crf` + `n64.fnt`)

| String | RVA |
|--------|-----|
| `quip.crf` | `0x980DE` |
| `n64.fnt` | `0x2658A8` |
| `n64_0.png` | `0x265A80` |
| `genes.xml` | `0x266130` (xref data) |

**Static:** `crf_font.py`, `crf_opcode_trace.py`, `bmf_binary.py`.  
**Ghidra:** Xref each string → loader; decompile; compare to `analysis/crf_opcode_trace.json`.

## 9. Capstone disassembly dumps

```bat
python RE_Tools\tools\scripts\disasm_phase1.py
python RE_Tools\tools\scripts\phase1_string_xrefs.py
python RE_Tools\tools\scripts\phase1_pointer_xrefs.py
```

Output: `analysis/disasm_phase1.txt`, `phase1_string_xrefs.json`, `phase1_pointer_xrefs.json`.

## 10. Master exe notes

See [Phase1_Exe_Notes.md](Phase1_Exe_Notes.md).

## Deliverables back to HorseSDK

Paste decompiler output or notes for any confirmed function into `RE_Tools/docs/ReverseEngineeringProgress.md` under a new `[KNOWLEDGE UPDATE]` block with:

- Symbol name (your label)
- RVA
- One-line purpose
- Key callees / strings
