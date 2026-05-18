/**
 * Mod DLL API (Phase 4). Mods export HorseMod_GetInfo / HorseMod_Init / HorseMod_Shutdown.
 */
#ifndef HORSE_MOD_API_H
#define HORSE_MOD_API_H

#include <stdint.h>

#include "horse/hook.h"
#include "horse/module.h"

#ifdef __cplusplus
extern "C" {
#endif

#define HORSE_MOD_API_VERSION 1

typedef struct HorseModInfo {
    uint32_t api_version;
    const char *id;
    const char *name;
    const char *version;
} HorseModInfo;

typedef struct HorseModHost {
    uint32_t api_version;
    const void *game_base;
    void *(*resolve)(uint32_t rva);
    HorseHookStatus (*hook_install)(struct HorseHookSlot *slot);
    HorseHookStatus (*hook_remove)(struct HorseHookSlot *slot);
    void (*log)(const char *message);
} HorseModHost;

typedef const HorseModInfo *(*HorseModGetInfoFn)(void);
typedef int (*HorseModInitFn)(const HorseModHost *host);
typedef void (*HorseModShutdownFn)(void);

#define HORSE_MOD_EXPORT __declspec(dllexport)

#ifdef HORSE_MOD_BUILD
#define HORSE_MOD_API HORSE_MOD_EXPORT
#else
#define HORSE_MOD_API
#endif

#ifdef __cplusplus
}
#endif

#endif /* HORSE_MOD_API_H */
