# Source of truth policy

## Repomix (`repomix-output-DohmBoy64Bit-Horsey-Game.xml`)

**Not authoritative.** Use it only as a pointer to prior notes, scripts, and hypotheses.

- RVAs, function names, save layouts, and format descriptions inside repomix may be wrong or from an older build.
- **Do not implement SDK features from repomix alone.**
- Every claim must be re-verified on the current `Game/Horsey.exe` and `Game/data/` (PE scan, Frida, parsers, hex dumps, Ghidra).

When repomix and live verification disagree, **live verification wins**.

## Authoritative inputs (in order)

| Priority | Source |
|----------|--------|
| 1 | `Game/Horsey.exe` + runtime (Frida, x64dbg) |
| 2 | `Game/data/` and `Game/save/` files parsed/measured in this repo |
| 3 | `RE_Tools/analysis/*` generated reports (`phase1_verify.txt`, `data_inventory.json`, etc.) |
| 4 | Repomix / external notes (reference only) |

Document confirmed facts in `ReverseEngineeringProgress.md` under `[KNOWLEDGE UPDATE]` with the verification method named.
