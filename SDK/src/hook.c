/**
 * Minimal x64 hook (5-byte rel32 JMP). Windows only for install/remove.
 */
#include "horse/hook.h"

#include <limits.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

#if defined(_WIN32)

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#define HORSE_HOOK_PATCH_LEN 5

typedef struct HorseHookPlatform {
    uint8_t original[HORSE_HOOK_PATCH_LEN];
    void *trampoline;
} HorseHookPlatform;

static int hook_unprotect(void *addr, size_t len, DWORD *old)
{
    return VirtualProtect(addr, len, PAGE_EXECUTE_READWRITE, old) != 0;
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

    HorseHookPlatform *plat = (HorseHookPlatform *)calloc(1, sizeof(HorseHookPlatform));
    if (plat == NULL) {
        return HORSE_HOOK_ERR_INVALID;
    }

    uint8_t *target = (uint8_t *)slot->target;
    memcpy(plat->original, target, HORSE_HOOK_PATCH_LEN);

    /*
     * Trampoline: original 5 bytes + jmp back to target+5.
     * Requires target+5 within rel32 range of trampoline tail (same module: OK).
     */
    uint8_t *tramp = (uint8_t *)VirtualAlloc(NULL, 32, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (tramp == NULL) {
        free(plat);
        return HORSE_HOOK_ERR_PROTECT;
    }
    memcpy(tramp, plat->original, HORSE_HOOK_PATCH_LEN);
    tramp[HORSE_HOOK_PATCH_LEN] = 0xE9;
    int32_t back = (int32_t)((target + HORSE_HOOK_PATCH_LEN) - (tramp + HORSE_HOOK_PATCH_LEN + 5));
    memcpy(tramp + HORSE_HOOK_PATCH_LEN + 1, &back, 4);

    DWORD old_prot;
    if (!hook_unprotect(target, HORSE_HOOK_PATCH_LEN, &old_prot)) {
        VirtualFree(tramp, 0, MEM_RELEASE);
        free(plat);
        return HORSE_HOOK_ERR_PROTECT;
    }

    intptr_t delta = (intptr_t)slot->detour - (intptr_t)(target + HORSE_HOOK_PATCH_LEN);
    if (delta > INT32_MAX || delta < INT32_MIN) {
        VirtualProtect(target, HORSE_HOOK_PATCH_LEN, old_prot, &old_prot);
        VirtualFree(tramp, 0, MEM_RELEASE);
        free(plat);
        return HORSE_HOOK_ERR_RANGE;
    }

    int32_t rel = (int32_t)delta;
    target[0] = 0xE9;
    memcpy(target + 1, &rel, 4);
    VirtualProtect(target, HORSE_HOOK_PATCH_LEN, old_prot, &old_prot);
    FlushInstructionCache(GetCurrentProcess(), target, HORSE_HOOK_PATCH_LEN);

    plat->trampoline = tramp;
    slot->trampoline = tramp;
    slot->platform_data = plat;
    return HORSE_HOOK_OK;
}

HorseHookStatus horse_hook_remove(HorseHookSlot *slot)
{
    if (slot == NULL || slot->target == NULL) {
        return HORSE_HOOK_ERR_INVALID;
    }
    if (slot->trampoline == NULL || slot->platform_data == NULL) {
        return HORSE_HOOK_ERR_NOT_INSTALLED;
    }

    HorseHookPlatform *plat = (HorseHookPlatform *)slot->platform_data;
    uint8_t *target = (uint8_t *)slot->target;

    DWORD old_prot;
    if (!hook_unprotect(target, HORSE_HOOK_PATCH_LEN, &old_prot)) {
        return HORSE_HOOK_ERR_PROTECT;
    }
    memcpy(target, plat->original, HORSE_HOOK_PATCH_LEN);
    VirtualProtect(target, HORSE_HOOK_PATCH_LEN, old_prot, &old_prot);
    FlushInstructionCache(GetCurrentProcess(), target, HORSE_HOOK_PATCH_LEN);

    VirtualFree(plat->trampoline, 0, MEM_RELEASE);
    free(plat);

    slot->trampoline = NULL;
    slot->platform_data = NULL;
    return HORSE_HOOK_OK;
}

#else

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
    (void)slot;
    return HORSE_HOOK_ERR_NOT_FOUND;
}

HorseHookStatus horse_hook_remove(HorseHookSlot *slot)
{
    (void)slot;
    return HORSE_HOOK_ERR_NOT_INSTALLED;
}

#endif
