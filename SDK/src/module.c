/**
 * Horsey.exe module resolution (Windows).
 */
#include "horse/module.h"

#if defined(_WIN32)

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

static const void *g_cached_base;

const void *horse_module_base(int force_refresh)
{
    if (force_refresh) {
        g_cached_base = NULL;
    }
    if (g_cached_base != NULL) {
        return g_cached_base;
    }
    HMODULE mod = GetModuleHandleA(HORSE_MODULE_NAME);
    if (mod == NULL) {
        return NULL;
    }
    g_cached_base = (const void *)mod;
    return g_cached_base;
}

#else

const void *horse_module_base(int force_refresh)
{
    (void)force_refresh;
    return NULL;
}

#endif

void *horse_module_rva(const void *module_base, uint32_t rva)
{
    if (module_base == NULL) {
        return NULL;
    }
    return (uint8_t *)module_base + rva;
}

void *horse_resolve(uint32_t rva)
{
    return horse_module_rva(horse_module_base(0), rva);
}
