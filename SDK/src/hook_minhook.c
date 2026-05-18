/**
 * MinHook backend for horse_hook_install (Windows).
 */
#include "horse/hook.h"

#include <stdlib.h>
#include <string.h>

#if defined(_WIN32) && defined(HORSE_USE_MINHOOK)

#define WIN32_LEAN_AND_MEAN
#include <MinHook.h>
#include <windows.h>

static int g_mh_init;

int horse_hook_system_init(void)
{
    if (g_mh_init) {
        return 1;
    }
    MH_STATUS st = MH_Initialize();
    if (st != MH_OK && st != MH_ERROR_ALREADY_INITIALIZED) {
        return 0;
    }
    g_mh_init = 1;
    return 1;
}

void horse_hook_system_shutdown(void)
{
    if (!g_mh_init) {
        return;
    }
    MH_Uninitialize();
    g_mh_init = 0;
}

void horse_hook_slot_init(HorseHookSlot *slot, const void *module_base, uint32_t rva,
                          void *detour)
{
    if (slot == NULL) {
        return;
    }
    memset(slot, 0, sizeof(*slot));
    slot->target = horse_module_rva(module_base, rva);
    slot->detour = detour;
}

HorseHookStatus horse_hook_install(HorseHookSlot *slot)
{
    if (slot == NULL || slot->target == NULL || slot->detour == NULL) {
        return HORSE_HOOK_ERR_INVALID;
    }
    if (slot->trampoline != NULL) {
        return HORSE_HOOK_ERR_ALREADY;
    }
    if (!horse_hook_system_init()) {
        return HORSE_HOOK_ERR_PROTECT;
    }

    MH_STATUS st = MH_CreateHook(slot->target, slot->detour, &slot->trampoline);
    if (st != MH_OK) {
        return HORSE_HOOK_ERR_PROTECT;
    }
    st = MH_EnableHook(slot->target);
    if (st != MH_OK) {
        MH_RemoveHook(slot->target);
        slot->trampoline = NULL;
        return HORSE_HOOK_ERR_PROTECT;
    }
    slot->platform_data = slot->target;
    return HORSE_HOOK_OK;
}

HorseHookStatus horse_hook_remove(HorseHookSlot *slot)
{
    if (slot == NULL || slot->target == NULL || slot->trampoline == NULL) {
        return HORSE_HOOK_ERR_NOT_INSTALLED;
    }
    void *target = slot->platform_data ? slot->platform_data : slot->target;
    MH_DisableHook(target);
    MH_RemoveHook(target);
    slot->trampoline = NULL;
    slot->platform_data = NULL;
    return HORSE_HOOK_OK;
}

#else
/* hook.c provides fallback when MinHook disabled */
#endif
