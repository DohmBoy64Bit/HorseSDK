#include "mod_loader.h"

#include <windows.h>

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID reserved)
{
    (void)reserved;
    switch (reason) {
    case DLL_PROCESS_ATTACH:
        DisableThreadLibraryCalls(inst);
        horse_mod_loader_init(inst);
        break;
    case DLL_PROCESS_DETACH:
        horse_mod_loader_shutdown();
        break;
    default:
        break;
    }
    return TRUE;
}
