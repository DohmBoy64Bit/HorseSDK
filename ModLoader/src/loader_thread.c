#define WIN32_LEAN_AND_MEAN
#include "mod_loader.h"

#include "async_log.h"
#include "debug_console.h"
#include "hook_manager.h"
#include "loader_config.h"
#include "overlay.h"

#include <horse/hook.h>
#include <horse/module.h>
#include <stdio.h>
#include <windows.h>

static LoaderConfig g_cfg;

static DWORD WINAPI loader_main_thread(LPVOID param)
{
    HMODULE self = (HMODULE)param;
    char dir[MAX_PATH];
    char ini[MAX_PATH];

    GetModuleFileNameA(self, dir, MAX_PATH);
    char *slash = strrchr(dir, '\\');
    if (slash) {
        *slash = '\0';
    }
    snprintf(ini, sizeof(ini), "%s\\HorseModLoader.ini", dir);
    loader_config_load(ini, &g_cfg);

    horse_hook_system_init();
    horse_async_log_start();

    if (g_cfg.console) {
        horse_debug_console_open("Horsey Mod Loader");
    }
    if (g_cfg.overlay == 2) {
        horse_overlay_start_mode(2);
    } else if (g_cfg.overlay == 1) {
        horse_overlay_start_mode(1);
    }

    horse_mod_loader_init(self, &g_cfg);
    horse_hook_manager_init(horse_module_base(0));

    if (g_cfg.auto_hook_gain) {
        horse_hook_manager_apply_list("GainMoney,SpendMoney");
    }
    if (g_cfg.auto_hooks[0]) {
        horse_hook_manager_apply_list(g_cfg.auto_hooks);
    }

    if (g_cfg.console) {
        horse_debug_console_start_input_thread();
    }
    return 0;
}

void horse_mod_loader_start_async(HMODULE self)
{
    HANDLE th = CreateThread(NULL, 0, loader_main_thread, self, 0, NULL);
    if (th) {
        CloseHandle(th);
    }
}
