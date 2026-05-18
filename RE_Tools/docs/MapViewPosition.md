# Minimap player / camera position

**Game:** `Horsey.exe`  
**API:** [`horse/horse_map.h`](../../SDK/include/horse/horse_map.h) — implemented in **`SDK/src/horse_map.c`** (`libhorse_sdk`, `HORSE_SDK_BUILD_DATA=ON`)  
**Consumer:** `minimap_mod` v0.2.1+ (hooks + window only)

**Status:** `g_save_context` **confirmed** · live pan offset **open** (Frida pinned below)

> **Pinned for later:** finish live dot RE before changing `horse_map_read_view` offsets.

## Active save context global

| RVA | Name | Evidence |
|-----|------|----------|
| **`0x31A660`** | `g_save_context` | `mov [rip+0x216aed], rax` @ **`0x103B6C`** before `Save_Load` (`rcx=rbx` save ctx, alloc `0x268` @ `0x103B51`) |

```c
void *ctx = horse_map_get_save_context(horse_module_base(0));
/* or */
void *ctx = *(void **)((uint8_t *)horse_module_base(0) + HORSE_RVA_g_save_context);
```

Catalog: `HORSE_RVA_g_save_context` in [`game_functions.h`](../../SDK/include/horse/game_functions.h) · umbrella [`sdk.h`](../../SDK/include/horse/sdk.h).

**Note:** Ghidra also labels `DAT_14031a660` for footer nested I/O in `Save_Write` @ `0x6E103`; on the load UI path above the qword holds the **heap save context** pointer.

## Position fields (on save context)

| Offset | Role | Evidence |
|--------|------|----------|
| **`+0x300`** | Pointer to active horse / world object | [`SaveGhidraCrossref.md`](SaveGhidraCrossref.md) — **Frida: invalid ptr in farm** (see below) |
| **`+0x28`** (on `+0x300` object) | View XY (load copy target) | `mov [rcx+0x28], eax` @ **`0x6EA90`** |
| **`+0x394` / `+0x398`** | Footer camera floats | `movss [rsi+0x394]` @ **`0x6EA57`** — **Frida: static (18, 24) while panning** |

**Not used for dot:** `+0x39C` — save serialize field (`WriteString` @ `0x6DD61` / ambiguous trace); **not** live world XY.

## SDK API (`horse_map_read_view`)

Priority order in `SDK/src/horse_map.c`:

1. `save_ctx_hint`, else `*(base + 0x31A660)`
2. `[ctx+0x300]+0x28` if pointer and floats valid → `HorseMapView.source = 1`
3. Else `ctx+0x394` / `+0x398` → `source = 2`

Returns `0` if no valid coords. Use `horse_map_world_to_tile()` with a loaded `HorseDataTmxMap` for tile indices.

## minimap_mod hooks

| Hook | Role |
|------|------|
| `Game_UpdateWorld` @ `0x87510` | Refresh dot every 4th tick while map visible |
| `Save_Write` @ `0x6DAB0` | Cache `rcx` as `save_ctx_hint` |

## Verify (Frida)

```bat
python RE_Tools\tools\scripts\frida_map_view_probe.py --attach --seconds 45
```

Pan/drag the **farm** for the full window; inspect [`map_view_probe.json`](../analysis/map_view_probe.json).

### Pinned probe result (farm, 45 s, May 2026)

| Sample | Result |
|--------|--------|
| `ctx` @ `0x31A660` | Stable heap ptr — **OK** |
| `cam394` / `cam398` | **(18, 24)** all samples — **no pan tracking** |
| `[ctx+0x300]` | Garbage qword — `horse28_x/y` null |

**Next (later):** re-probe while moving; scan `ctx+0x0..0x500` for moving floats; tie to `Game_UpdateWorld` tables @ `0x312830` ([Game_UpdateWorld.md](Game_UpdateWorld.md)).

## World → tile

TMX **400×225**, tiles **32×32** px ([`DataFileFormats.md`](DataFileFormats.md)):

`tile_x = (int)(world_x / 32)`, `tile_y = (int)(world_y / 32)`

Footer sample camera `(4240, 4016)` → ~(132, 125) tiles.
