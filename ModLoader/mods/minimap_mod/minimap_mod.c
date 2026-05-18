#define HORSE_MOD_BUILD
#define WIN32_LEAN_AND_MEAN

#include <horse/game_function_types.h>
#include <horse/game_functions.h>
#include <horse/horse_map.h>
#include <horse/mod_api.h>

#include "map_window.h"

#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <windows.h>

/* SDL2 keyboard event — Game_DispatchSdlEvent @ 0xC0430 */
#define SDL_EVENT_KEYDOWN 0x300u
#define SDL_SCANCODE_M 39
#define SDLK_M 109

static HorseModHost g_host;
static HorseHookSlot g_sdl_slot;
static HorseHookSlot g_world_slot;
static HorseHookSlot g_save_slot;
static HORSE_FN_Game_DispatchSdlEvent g_orig_sdl;
static HORSE_FN_Game_UpdateWorld g_orig_world;
static HORSE_FN_Save_Write g_orig_save;
static void *g_save_ctx;
static int g_sdl_seen;
static int g_world_ticks;
static char g_tmx_path[MAX_PATH];
static int g_debug_keys_left = 4;

static void mod_logf(const char *fmt, ...)
{
    char buf[512];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    if (g_host.log) {
        g_host.log(buf);
    }
}

static int is_m_key(const unsigned char *ev)
{
    if (ev[13] != 0) {
        return 0;
    }
    int scancode = *(const int *)(ev + 0x10);
    int sym = *(const int *)(ev + 0x14);
    if (scancode == SDL_SCANCODE_M || sym == SDLK_M || sym == 'm' || sym == 'M') {
        return 1;
    }
    return 0;
}

static void refresh_view(void)
{
    HorseMapView v;
    if (horse_map_read_view(g_host.game_base, g_save_ctx, &v)) {
        map_window_set_view(&v);
    }
}

static void detour_save_write(void *ctx)
{
    g_save_ctx = ctx;
    if (g_orig_save) {
        g_orig_save(ctx);
    }
}

static void detour_world(int year_or_frame)
{
    g_world_ticks++;
    if ((g_world_ticks & 3) == 0) {
        if (map_window_is_visible()) {
            refresh_view();
        }
    }
    if (g_orig_world) {
        g_orig_world(year_or_frame);
    }
}

static void detour_sdl(void *ctx, void *sdl_event)
{
    if (sdl_event != NULL) {
        uint32_t type = *(const uint32_t *)sdl_event;
        const unsigned char *ev = (const unsigned char *)sdl_event;
        if (!g_sdl_seen) {
            g_sdl_seen = 1;
            mod_logf("minimap: SDL hook active (first ev type=0x%X)", (unsigned)type);
        }
        if (type == SDL_EVENT_KEYDOWN) {
            if (g_debug_keys_left > 0) {
                g_debug_keys_left--;
                mod_logf("minimap: KEYDOWN scan=%d sym=%d (M=39/109)",
                         *(const int *)(ev + 0x10),
                         *(const int *)(ev + 0x14));
            }
            if (is_m_key(ev)) {
                map_window_toggle(NULL, g_tmx_path);
                refresh_view();
                mod_logf("minimap: map toggle sent (M)");
            }
        }
    }
    if (g_orig_sdl) {
        g_orig_sdl(ctx, sdl_event);
    }
}

static void resolve_paths(void)
{
    char exe[MAX_PATH];
    GetModuleFileNameA(NULL, exe, MAX_PATH);
    char *slash = strrchr(exe, '\\');
    if (slash) {
        *slash = '\0';
    }
    snprintf(g_tmx_path, sizeof(g_tmx_path), "%s\\data\\horsey.tmx", exe);
}

HORSE_MOD_API const HorseModInfo *HorseMod_GetInfo(void)
{
    static const HorseModInfo info = {
        HORSE_MOD_API_VERSION,
        "minimap_mod",
        "Minimap Mod",
        "0.2.1",
    };
    return &info;
}

HORSE_MOD_API int HorseMod_Init(const HorseModHost *host)
{
    if (host == NULL || host->api_version != HORSE_MOD_API_VERSION) {
        return -1;
    }
    g_host = *host;
    if (g_host.game_base == NULL || g_host.hook_install == NULL) {
        return -1;
    }

    resolve_paths();
    if (GetFileAttributesA(g_tmx_path) == INVALID_FILE_ATTRIBUTES) {
        mod_logf("minimap: WARN missing %s", g_tmx_path);
    } else {
        mod_logf("minimap: tmx OK %s", g_tmx_path);
    }

    if (!map_window_start()) {
        mod_logf("minimap: map window thread failed");
        return -1;
    }

    horse_hook_slot_init(&g_sdl_slot, g_host.game_base, HORSE_RVA_Game_DispatchSdlEvent, (void *)detour_sdl);
    if (g_host.hook_install(&g_sdl_slot) != HORSE_HOOK_OK) {
        mod_logf("minimap: Game_DispatchSdlEvent hook FAILED");
        return -1;
    }
    g_orig_sdl = (HORSE_FN_Game_DispatchSdlEvent)g_sdl_slot.trampoline;

    horse_hook_slot_init(&g_world_slot, g_host.game_base, HORSE_RVA_Game_UpdateWorld, (void *)detour_world);
    if (g_host.hook_install(&g_world_slot) == HORSE_HOOK_OK) {
        g_orig_world = (HORSE_FN_Game_UpdateWorld)g_world_slot.trampoline;
        mod_logf("minimap: Game_UpdateWorld hook OK (live dot @ g_save+0x300/0x394)");
    } else {
        mod_logf("minimap: Game_UpdateWorld hook skipped");
    }

    horse_hook_slot_init(&g_save_slot, g_host.game_base, HORSE_RVA_Save_Write, (void *)detour_save_write);
    if (g_host.hook_install(&g_save_slot) == HORSE_HOOK_OK) {
        g_orig_save = (HORSE_FN_Save_Write)g_save_slot.trampoline;
    }

    mod_logf("minimap: v0.2.1 wheel zoom, drag pan, R=fit, arrows pan");
    return 0;
}

HORSE_MOD_API void HorseMod_MapToggle(void)
{
    map_window_toggle(NULL, g_tmx_path);
    refresh_view();
    mod_logf("minimap: MapToggle() from export");
}

HORSE_MOD_API void HorseMod_Shutdown(void)
{
    if (g_host.hook_remove) {
        if (g_save_slot.trampoline) {
            g_host.hook_remove(&g_save_slot);
        }
        if (g_world_slot.trampoline) {
            g_host.hook_remove(&g_world_slot);
        }
        if (g_sdl_slot.trampoline) {
            g_host.hook_remove(&g_sdl_slot);
        }
    }
    map_window_stop();
    mod_logf("minimap_mod shutdown");
}
