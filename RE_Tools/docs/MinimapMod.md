# Minimap mod

**Status:** 2026-05-17 · **Mod version:** 0.2.1 · **Game:** `Horsey.exe`

| Artifact | Role |
|----------|------|
| **`mods/minimap_mod.dll`** | Hooks + Win32 map window (UI only) |
| **`libhorse_sdk`** | [`horse_map_*`](../../SDK/include/horse/horse_map.h) — TMX, save ctx, view XY |
| **`horse_data`** | TMX parse, PNG atlases (`png_rgba`), texture XML |
| **Map data** | `Game/data/horsey.tmx` (400×225 static layout — [SaveLoadPath.md](SaveLoadPath.md)) |

## What this is (and is not)

| Shows | Does not show |
|-------|----------------|
| Full **static** world from `horsey.tmx` + `terrain.png` / `locs.png` | Your **save** farm layout (fences, crops, placed objects) |
| Bird's-eye of the whole island | The same cropped view as in-game play |
| Atlas-colored tiles (real sprites per GID) | `treasuremap.png` menu art (different asset) |

Use **wheel zoom + drag pan** to inspect an area at closer scale.

## Usage

1. Deploy: `python RE_Tools/tools/scripts/deploy_modloader.py`
2. `HorseModLoader.ini`:

```ini
mods_order=example_mod.dll,minimap_mod.dll
```

3. Start game → `horse_inject.exe` → press **M** (farm view focused, not the loader console).
4. Fallback: type **`map`** in the **Horsey Mod Loader** console.

### Map window controls

| Input | Action |
|-------|--------|
| **Mouse wheel** | Zoom in/out at cursor |
| **+** / **-** | Zoom at center |
| **Left-drag** | Pan |
| **Arrow keys** | Pan |
| **R** | Fit whole map |
| **Esc** | Close window |

## Architecture

```
minimap_mod.dll
  minimap_mod.c     Game_DispatchSdlEvent (M), Game_UpdateWorld (dot refresh), Save_Write (ctx cache)
  map_window.c      Win32 thread, GDI paint, zoom/pan viewport
  map_atlas.c       GID → terrain/locs sprite blit
  map_raster.c      TMX layer → BGRA bitmap
  horse_sdk         horse_map_load_tmx, horse_map_read_view, horse_map_world_to_tile, …
  horse_data        horse_data_tmx_load_file, horse_data_png_load_rgba, horse_data_atlas_load_file
```

**Source files:** `ModLoader/mods/minimap_mod/`

## How it works

| Piece | Source |
|-------|--------|
| **M key** | Hook `Game_DispatchSdlEvent` @ `0xC0430` ([Game_DispatchSdlEvent.md](Game_DispatchSdlEvent.md)) |
| **Map image** | `horsey.tmx` tile GIDs → `terrain.xml`/`terrain.png`, `locs.xml`/`locs.png` ([DataFileFormats.md](DataFileFormats.md), `map_tile_gids.py`) |
| **Player dot** | SDK `horse_map_read_view()` — [MapViewPosition.md](MapViewPosition.md) |
| **Draw** | Topmost Win32 window + GDI `StretchDIBits` |

## Player position

See **[MapViewPosition.md](MapViewPosition.md)** (pinned RE; live pan XY still open).

```bat
python RE_Tools\tools\scripts\frida_map_view_probe.py --attach --seconds 45
```

## Building another map mod

Link `horse_sdk` (requires `HORSE_SDK_BUILD_DATA=ON` for `horse_map`). Example:

```c
#include <horse/sdk.h>

HorseMapView v;
if (horse_map_read_view(host->game_base, NULL, &v)) { /* dot at v.world_x/y */ }
```

Reference UI stays in `minimap_mod`; copy `map_atlas` / `map_raster` patterns if you need a custom window.

## Roadmap

**Pinned for later** (active work: race predictor mod):

- [ ] **Live player dot** — per-frame XY (Frida scan; `+0x394` static in probe)
- [ ] Save grid overlay on static TMX
- [ ] Corner HUD (`overlay=2` or ImGui — [ImGuiOverlay.md](ImGuiOverlay.md))
- [x] `horse_map` in **libhorse_sdk**
- [x] Atlas tiles (not GID hash colors)
- [x] Zoom / pan / fit (`R`)
- [x] `g_save_context` @ `0x31A660` (global; view offsets TBD)

## Related

- [ModCapabilities.md](ModCapabilities.md) · [ModLoaderSmokeTest.md](ModLoaderSmokeTest.md)
- [Phase4_ModLoader.md](Phase4_ModLoader.md) · [SDK/README.md](../../SDK/README.md)
