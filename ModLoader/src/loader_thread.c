#define WIN32_LEAN_AND_MEAN
#include "mod_loader.h"

#include "debug_console.h"

#include <windows.h>

static DWORD WINAPI loader_main_thread(LPVOID param)
{
    HMODULE self = (HMODULE)param;
    horse_debug_console_open("Horsey Mod Loader");
    horse_mod_loader_init(self);
    horse_debug_console_start_input_thread();
    return 0;
}

void horse_mod_loader_start_async(HMODULE self)
{
    HANDLE th = CreateThread(NULL, 0, loader_main_thread, self, 0, NULL);
    if (th) {
        CloseHandle(th);
    }
}
