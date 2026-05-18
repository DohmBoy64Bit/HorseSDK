# Mods directory

Place mod DLLs here (next to `HorseModLoader.dll` after deploy).

Each mod must export:

- `HorseMod_GetInfo`
- `HorseMod_Init`
- `HorseMod_Shutdown` (optional but recommended)

See `example_mod/` and `SDK/include/horse/mod_api.h`.

Build example:

```bat
cmake --build build/modloader --config Release
copy build\modloader\mods\Release\example_mod.dll build\modloader\Release\mods\
```

Inject (start game first, then alt-tab to **Horsey Mod Loader** console on the game):

```bat
build\modloader\Release\horse_inject.exe
```
