/**
 * Map helpers (minimap mod / Phase 5).
 * TMX from horse_data; live view position is best-effort until RE pins a field.
 */
#ifndef HORSE_MAP_H
#define HORSE_MAP_H

#include <horse_data/tmx_map.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct HorseMapView {
    float world_x;
    float world_y;
    int valid;
} HorseMapView;

/** Load horsey.tmx from path (e.g. Game\\data\\horsey.tmx). */
HorseDataStatus horse_map_load_tmx(const char *path, HorseDataTmxMap *out);

/**
 * Best-effort player/world position from save context.
 * save_ctx: pointer seen as GainMoney/SpendMoney rcx (money @ +0x308).
 * Reads vec2 @ save_ctx+0x39C per SaveContext.h / Save_Write disasm.
 */
int horse_map_read_view_from_save_ctx(const void *save_ctx, HorseMapView *out);

/** World coords -> tile indices using TMX tile size. */
void horse_map_world_to_tile(const HorseDataTmxMap *map, float wx, float wy, int *tile_x, int *tile_y);

#ifdef __cplusplus
}
#endif

#endif /* HORSE_MAP_H */
