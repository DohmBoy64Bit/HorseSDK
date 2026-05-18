#include "mod_loader.h"

#include "debug_console.h"

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
        horse_debug_console_close();
        break;
    default:
        break;
    }
    return TRUE;
}
