# RE_Tools — Phase 1

Scripts and docs for reverse engineering **Horsey Game** (`Game/Horsey.exe`).

## Quick commands

```bat
cd E:\games\HorseSDK

python RE_Tools\tools\scripts\inventory_data.py
python RE_Tools\tools\scripts\phase1_verify.py
python RE_Tools\tools\scripts\pe_recon.py Game\Horsey.exe
python RE_Tools\tools\scripts\frida_renderframe.py
python RE_Tools\tools\scripts\frida_gameloop.py --frames 4
python RE_Tools\tools\parsers\genes.py
```

Outputs: `RE_Tools/analysis/phase1_verify.txt`

## Docs

| File | Purpose |
|------|---------|
| `docs/SOURCES.md` | **Repomix is reference only — verification policy** |
| `docs/DataFileFormats.md` | **All `Game/data/` files (verified counts)** |
| `docs/Data/README.md` | Data docs index |
| `docs/ReverseEngineeringProgress.md` | Living RE log + checklist |
| `docs/Ghidra_Phase1.md` | Ghidra/x64dbg tasks with RVAs |
| `../steam_bypass/README.md` | Offline Steam stub |

## Layout

```
RE_Tools/
  analysis/          # generated reports
  docs/
  tools/
    core/paths.py    # Game/, data/, save/ paths
    scripts/         # pe_recon, phase1_verify
    parsers/         # XML/TMX parsers (expand in Phase 1)
```
