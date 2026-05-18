/**
 * Map helpers (HorseSDK / Phase 5).
 * Implemented in libhorse_sdk when CMake HORSE_SDK_BUILD_DATA=ON.
 * TMX via horse_data; live view from g_save_context + save ctx offsets.
 * See RE_Tools/docs/MapViewPosition.md.
 */
#ifndef HORSE_MAP_H
#define HORSE_MAP_H

#include <horse_data/tmx_map.h>

#ifdef __cplusplus
extern "C" {
#endif

/** Active save context pointer @ Horsey.exe+0x31A660 (store @ 0x103B6C before Save_Load). */
#define HORSE_RVA_g_save_context 0x0031A660u

/** SaveContext offsets — SaveGhidraCrossref.md, load @ 0x6EA57 / 0x6EA90. */
#define HORSE_SAVE_OFF_HORSE_OBJ 0x300u
#define HORSE_SAVE_OFF_CAMERA_X 0x394u
#define HORSE_SAVE_OFF_CAMERA_Y 0x398u
#define HORSE_SAVE_OFF_HORSE_VIEW_X 0x28u /* on object at +0x300 */

typedef struct HorseMapView {
    float world_x;
    float world_y;
    int valid;
    int source; /* 0 none, 1 horse_obj+0x28, 2 ctx+0x394 */
} HorseMapView;

HorseDataStatus horse_map_load_tmx(const char *path, HorseDataTmxMap *out);

/** Read qword @ [module+0x31A660] — active save context heap pointer. */
void *horse_map_get_save_context(const void *game_base);

/**
 * Best-effort world/camera position for minimap dot.
 * Tries [ctx+0x300]+0x28 (live horse object), then ctx+0x394/+0x398 (footer camera).
 */
int horse_map_read_view(const void *game_base, const void *save_ctx_hint, HorseMapView *out);

/** Legacy wrapper — save_ctx only, no global. */
int horse_map_read_view_from_save_ctx(const void *save_ctx, HorseMapView *out);

void horse_map_world_to_tile(const HorseDataTmxMap *map, float wx, float wy, int *tile_x, int *tile_y);

#ifdef __cplusplus
}
#endif

#endif /* HORSE_MAP_H */
