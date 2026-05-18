# Ghidra scripts (HorseSDK)

Scripts for **Ghidra 10+** (Java). Image base: **`0x140000000`**.

## ExportGameplayDecompile.java

Decompiles gameplay functions and writes `*.c.txt` to `RE_Tools/docs/ghidra_exports/`.

| Output file | Pin RVA | Function entry (typical) |
|-------------|---------|---------------------------|
| `GainMoney.c.txt` | `0x10AB80` | same — `GainMoney` |
| `SimSpawnDisk.c.txt` | `0x342F0` (string) | **`0x33A20`** — containing function |
| `BuyItem.c.txt` | `0x78B00` (string) | **`0x787D0`** |
| `RaceCluster.c.txt` | `0x90E00`–`0x92000` | Often **0 functions** (strings sit inside `0x8F2B0`) |
| `Race_91148.c.txt` / `RaceStateMachine.c.txt` | xrefs | **`0x8F2B0`** race FSM |

Pinned RVAs that land **inside** a function export the **containing** function (header shows real entry RVA).

### GUI (interactive)

**Use only** `E:\games\HorseSDK\RE_Tools\ghidra_scripts` as the script directory.

Do **not** put this script in `C:\Users\SeanS\ghidra_scripts` with other projects’ `.java` files (Polytoria, RecoverAPI, `d.py` renamed to `.java`, etc.). Ghidra compiles **every** `.java` in the directory; one broken file blocks all scripts.

1. Import `Game/Horsey.exe` → Analyze (default + Decompiler).
2. **Memory Map** → confirm image base `0x140000000`.
3. **Edit → Script Manager** → **Manage script directories** → add **only** `...\HorseSDK\RE_Tools\ghidra_scripts`.
4. Remove or disable `C:\Users\SeanS\ghidra_scripts` from the list (or fix/delete broken scripts there).
5. Run **ExportGameplayDecompile** — the file must be `ExportGameplayDecompile.java` (not `NewScript2.java`).
6. Output path: `E:\games\HorseSDK\RE_Tools\docs\ghidra_exports`

### Headless (batch)

Adjust `GHIDRA_INSTALL` and run from repo root:

```bat
set GHIDRA_INSTALL=C:\Program Files\Ghidra\ghidra_11.3_PUBLIC
set REPO=E:\games\HorseSDK

"%GHIDRA_INSTALL%\support\analyzeHeadless.bat" ^
  "%REPO%\ghidra_project" HorseSDK ^
  -import "%REPO%\Game\Horsey.exe" ^
  -overwrite ^
  -scriptPath "%REPO%\RE_Tools\ghidra_scripts" ^
  -postScript ExportGameplayDecompile.java "%REPO%\RE_Tools\docs\ghidra_exports"
```

First run creates the project under `ghidra_project/` (gitignored if you add it to `.gitignore`).

### After export

1. Commit new `ghidra_exports/*.c.txt` if decompilation looks correct.
2. Update `build_game_function_catalog.py` `decompile` paths for pinned names.
3. Note any renamed `FUN_140…` in [GameplayFunctions.md](../docs/GameplayFunctions.md).

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ExportGameplayDecompile not found` / class in `NewScript2.java` | Rename file to `ExportGameplayDecompile.java` or copy from repo; public class name must match filename |
| `6 files failing` / `d.java` / `RecoverAPI` | Remove other projects’ scripts from the script directory; use HorseSDK path only |
| `bad operand type Function for !createFunction` | Update script from repo (fixed: uses `CreateFunctionCmd`) |
| `decompiler.close()` (other scripts) | Use `decompiler.dispose()` — fix or remove `FindStateMachineDialogs.java` |
| `createFunction failed` | Go to VA `0x14010AB80`, press **F**, then re-run script |
| Empty `RaceCluster.c.txt` | Expected if no function **starts** in `0x90E00`–`0x92000`; use `Race_91148.c.txt` / `RaceStateMachine.c.txt` (`0x8F2B0`) |
| Wrong addresses | Set image base `0x140000000` in Memory Map |
