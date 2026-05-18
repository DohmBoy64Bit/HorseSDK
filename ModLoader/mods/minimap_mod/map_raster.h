#ifndef MAP_RASTER_H
#define MAP_RASTER_H

#include <horse_data/tmx_map.h>
#include <horse/horse_map.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct MapRaster {
    uint32_t *pixels; /* BGRA */
    int width;
    int height;
} MapRaster;

int map_raster_from_tmx(const HorseDataTmxMap *map, int scale, MapRaster *out);
void map_raster_free(MapRaster *r);
void map_raster_draw_dot(MapRaster *r, int tile_x, int tile_y, int scale, uint32_t bgra);

#ifdef __cplusplus
}
#endif

#endif /* MAP_RASTER_H */
