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

## How it works

| Piece | Source |
|-------|--------|
| **M key** | Hook `Game_DispatchSdlEvent` @ `0xC0430` — SDL_KEYDOWN scancode **39** ([Game_DispatchSdlEvent.md](Game_DispatchSdlEvent.md)) |
| **Map image** | `horse_data_tmx_load_file` → rasterize GIDs ([`tmx_map.h`](../../RE_Tools/src/horse_data/include/horse_data/tmx_map.h)) |
| **Player dot** | Save context `rcx` from `GainMoney` @ `0x10AB80`; vec2 @ **`ctx+0x39C`** ([`SaveContext.h`](SaveContext.h)) |
| **Draw** | Topmost Win32 window + GDI `StretchDIBits` |

## Player position (best-effort)

The dot uses **`[save_ctx+0x39C]`** (same layout as `WriteVec2F32` @ `0x6DD61`). This updates when the game touches that context (e.g. after money events). **Live panning may lag** until RE pins the per-frame camera.

**RE tool:** `python RE_Tools/tools/scripts/frida_map_view_probe.py --attach --seconds 60` — pan the farm; inspect `map_view_probe.json`.

## Roadmap

- [ ] Corner minimap (`overlay=2` or child HUD)
- [ ] Pin live camera globals (Frida + doc offset)
- [ ] Tile colors from texture atlas instead of GID hash
