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

#define SDL_EVENT_KEYDOWN 0x300u
#define SDL_SCANCODE_M 39

static HorseModHost g_host;
static HorseHookSlot g_sdl_slot;
static HorseHookSlot g_gain_slot;
static HORSE_FN_Game_DispatchSdlEvent g_orig_sdl;
static HORSE_FN_GainMoney g_orig_gain;
static void *g_save_ctx;
static char g_tmx_path[MAX_PATH];
static char g_game_dir[MAX_PATH];

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

static void refresh_view(void)
{
    HorseMapView v;
    if (horse_map_read_view_from_save_ctx(g_save_ctx, &v)) {
        map_window_set_view(&v);
    }
}

static void detour_sdl(void *ctx, void *sdl_event)
{
    if (sdl_event != NULL) {
        uint32_t type = *(const uint32_t *)sdl_event;
        if (type == SDL_EVENT_KEYDOWN) {
            const unsigned char *ev = (const unsigned char *)sdl_event;
            unsigned char repeat = ev[13];
            int scancode = *(const int *)(ev + 16);
            if (!repeat && scancode == SDL_SCANCODE_M) {
                map_window_toggle(NULL, g_tmx_path);
                refresh_view();
                mod_logf("minimap: toggled map (M)");
            }
        }
    }
    if (g_orig_sdl) {
        g_orig_sdl(ctx, sdl_event);
    }
}

static void detour_gain(void *ctx, int amount, char show_ui)
{
    if (ctx) {
        g_save_ctx = ctx;
    }
    if (g_orig_gain) {
        g_orig_gain(ctx, amount, show_ui);
    }
    if (map_window_is_visible()) {
        refresh_view();
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
    strncpy(g_game_dir, exe, sizeof(g_game_dir) - 1);
    snprintf(g_tmx_path, sizeof(g_tmx_path), "%s\\data\\horsey.tmx", g_game_dir);
}

HORSE_MOD_API const HorseModInfo *HorseMod_GetInfo(void)
{
    static const HorseModInfo info = {
        HORSE_MOD_API_VERSION,
        "minimap_mod",
        "Minimap Mod",
        "0.1.0",
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
        mod_logf("minimap: missing %s", g_tmx_path);
    }

    if (!map_window_start()) {
        mod_logf("minimap: map window thread failed");
        return -1;
    }

    horse_hook_slot_init(&g_sdl_slot, g_host.game_base, HORSE_RVA_Game_DispatchSdlEvent, (void *)detour_sdl);
    if (g_host.hook_install(&g_sdl_slot) != HORSE_HOOK_OK) {
        mod_logf("minimap: Game_DispatchSdlEvent hook failed");
        return -1;
    }
    g_orig_sdl = (HORSE_FN_Game_DispatchSdlEvent)g_sdl_slot.trampoline;

    horse_hook_slot_init(&g_gain_slot, g_host.game_base, HORSE_RVA_GainMoney, (void *)detour_gain);
    if (g_host.hook_install(&g_gain_slot) == HORSE_HOOK_OK) {
        g_orig_gain = (HORSE_FN_GainMoney)g_gain_slot.trampoline;
    }

    mod_logf("minimap: ready — press M for map (Esc close). tmx=%s", g_tmx_path);
    mod_logf("minimap: player dot uses save ctx+0x39C (best-effort; see MinimapMod.md)");
    return 0;
}

HORSE_MOD_API void HorseMod_Shutdown(void)
{
    if (g_host.hook_remove) {
        if (g_sdl_slot.trampoline) {
            g_host.hook_remove(&g_sdl_slot);
        }
        if (g_gain_slot.trampoline) {
            g_host.hook_remove(&g_gain_slot);
        }
    }
    map_window_stop();
    mod_logf("minimap_mod shutdown");
}
