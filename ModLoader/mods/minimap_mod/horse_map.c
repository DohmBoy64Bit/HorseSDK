#include <horse/horse_map.h>

#include <string.h>

HorseDataStatus horse_map_load_tmx(const char *path, HorseDataTmxMap *out)
{
    return horse_data_tmx_load_file(path, out);
}

int horse_map_read_view_from_save_ctx(const void *save_ctx, HorseMapView *out)
{
    if (save_ctx == NULL || out == NULL) {
        return 0;
    }
    memset(out, 0, sizeof(*out));
    const float *xy = (const float *)((const char *)save_ctx + 0x39C);
    out->world_x = xy[0];
    out->world_y = xy[1];
    if (out->world_x != out->world_x || out->world_y != out->world_y) {
        return 0;
    }
    out->valid = 1;
    return 1;
}

void horse_map_world_to_tile(const HorseDataTmxMap *map, float wx, float wy, int *tile_x, int *tile_y)
{
    if (tile_x == NULL || tile_y == NULL || map == NULL) {
        return;
    }
    uint32_t tw = map->tile_width ? map->tile_width : 32;
    uint32_t th = map->tile_height ? map->tile_height : 32;
    int tx = (int)(wx / (float)tw);
    int ty = (int)(wy / (float)th);
    if (tx < 0) {
        tx = 0;
    }
    if (ty < 0) {
        ty = 0;
    }
    if (map->width && (uint32_t)tx >= map->width) {
        tx = (int)map->width - 1;
    }
    if (map->height && (uint32_t)ty >= map->height) {
        ty = (int)map->height - 1;
    }
    *tile_x = tx;
    *tile_y = ty;
}
