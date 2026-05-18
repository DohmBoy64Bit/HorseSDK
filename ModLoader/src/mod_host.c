#include "mod_loader.h"

#include <horse/mod_api.h>
#include <stdio.h>
#include <string.h>

#define MOD_DIR_MAX 512
#define MOD_MAX 32

typedef struct LoadedMod {
    HMODULE dll;
    HorseModInitFn init;
    HorseModShutdownFn shutdown;
    char path[MAX_PATH];
} LoadedMod;

static LoadedMod g_mods[MOD_MAX];
static uint32_t g_mod_count;
static HorseModHost g_host;
static HMODULE g_self;
static void mod_log(const char *msg)
{
    OutputDebugStringA("[HorseModLoader] ");
    OutputDebugStringA(msg);
    OutputDebugStringA("\n");
}

static void *host_resolve(uint32_t rva)
{
    return horse_resolve(rva);
}

static void scan_and_load(const char *mods_dir)
{
    char pattern[MAX_PATH];
    snprintf(pattern, sizeof(pattern), "%s\\*.dll", mods_dir);
    WIN32_FIND_DATAA fd;
    HANDLE h = FindFirstFileA(pattern, &fd);
    if (h == INVALID_HANDLE_VALUE) {
        return;
    }
    do {
        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            continue;
        }
        if (_stricmp(fd.cFileName, "HorseModLoader.dll") == 0) {
            continue;
        }
        if (g_mod_count >= MOD_MAX) {
            break;
        }
        char full[MAX_PATH];
        snprintf(full, sizeof(full), "%s\\%s", mods_dir, fd.cFileName);
        HMODULE mod = LoadLibraryA(full);
        if (mod == NULL) {
            mod_log("LoadLibrary failed");
            continue;
        }
        HorseModGetInfoFn get_info =
            (HorseModGetInfoFn)GetProcAddress(mod, "HorseMod_GetInfo");
        HorseModInitFn init_fn = (HorseModInitFn)GetProcAddress(mod, "HorseMod_Init");
        HorseModShutdownFn shutdown_fn =
            (HorseModShutdownFn)GetProcAddress(mod, "HorseMod_Shutdown");
        if (get_info == NULL || init_fn == NULL) {
            FreeLibrary(mod);
            continue;
        }
        const HorseModInfo *info = get_info();
        if (info == NULL || info->api_version != HORSE_MOD_API_VERSION) {
            FreeLibrary(mod);
            continue;
        }
        LoadedMod *L = &g_mods[g_mod_count++];
        L->dll = mod;
        L->init = init_fn;
        L->shutdown = shutdown_fn;
        strncpy(L->path, full, sizeof(L->path) - 1);
        if (init_fn(&g_host) != 0) {
            mod_log("HorseMod_Init failed");
            if (shutdown_fn) {
                shutdown_fn();
            }
            FreeLibrary(mod);
            g_mod_count--;
        } else {
            char buf[256];
            snprintf(buf, sizeof(buf), "Loaded mod: %s", info->name ? info->name : "?");
            mod_log(buf);
        }
    } while (FindNextFileA(h, &fd));
    FindClose(h);
}

void horse_mod_loader_init(HMODULE self)
{
    g_self = self;
    memset(&g_host, 0, sizeof(g_host));
    g_host.api_version = HORSE_MOD_API_VERSION;
    g_host.game_base = horse_module_base(0);
    g_host.resolve = host_resolve;
    g_host.hook_install = horse_hook_install;
    g_host.hook_remove = horse_hook_remove;
    g_host.log = mod_log;

    if (g_host.game_base == NULL) {
        mod_log("Horsey.exe base not found");
        return;
    }

    char dir[MAX_PATH];
    GetModuleFileNameA(self, dir, MAX_PATH);
    char *slash = strrchr(dir, '\\');
    if (slash) {
        *slash = '\0';
    }
    char mods_dir[MAX_PATH];
    snprintf(mods_dir, sizeof(mods_dir), "%s\\mods", dir);
    scan_and_load(mods_dir);
}

void horse_mod_loader_shutdown(void)
{
    while (g_mod_count > 0) {
        g_mod_count--;
        LoadedMod *L = &g_mods[g_mod_count];
        if (L->shutdown) {
            L->shutdown();
        }
        if (L->dll) {
            FreeLibrary(L->dll);
        }
        memset(L, 0, sizeof(*L));
    }
}
