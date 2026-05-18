# Ghidra decompiler exports (user-pasted)

Paste one file per function from Ghidra’s Decompiler window.

**Naming:** `<FunctionName>.c.txt` (e.g. `Game_DispatchSdlEvent.c.txt`)

**Template:** see [Ghidra_User_Tasks.md](../Ghidra_User_Tasks.md) § “Paste template”.

Files here are **optional** — the repo still has Capstone artifacts under `RE_Tools/analysis/` if this folder is empty.

After pasting, register the function in [GameFunctionCatalog.md](../GameFunctionCatalog.md) via `build_game_function_catalog.py` (add to seed or `RE_Tools/analysis/catalog_seed.json`).

### Automated export (gameplay)

```bat
REM From repo root — set GHIDRA_INSTALL first
RE_Tools\ghidra_scripts\run_export_gameplay.bat
```

Or in Ghidra GUI: **Script Manager** → `ExportGameplayDecompile.java` — see [ghidra_scripts/README.md](../../ghidra_scripts/README.md).

Expected files: `GainMoney.c.txt`, `SimSpawnDisk.c.txt`, `BuyItem.c.txt`, `RaceCluster.c.txt`.
