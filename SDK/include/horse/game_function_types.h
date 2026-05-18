/**
 * Typed function pointers (microsoft x64) from catalog parameters.
 * Regenerate: python RE_Tools/tools/scripts/build_game_function_catalog.py
 */
#ifndef HORSE_GAME_FUNCTION_TYPES_H
#define HORSE_GAME_FUNCTION_TYPES_H

#include "horse/game_functions.h"
#include "horse/module.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef int (*HORSE_FN_ClampInt3)(int value, int lo, int hi);
#define HORSE_PTR_ClampInt3(base) ((HORSE_FN_ClampInt3)horse_module_rva((base), HORSE_RVA_ClampInt3))

typedef void (*HORSE_FN_GainMoney)(void * ctx, int amount, char show_ui);
#define HORSE_PTR_GainMoney(base) ((HORSE_FN_GainMoney)horse_module_rva((base), HORSE_RVA_GainMoney))

typedef void (*HORSE_FN_HorseRaceScore)(void * race_ctx, int horse_index);
#define HORSE_PTR_HorseRaceScore(base) ((HORSE_FN_HorseRaceScore)horse_module_rva((base), HORSE_RVA_HorseRaceScore))

typedef void (*HORSE_FN_RaceAdvanceSim)(void * race_ctx);
#define HORSE_PTR_RaceAdvanceSim(base) ((HORSE_FN_RaceAdvanceSim)horse_module_rva((base), HORSE_RVA_RaceAdvanceSim))

typedef void (*HORSE_FN_Save_Load)(void * ctx);
#define HORSE_PTR_Save_Load(base) ((HORSE_FN_Save_Load)horse_module_rva((base), HORSE_RVA_Save_Load))

typedef void (*HORSE_FN_Save_Write)(void * ctx);
#define HORSE_PTR_Save_Write(base) ((HORSE_FN_Save_Write)horse_module_rva((base), HORSE_RVA_Save_Write))

typedef int (*HORSE_FN_SimRandMod)(int modulus);
#define HORSE_PTR_SimRandMod(base) ((HORSE_FN_SimRandMod)horse_module_rva((base), HORSE_RVA_SimRandMod))

typedef void (*HORSE_FN_SpendMoney)(void * ctx, int cost);
#define HORSE_PTR_SpendMoney(base) ((HORSE_FN_SpendMoney)horse_module_rva((base), HORSE_RVA_SpendMoney))

#ifdef __cplusplus
}
#endif

#endif /* HORSE_GAME_FUNCTION_TYPES_H */
