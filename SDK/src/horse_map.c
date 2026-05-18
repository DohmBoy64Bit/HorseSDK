#include <horse/horse_map.h>

#include <math.h>
#include <string.h>

HorseDataStatus horse_map_load_tmx(const char *path, HorseDataTmxMap *out)
{
    return horse_data_tmx_load_file(path, out);
}

void *horse_map_get_save_context(const void *game_base)
{
    if (game_base == NULL) {
        return NULL;
    }
    const void *slot = (const void *)((const char *)game_base + HORSE_RVA_g_save_context);
    return *(void *const *)slot;
}

static int valid_map_coord(float x, float y)
{
    if (x != x || y != y) {
        return 0;
    }
    if (fabsf(x) > 200000.f || fabsf(y) > 200000.f) {
        return 0;
    }
    return 1;
}

int horse_map_read_view(const void *game_base, const void *save_ctx_hint, HorseMapView *out)
{
    if (out == NULL) {
        return 0;
    }
    memset(out, 0, sizeof(*out));

    const void *ctx = save_ctx_hint;
    if (ctx == NULL) {
        ctx = horse_map_get_save_context(game_base);
    }
    if (ctx == NULL) {
        return 0;
    }

    const char *base = (const char *)ctx;

    /* Live path: copy target @ Save_Load 0x6EA90 → [ctx+0x300]+0x28 */
    const void *horse_obj = *(const void *const *)(base + HORSE_SAVE_OFF_HORSE_OBJ);
    if (horse_obj != NULL) {
        const float *xy = (const float *)((const char *)horse_obj + HORSE_SAVE_OFF_HORSE_VIEW_X);
        if (valid_map_coord(xy[0], xy[1])) {
            out->world_x = xy[0];
            out->world_y = xy[1];
            out->valid = 1;
            out->source = 1;
            return 1;
        }
    }

    /* Footer / camera fields @ 0x6EA57 → ctx+0x394/+0x398 */
    const float *cam = (const float *)(base + HORSE_SAVE_OFF_CAMERA_X);
    if (valid_map_coord(cam[0], cam[1])) {
        out->world_x = cam[0];
        out->world_y = cam[1];
        out->valid = 1;
        out->source = 2;
        return 1;
    }

    return 0;
}

int horse_map_read_view_from_save_ctx(const void *save_ctx, HorseMapView *out)
{
    return horse_map_read_view(NULL, save_ctx, out);
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
