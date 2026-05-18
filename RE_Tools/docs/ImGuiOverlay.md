# ImGui in-game overlay (optional build)

**Hook site (verified):** `Game_PostSwapHook` @ `0xBFFA0` — called from `GameMain` @ `0xBEB00` after `SDL_GL_SwapWindow` ([GameLoop.md](GameLoop.md)).

**Today:** use `overlay=2` in `HorseModLoader.ini` for a **GDI log panel** parented to the Horsey window (no ImGui dependency).

## Enable Dear ImGui (future / advanced)

```powershell
cd E:\games\HorseSDK
.\RE_Tools\tools\scripts\setup_imgui.ps1
cmake -S ModLoader -B build/modloader -DHORSE_ENABLE_IMGUI=ON
cmake --build build/modloader --config Release
```

Set `imgui=1` in `HorseModLoader.ini` (after `setup_imgui.ps1` adds support).

ImGui draws in `Game_PostSwapHook` before returning to the game loop — same frame as present.

## Related

- [Phase4_ModLoader.md](Phase4_ModLoader.md)
- [MinimapMod.md](MinimapMod.md) — today’s map is a **separate Win32 window** (`minimap_mod`), not an ImGui overlay
- Catalog: `Game_PostSwapHook` in `game_function_catalog.json`
