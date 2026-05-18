# Mods directory

Place mod DLLs here (next to `HorseModLoader.dll` after deploy).

Each mod must export:

- `HorseMod_GetInfo`
- `HorseMod_Init`
- `HorseMod_Shutdown` (optional but recommended)

See `example_mod/` and `SDK/include/horse/mod_api.h`.

## Shipped mods

| DLL | Purpose | Doc |
|-----|---------|-----|
| `example_mod.dll` | GainMoney / SpendMoney hooks, logging | [ModLoaderSmokeTest.md](../../RE_Tools/docs/ModLoaderSmokeTest.md) |
| `minimap_mod.dll` | Atlas map from `data/horsey.tmx`, **M** or console **`map`** | [MinimapMod.md](../../RE_Tools/docs/MinimapMod.md) |
| `race_predictor_mod.dll` | Pre-race ranking from `HorseRaceScore` power, **P** re-print | [RacePredictorMod.md](../../RE_Tools/docs/RacePredictorMod.md) |

Enable in `HorseModLoader.ini`:

```ini
mods_order=example_mod.dll,minimap_mod.dll
```

## Build

```bat
cmake -S ModLoader -B build/modloader -DCMAKE_BUILD_TYPE=Release
cmake --build build/modloader --config Release
python RE_Tools\tools\scripts\deploy_modloader.py
```

## Inject

1. Start `Game\Horsey.exe` (windowed).
2. Run `Game\horse_inject.exe`.
3. Alt-tab to **Horsey Mod Loader** console.
4. For map: focus game farm view, press **M**, or type **`map`** in the loader console.
