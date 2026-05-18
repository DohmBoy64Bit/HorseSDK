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

typedef void (*HORSE_FN_BuyItem)(void * shop_ctx);
#define HORSE_PTR_BuyItem(base) ((HORSE_FN_BuyItem)horse_module_rva((base), HORSE_RVA_BuyItem))

typedef int (*HORSE_FN_ClampInt3)(int value, int lo, int hi);
#define HORSE_PTR_ClampInt3(base) ((HORSE_FN_ClampInt3)horse_module_rva((base), HORSE_RVA_ClampInt3))

typedef void (*HORSE_FN_Font_LoadOrInit)(void * ctx, const char * path, void * font_out, int flags);
#define HORSE_PTR_Font_LoadOrInit(base) ((HORSE_FN_Font_LoadOrInit)horse_module_rva((base), HORSE_RVA_Font_LoadOrInit))

typedef void (*HORSE_FN_GainMoney)(void * ctx, int amount, char show_ui);
#define HORSE_PTR_GainMoney(base) ((HORSE_FN_GainMoney)horse_module_rva((base), HORSE_RVA_GainMoney))

typedef void (*HORSE_FN_Game_BootstrapWorld)(void * ctx);
#define HORSE_PTR_Game_BootstrapWorld(base) ((HORSE_FN_Game_BootstrapWorld)horse_module_rva((base), HORSE_RVA_Game_BootstrapWorld))

typedef void (*HORSE_FN_Game_DispatchSdlEvent)(void * ctx, void * sdl_event);
#define HORSE_PTR_Game_DispatchSdlEvent(base) ((HORSE_FN_Game_DispatchSdlEvent)horse_module_rva((base), HORSE_RVA_Game_DispatchSdlEvent))

typedef void (*HORSE_FN_Game_UpdateWorld)(int frame_counter);
#define HORSE_PTR_Game_UpdateWorld(base) ((HORSE_FN_Game_UpdateWorld)horse_module_rva((base), HORSE_RVA_Game_UpdateWorld))

typedef void (*HORSE_FN_Game_WorldSimStep)(void);
#define HORSE_PTR_Game_WorldSimStep(base) ((HORSE_FN_Game_WorldSimStep)horse_module_rva((base), HORSE_RVA_Game_WorldSimStep))

typedef void (*HORSE_FN_GeneticsApply)(void * item, void * horse);
#define HORSE_PTR_GeneticsApply(base) ((HORSE_FN_GeneticsApply)horse_module_rva((base), HORSE_RVA_GeneticsApply))

typedef void (*HORSE_FN_GrabHorse)(void * ctx, int tile_or_mode);
#define HORSE_PTR_GrabHorse(base) ((HORSE_FN_GrabHorse)horse_module_rva((base), HORSE_RVA_GrabHorse))

typedef void (*HORSE_FN_HorseRaceScore)(void * race_ctx, int horse_index);
#define HORSE_PTR_HorseRaceScore(base) ((HORSE_FN_HorseRaceScore)horse_module_rva((base), HORSE_RVA_HorseRaceScore))

typedef void (*HORSE_FN_RaceAdvanceSim)(void * race_ctx);
#define HORSE_PTR_RaceAdvanceSim(base) ((HORSE_FN_RaceAdvanceSim)horse_module_rva((base), HORSE_RVA_RaceAdvanceSim))

typedef void (*HORSE_FN_RacePhaseDispatch)(void * race_ctx);
#define HORSE_PTR_RacePhaseDispatch(base) ((HORSE_FN_RacePhaseDispatch)horse_module_rva((base), HORSE_RVA_RacePhaseDispatch))

typedef void (*HORSE_FN_RaceSimHandler)(void * race_ctx);
#define HORSE_PTR_RaceSimHandler(base) ((HORSE_FN_RaceSimHandler)horse_module_rva((base), HORSE_RVA_RaceSimHandler))

typedef void (*HORSE_FN_RaceSimObject_Init)(void * race_ctx);
#define HORSE_PTR_RaceSimObject_Init(base) ((HORSE_FN_RaceSimObject_Init)horse_module_rva((base), HORSE_RVA_RaceSimObject_Init))

typedef void (*HORSE_FN_RaceStateMachine)(void * race_ctx);
#define HORSE_PTR_RaceStateMachine(base) ((HORSE_FN_RaceStateMachine)horse_module_rva((base), HORSE_RVA_RaceStateMachine))

typedef void (*HORSE_FN_RaceUpdateHorses)(void * race_ctx);
#define HORSE_PTR_RaceUpdateHorses(base) ((HORSE_FN_RaceUpdateHorses)horse_module_rva((base), HORSE_RVA_RaceUpdateHorses))

typedef void (*HORSE_FN_Save_Load)(void * ctx);
#define HORSE_PTR_Save_Load(base) ((HORSE_FN_Save_Load)horse_module_rva((base), HORSE_RVA_Save_Load))

typedef void (*HORSE_FN_Save_LoadFromBuffer)(void * ctx);
#define HORSE_PTR_Save_LoadFromBuffer(base) ((HORSE_FN_Save_LoadFromBuffer)horse_module_rva((base), HORSE_RVA_Save_LoadFromBuffer))

typedef void (*HORSE_FN_Save_Write)(void * ctx);
#define HORSE_PTR_Save_Write(base) ((HORSE_FN_Save_Write)horse_module_rva((base), HORSE_RVA_Save_Write))

typedef void (*HORSE_FN_SettingsLoader)(void * ctx);
#define HORSE_PTR_SettingsLoader(base) ((HORSE_FN_SettingsLoader)horse_module_rva((base), HORSE_RVA_SettingsLoader))

typedef void (*HORSE_FN_Settings_Save)(void);
#define HORSE_PTR_Settings_Save(base) ((HORSE_FN_Settings_Save)horse_module_rva((base), HORSE_RVA_Settings_Save))

typedef void (*HORSE_FN_SimPostMessage)(void * ctx, const char * tag);
#define HORSE_PTR_SimPostMessage(base) ((HORSE_FN_SimPostMessage)horse_module_rva((base), HORSE_RVA_SimPostMessage))

typedef int (*HORSE_FN_SimRandMod)(int modulus);
#define HORSE_PTR_SimRandMod(base) ((HORSE_FN_SimRandMod)horse_module_rva((base), HORSE_RVA_SimRandMod))

typedef void (*HORSE_FN_SimRandSeedFromFloat)(float * out2);
#define HORSE_PTR_SimRandSeedFromFloat(base) ((HORSE_FN_SimRandSeedFromFloat)horse_module_rva((base), HORSE_RVA_SimRandSeedFromFloat))

typedef void (*HORSE_FN_SimSpawnDisk)(void * world_ctx);
#define HORSE_PTR_SimSpawnDisk(base) ((HORSE_FN_SimSpawnDisk)horse_module_rva((base), HORSE_RVA_SimSpawnDisk))

typedef void (*HORSE_FN_SpawnEntity)(void * ctx);
#define HORSE_PTR_SpawnEntity(base) ((HORSE_FN_SpawnEntity)horse_module_rva((base), HORSE_RVA_SpawnEntity))

typedef void (*HORSE_FN_SpawnPlace)(void * ctx);
#define HORSE_PTR_SpawnPlace(base) ((HORSE_FN_SpawnPlace)horse_module_rva((base), HORSE_RVA_SpawnPlace))

typedef void (*HORSE_FN_SpendMoney)(void * ctx, int cost);
#define HORSE_PTR_SpendMoney(base) ((HORSE_FN_SpendMoney)horse_module_rva((base), HORSE_RVA_SpendMoney))

#ifdef __cplusplus
}
#endif

#endif /* HORSE_GAME_FUNCTION_TYPES_H */
