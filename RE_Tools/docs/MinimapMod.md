# Minimap mod

**Mod:** `mods/minimap_mod.dll`  
**SDK:** [`horse_map.h`](../../SDK/include/horse/horse_map.h)  
**Map file:** `Game/data/horsey.tmx` (400×225, not in save blob — [SaveLoadPath.md](SaveLoadPath.md))

## Usage

1. Deploy with `deploy_modloader.py` (copies `minimap_mod.dll`).
2. In `HorseModLoader.ini`:

```ini
mods_order=example_mod.dll,minimap_mod.dll
```

3. Inject → in-game press **M** to toggle map window. **Esc** closes.
4. If **M** does nothing, type **`map`** in the mod-loader debug console.

### Map window controls (v0.2.1)

| Input | Action |
|-------|--------|
| **Mouse wheel** | Zoom in/out at cursor |
| **+** / **-** | Zoom at center |
| **Left-drag** | Pan |
| **Arrow keys** | Pan |
| **R** | Reset zoom (fit whole map) |
| **Esc** | Close window |

## How it works

| Piece | Source |
|-------|--------|
| **M key** | Hook `Game_DispatchSdlEvent` @ `0xC0430` ([Game_DispatchSdlEvent.md](Game_DispatchSdlEvent.md)) |
| **Map image** | `horsey.tmx` + `terrain.xml`/`terrain.png` + `locs.xml`/`locs.png` ([`DataFileFormats.md`](DataFileFormats.md)) |
| **Player dot** | Live: `g_save_context` @ **`0x31A660`** → `[ctx+0x300]+0x28` or `ctx+0x394` — [MapViewPosition.md](MapViewPosition.md) |
| **Draw** | Topmost Win32 window + GDI `StretchDIBits` |

## Atlas rendering (v0.2.0)

GID → sprite via Tiled `firstgid` + atlas XML order (same as `map_tile_gids.py`):

- `terrain.tsx` (firstgid **1**) → `terrain.xml` + `terrain.png`
- `locs.tsx` (firstgid **97**) → `locs.xml` + `locs.png`

Loader: `horse_data_png_load_rgba` (stb_image) in `horse_data`.

## Player position

See **[MapViewPosition.md](MapViewPosition.md)** for pinned RVAs and offsets.

**RE tool:** `python RE_Tools/tools/scripts/frida_map_view_probe.py --attach --seconds 60`

## Current look (v0.2.0, May 2026)

Atlas path is live: `terrain.png` + `locs.png` blitted per GID (`map_atlas.c`). You should see:

- Yellow **Plain** / **CactusLand** terrain, green **GrassLand** patches, blue **Water** / **Pond**
- Brown/pink **Road** / fence lines on the west side
- Cream **locs** blocks (stable, shops) and the pink-bordered central plot from `horsey.tmx`
- Dark dotted **void** outside the island (unpainted raster / low GID background)
- Top-left **Loc** sprite icon; red **player dot** when `horse_map_read_view` finds valid coords

If the map still looks like solid hash colors, check `Game\data\terrain.png` and `locs.png` exist after deploy.

**Live dot:** blocked on RE — see [MapViewPosition.md](MapViewPosition.md) (Frida probe pinned).

## Roadmap

- [ ] **Live player dot** — find per-frame XY (Frida scan; `+0x394` static in probe)
- [ ] Corner minimap (`overlay=2` or child HUD)
- [x] Pin `g_save_context` @ `0x31A660` (global; pan offset TBD)
- [x] Tile colors from texture atlas
