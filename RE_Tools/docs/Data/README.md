# `Game/data/` documentation index

All numbers must come from **`inventory_data.py`**, not repomix. Policy: [../SOURCES.md](../SOURCES.md).

## Master reference

- [../DataFileFormats.md](../DataFileFormats.md) — full format spec + verified counts  
- [../../analysis/data_inventory.json](../../analysis/data_inventory.json) — machine-readable per-file report  

## Regenerate

```bat
cd E:\games\HorseSDK
python RE_Tools\tools\scripts\inventory_data.py
python RE_Tools\tools\scripts\map_tile_gids.py
python RE_Tools\tools\scripts\analyze_crf.py
python RE_Tools\tools\scripts\xref_data_strings.py
python RE_Tools\tools\scripts\verify_sound_paths.py
python RE_Tools\tools\parsers\genes_dat.py
python RE_Tools\tools\parsers\bmf_binary.py
python RE_Tools\tools\parsers\crf_font.py
```

## Analysis outputs

| File | Script |
|------|--------|
| `analysis/data_inventory.json` | `inventory_data.py` |
| `analysis/tile_gid_map.json` | `map_tile_gids.py` |
| `analysis/crf_probe.json` | `analyze_crf.py` |
| `analysis/data_exe_xrefs.json` | `xref_data_strings.py` |
| `analysis/sound_path_verify.json` | `verify_sound_paths.py` |
| `analysis/crf_opcode_trace.json` | `crf_opcode_trace.py` |
| `analysis/save_format_probe.json` | `probe_save_format.py` |
| `analysis/disasm_phase1.txt` | `disasm_phase1.py` |
| `analysis/phase1_string_xrefs.json` | `phase1_string_xrefs.py` |
| `../SaveFormat.md` | save probe doc |
| `../Phase1_Exe_Notes.md` | exe RE summary |

## Parsers (`RE_Tools/tools/parsers/`)

| Module | Files |
|--------|--------|
| `texture_atlas.py` | `*xml` TextureAtlas |
| `tiled_map.py` | `horsey.tmx` |
| `genes.py` | `genes.xml`, `pop.xml` |
| `genes_dat.py` | `genes.dat` (name index) |
| `bmf_binary.py` | `n64.fnt` (BMF v3) |
| `crf_font.py` | `*.crf` compiled fonts |
| `sound.py` | `sound.xml` |
| `bmfont_txt.py` | `bubbletime.txt`, `classified.txt`, `picory.txt`, `softsquare.txt` |
