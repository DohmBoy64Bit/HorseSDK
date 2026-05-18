#include "mod_loader.h"

#include "async_log.h"
#include "debug_console.h"
#include "hook_manager.h"
#include "overlay.h"

#include <windows.h>

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID reserved)
{
    (void)reserved;
    switch (reason) {
    case DLL_PROCESS_ATTACH:
        DisableThreadLibraryCalls(inst);
        horse_mod_loader_start_async(inst);
        break;
    case DLL_PROCESS_DETACH:
        horse_mod_loader_shutdown();
        horse_hook_manager_shutdown();
        horse_async_log_stop();
        horse_overlay_stop();
        horse_debug_console_close();
        break;
    default:
        break;
    }
    return TRUE;
}
