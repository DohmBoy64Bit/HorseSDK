/**
 * Horsey.exe — verified RVAs for SDK hooks (auto-generated).
 *
 * Image base: 0x140000000
 * Regenerate: python RE_Tools/tools/scripts/build_game_function_catalog.py
 *
 * Do not edit by hand.
 */
#ifndef HORSE_GAME_FUNCTIONS_H
#define HORSE_GAME_FUNCTIONS_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define HORSE_IMAGE_BASE 0x140000000ULL
#define HORSE_RVA_TO_VA(rva) ((void *)(HORSE_IMAGE_BASE + (uint32_t)(rva)))

static inline void *horse_rva(const void *module_base, uint32_t rva) {
    return (uint8_t *)module_base + rva;
}

/* --- loop --- */
#define HORSE_RVA_ClampInt3                        0x000C12D0u
#define HORSE_RVA_GameMain_InitAndLoop             0x000BE0F0u
#define HORSE_RVA_Game_DispatchSdlEvent            0x000C0430u

/* --- economy --- */
#define HORSE_RVA_GainMoney                        0x0010AB80u

/* --- spawn --- */
#define HORSE_RVA_SimSpawnDisk                     0x00033A20u

/* --- shop --- */
#define HORSE_RVA_BuyItem                          0x000787D0u
#define HORSE_RVA_HorseMart                        0x0007AC8Eu
#define HORSE_RVA_Shopkeep                         0x000785A0u

/* --- race --- */
#define HORSE_RVA_BetMore                          0x000908BDu
#define HORSE_RVA_Betting                          0x0002CFE0u
#define HORSE_RVA_CrossFinishLine                  0x000912F9u
#define HORSE_RVA_OnYourMark                       0x0008A62Fu
#define HORSE_RVA_RaceGetSet                       0x0002DAE7u
#define HORSE_RVA_RaceStateMachine                 0x0008F2B0u
#define HORSE_RVA_SimHorseFinished                 0x000334E5u
#define HORSE_RVA_SimMessageDispatch               0x0005E0C2u
#define HORSE_RVA_SimStartRace                     0x00032FA3u
#define HORSE_RVA_WonRace                          0x0009177Bu

/* --- horse --- */
#define HORSE_RVA_DropHorseFail                    0x000D3C50u
#define HORSE_RVA_GrabHorse                        0x000D9158u
#define HORSE_RVA_LerpHorse                        0x00076149u
#define HORSE_RVA_ProcessHorse                     0x000A23F0u

/* --- breeding --- */
#define HORSE_RVA_StatusFoal                       0x00056892u
#define HORSE_RVA_Studs                            0x000E90EAu

/* --- save --- */
#define HORSE_RVA_FooterExtra_Read                 0x00101810u
#define HORSE_RVA_FooterExtra_Write                0x001017C0u
#define HORSE_RVA_PackGenes_6D2A0                  0x0006D2A0u
#define HORSE_RVA_ReadCheck                        0x0006FB90u
#define HORSE_RVA_ReadOpen                         0x0006F3C0u
#define HORSE_RVA_Save_Load                        0x0006E2B0u
#define HORSE_RVA_Save_LoadFromBuffer              0x0006E643u
#define HORSE_RVA_Save_Write                       0x0006DAB0u
#define HORSE_RVA_UnpackGenes_6D3B0                0x0006D3B0u
#define HORSE_RVA_WriteFlush                       0x0006FD90u

/* --- io --- */
#define HORSE_RVA_FlushToFile_fopenRead            0x0006FD90u
#define HORSE_RVA_GridWriteLoop_GridReadLoop       0x0006DF30u
#define HORSE_RVA_PairWrite_ReadPairVec            0x0006E043u
#define HORSE_RVA_StreamAvail_ReadU32Peek          0x0006FDF0u
#define HORSE_RVA_StreamOpen                       0x0006FD40u
#define HORSE_RVA_WriteF32_ReadF32                 0x0006FF10u
#define HORSE_RVA_WriteFlush                       0x0006FD90u
#define HORSE_RVA_WriteNestedItem_ReadNestedItem   0x0006EC40u
#define HORSE_RVA_WriteNestedSave_ReadNestedSave   0x0006D440u
#define HORSE_RVA_WriteStdString_ReadStringLen     0x0006FFF0u
#define HORSE_RVA_WriteU16_ReadU16                 0x0006FE50u
#define HORSE_RVA_WriteU32FromU8_ReadU8asU32       0x0006FEF0u
#define HORSE_RVA_WriteU32_ReadU32                 0x0006FE10u
#define HORSE_RVA_WriteU64_ReadU64                 0x0006FE70u
#define HORSE_RVA_WriteU8_ReadU8                   0x0006FEB0u
#define HORSE_RVA_WriteU8_alt_ReadU8               0x0006FE30u
#define HORSE_RVA_WriteVec2F32_ReadF32x2           0x0006FF30u

/* --- nested --- */
#define HORSE_RVA_ReadNestedItem                   0x0006EF80u
#define HORSE_RVA_ReadNestedSave                   0x0006D5C0u
#define HORSE_RVA_Type1_B8_Read                    0x00102E20u
#define HORSE_RVA_Type1_B8_Write                   0x00102DC0u
#define HORSE_RVA_WriteNestedItem                  0x0006EC40u
#define HORSE_RVA_WriteNestedSave                  0x0006D440u

/* --- settings --- */
#define HORSE_RVA_SettingsLoader                   0x000711B0u
#define HORSE_RVA_Settings_Save                    0x00071F60u

/* --- world --- */
#define HORSE_RVA_Game_BootstrapWorld              0x000874B0u
#define HORSE_RVA_Game_UpdateWorld                 0x00087510u
#define HORSE_RVA_Game_WorldSimStep                0x00088510u

/* --- font --- */
#define HORSE_RVA_Font_LoadOrInit                  0x0007F8A0u

/* --- genetics --- */
#define HORSE_RVA_GeneticsApply                    0x000AE470u
#define HORSE_RVA_GeneticsApplyGate                0x000ADB30u

/* --- globals --- */
#define HORSE_RVA_g_game_state                     0x00313720u

#ifdef __cplusplus
}
#endif

#endif /* HORSE_GAME_FUNCTIONS_H */
