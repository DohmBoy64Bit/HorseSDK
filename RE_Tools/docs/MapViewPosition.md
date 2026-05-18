# Minimap player / camera position

**Game:** `Horsey.exe` · **Mod:** `minimap_mod` v0.2.0+  
**Status:** `g_save_context` **confirmed** · live pan offset **open** (see Frida below)

> **Pinned for later:** finish live dot RE before changing `horse_map_read_view` offsets again.

## Active save context global

| RVA | Name | Evidence |
|-----|------|----------|
| **`0x31A660`** | `g_save_context` | `mov [rip+0x216aed], rax` @ **`0x103B6C`** before `Save_Load` (`rcx=rbx` save ctx, alloc `0x268` @ `0x103B51`) |

Read each frame:

```c
void *ctx = *(void **)((uint8_t *)horse_module_base(0) + 0x31A660);
```

Catalog: `HORSE_RVA_g_save_context` in [`game_functions.h`](../../SDK/include/horse/game_functions.h).

**Note:** Same symbol is used as the footer nested object in `Save_Write` @ `0x6E103`; at runtime the qword holds the **heap save context** allocated in the load UI path above.

## Position fields (on save context)

| Offset | Role | Evidence |
|--------|------|----------|
| **`+0x300`** | Pointer to active horse / world object (static RE) | [`SaveGhidraCrossref.md`](SaveGhidraCrossref.md) — **Frida: not a valid ptr in farm** (see below) |
| **`+0x28`** (on `+0x300` object) | View XY copy target on **load** | `mov [rcx+0x28], eax` @ **`0x6EA90`** — unreadable when `+0x300` bad |
| **`+0x394` / `+0x398`** | Footer camera floats (load path) | `movss [rsi+0x394]` @ **`0x6EA57`** — **Frida: static (18, 24) while panning** |

**Not used for dot:** `+0x39C` is a serialized blob field (`WriteString` / vec2 trace ambiguity) — do not read as live XY.

## Mod implementation

[`horse_map_read_view`](../../SDK/include/horse/horse_map.h):

1. `g_save_context` from `game_base + 0x31A660`
2. `[ctx+0x300]+0x28` if valid floats
3. Else `ctx+0x394` / `+0x398`

**Hooks:**

- `Game_UpdateWorld` @ `0x87510` — refresh dot while map visible (every 4th tick)
- `Save_Write` @ `0x6DAB0` — cache `rcx` as fallback hint

## Verify in-game

```bat
python RE_Tools\tools\scripts\frida_map_view_probe.py --attach --seconds 45
```

Pan the farm; inspect `RE_Tools/analysis/map_view_probe.json`.

### Frida probe result (pinned — farm view, 45 s)

**Artifact:** [`map_view_probe.json`](../analysis/map_view_probe.json) · script: `frida_map_view_probe.py`

| Sample | Result |
|--------|--------|
| `ctx` @ `0x31A660` | Stable heap ptr (e.g. `0x26e4f331e30`) — **OK** |
| `cam394` / `cam398` | **(18, 24)** all 112 samples — **does not track pan** |
| `[ctx+0x300]` | `0xc1900000c1900000` — **invalid**; `horse28_x/y` null |

**Conclusion:** Current mod dot uses best-effort `+0x394` or broken `+0x300` path — expect **fixed or missing dot** until RE finds moving floats.

**Next (later):**

1. Re-run probe while **dragging map the whole 45 s**.
2. Frida scan `ctx+0x0..0x500` for `float` pairs that change with pan.
3. Correlate with `Game_UpdateWorld` table writes @ `0x312830` ([`Game_UpdateWorld.md`](Game_UpdateWorld.md)).

## World → tile

TMX **400×225**, tiles **32×32** px ([`DataFileFormats.md`](DataFileFormats.md)):

`tile_x = world_x / 32`, `tile_y = world_y / 32`

Footer sample camera `(4240, 4016)` → tile ~(132, 125) on `horsey.tmx`.
