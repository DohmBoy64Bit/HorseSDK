/**
 * Hook helpers for Horsey.exe (Phase 3).
 *
 * Install/remove use MinHook when built with HORSE_USE_MINHOOK (default on Windows),
 * else a minimal 5-byte rel32 JMP. Prefer catalog-documented hook sites.
 */
#ifndef HORSE_HOOK_H
#define HORSE_HOOK_H

#include <stdint.h>

#include "horse/module.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum HorseHookStatus {
    HORSE_HOOK_OK = 0,
    HORSE_HOOK_ERR_INVALID = 1,
    HORSE_HOOK_ERR_NOT_FOUND = 2,
    HORSE_HOOK_ERR_PROTECT = 3,
    HORSE_HOOK_ERR_RANGE = 4,
    HORSE_HOOK_ERR_ALREADY = 5,
    HORSE_HOOK_ERR_NOT_INSTALLED = 6,
} HorseHookStatus;

typedef struct HorseHookSlot {
    /** Game function entry (module base + HORSE_RVA_*). */
    void *target;
    /** Your replacement; receives same calling convention as target. */
    void *detour;
    /**
     * Filled by horse_hook_install: trampoline to call original.
     * Cast to the target's function type before calling.
     */
    void *trampoline;
    /** Opaque platform state; do not touch. */
    void *platform_data;
} HorseHookSlot;

/** Call once before hooks (ModLoader calls this at startup). */
int horse_hook_system_init(void);
void horse_hook_system_shutdown(void);

/** Initialize target from module base + catalog RVA. */
void horse_hook_slot_init(HorseHookSlot *slot, const void *module_base, uint32_t rva,
                          void *detour);

/** Install detour; sets slot->trampoline on success. */
HorseHookStatus horse_hook_install(HorseHookSlot *slot);

/** Restore original bytes and free trampoline. */
HorseHookStatus horse_hook_remove(HorseHookSlot *slot);

#ifdef __cplusplus
}
#endif

#endif /* HORSE_HOOK_H */
