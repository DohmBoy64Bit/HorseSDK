/**
 * Minimal horsey.tmx reader (orthogonal CSV layers).
 * Mirrors RE_Tools/tools/parsers/tiled_map.py subset.
 */
#ifndef HORSE_DATA_TMX_MAP_H
#define HORSE_DATA_TMX_MAP_H

#include "horse_data/genes_dat.h"

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define HORSE_DATA_TMX_LAYERS_MAX 16
#define HORSE_DATA_TMX_LAYER_NAME 64
#define HORSE_DATA_TMX_TILESETS_MAX 8
#define HORSE_DATA_TMX_TILESET_SRC_MAX 64
#define HORSE_DATA_TMX_CELLS_MAX (512 * 512)

typedef struct HorseDataTmxTileset {
    uint32_t first_gid;
    char source[HORSE_DATA_TMX_TILESET_SRC_MAX];
} HorseDataTmxTileset;

typedef struct HorseDataTmxLayer {
    char name[HORSE_DATA_TMX_LAYER_NAME];
    uint32_t width;
    uint32_t height;
    uint32_t *cells; /* width*height GIDs */
} HorseDataTmxLayer;

typedef struct HorseDataTmxMap {
    uint32_t width;
    uint32_t height;
    uint32_t tile_width;
    uint32_t tile_height;
    HorseDataTmxLayer layers[HORSE_DATA_TMX_LAYERS_MAX];
    uint32_t layer_count;
    HorseDataTmxTileset tilesets[HORSE_DATA_TMX_TILESETS_MAX];
    uint32_t tileset_count;
} HorseDataTmxMap;

HorseDataStatus horse_data_tmx_load_file(const char *path, HorseDataTmxMap *out);
void horse_data_tmx_free(HorseDataTmxMap *map);

#ifdef __cplusplus
}
#endif

#endif /* HORSE_DATA_TMX_MAP_H */
