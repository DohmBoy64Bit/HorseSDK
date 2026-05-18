/**
 * Hook catalog for mod loader (Phase 4).
 * Regenerate: python RE_Tools/tools/scripts/build_game_function_catalog.py
 */
#ifndef HORSE_GAME_FUNCTION_HOOKS_H
#define HORSE_GAME_FUNCTION_HOOKS_H

#include "horse/game_functions.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct HorseHookCatalogEntry {
    const char *id;
    const char *name;
    uint32_t rva;
    uint8_t safe_pre_call;
    const char *notes;
} HorseHookCatalogEntry;

static const HorseHookCatalogEntry g_horse_hook_catalog[] = {
    { "gain_money", "GainMoney", 0x0010AB80u, 1, "UI feedback on credit" },
    { "spend_money", "SpendMoney", 0x0010AC60u, 1, "Shop/race debit; 4-arg per disasm@10AC94" },
    { "save_write", "Save_Write", 0x0006DAB0u, 1, "Pre-call: log ctx; avoid re-entrancy" },
    { "save_load", "Save_Load", 0x0006E2B0u, 1, "Pre-call: backup save path" },
    { "buy_item", "BuyItem", 0x000787D0u, 0, "Shop UI tick; fires often while shop open" },
    { "game_update_world", "Game_UpdateWorld", 0x00087510u, 0, "Every frame; no built-in detour (too noisy)" },
    { "race_advance_sim", "RaceAdvanceSim", 0x0008C9E0u, 1, "Hot path; throttle logging" },
    { "clamp_int3", "ClampInt3", 0x000C12D0u, 1, "Pure clamp; safe to wrap" },
};

#define HORSE_HOOK_CATALOG_COUNT (sizeof(g_horse_hook_catalog) / sizeof(g_horse_hook_catalog[0]))

#ifdef __cplusplus
}
#endif

#endif /* HORSE_GAME_FUNCTION_HOOKS_H */
