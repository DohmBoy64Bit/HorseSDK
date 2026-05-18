/**
 * Resolve Horsey.exe module base and RVAs (ASLR-safe).
 *
 * RVAs: horse/game_functions.h (from Phase 2 catalog).
 */
#ifndef HORSE_MODULE_H
#define HORSE_MODULE_H

#include <stdint.h>

#include "horse/version.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum HorseModuleStatus {
    HORSE_MODULE_OK = 0,
    HORSE_MODULE_ERR_NOT_FOUND = 1,
    HORSE_MODULE_ERR_INVALID = 2,
} HorseModuleStatus;

/** Default module name when the game is running. */
#define HORSE_MODULE_NAME "Horsey.exe"

/**
 * Cached base of HORSE_MODULE_NAME, or NULL if not loaded.
 * Pass force_refresh non-zero to re-query GetModuleHandle.
 */
const void *horse_module_base(int force_refresh);

/** module_base + rva; NULL if module_base is NULL. */
void *horse_module_rva(const void *module_base, uint32_t rva);

/** Convenience: horse_module_rva(horse_module_base(0), rva). */
void *horse_resolve(uint32_t rva);

#ifdef __cplusplus
}
#endif

#endif /* HORSE_MODULE_H */
