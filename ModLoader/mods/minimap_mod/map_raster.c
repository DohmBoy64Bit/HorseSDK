#include "map_raster.h"

#include <stdlib.h>
#include <string.h>

static uint32_t gid_color(uint32_t gid)
{
    if (gid == 0) {
        return 0xFF1A2818; /* BGRA dark */
    }
    uint32_t g = gid & 0xFFFF;
    uint8_t r = (uint8_t)((g * 47) & 0xFF);
    uint8_t gch = (uint8_t)((g * 91 + 40) & 0xFF);
    uint8_t b = (uint8_t)((g * 13 + 60) & 0xFF);
    return (uint32_t)b | ((uint32_t)gch << 8) | ((uint32_t)r << 16) | 0xFF000000u;
}

int map_raster_from_tmx(const HorseDataTmxMap *map, int scale, MapRaster *out)
{
    if (map == NULL || out == NULL || scale < 1) {
        return 0;
    }
    memset(out, 0, sizeof(*out));
    uint32_t w = map->width;
    uint32_t h = map->height;
    if (w == 0 || h == 0) {
        return 0;
    }
    out->width = (int)(w * (uint32_t)scale);
    out->height = (int)(h * (uint32_t)scale);
    size_t n = (size_t)out->width * (size_t)out->height;
    out->pixels = (uint32_t *)calloc(n, sizeof(uint32_t));
    if (out->pixels == NULL) {
        return 0;
    }

    for (uint32_t ly = 0; ly < map->layer_count; ly++) {
        const HorseDataTmxLayer *L = &map->layers[ly];
        if (L->cells == NULL || L->width != w || L->height != h) {
            continue;
        }
        for (uint32_t ty = 0; ty < h; ty++) {
            for (uint32_t tx = 0; tx < w; tx++) {
                uint32_t gid = L->cells[ty * w + tx];
                if (gid == 0 && ly > 0) {
                    continue;
                }
                uint32_t c = gid_color(gid);
                for (int sy = 0; sy < scale; sy++) {
                    for (int sx = 0; sx < scale; sx++) {
                        int px = (int)tx * scale + sx;
                        int py = (int)ty * scale + sy;
                        out->pixels[py * out->width + px] = c;
                    }
                }
            }
        }
    }
    return 1;
}

void map_raster_free(MapRaster *r)
{
    if (r == NULL) {
        return;
    }
    free(r->pixels);
    r->pixels = NULL;
    r->width = r->height = 0;
}

void map_raster_draw_dot(MapRaster *r, int tile_x, int tile_y, int scale, uint32_t bgra)
{
    if (r == NULL || r->pixels == NULL || scale < 1) {
        return;
    }
    int cx = tile_x * scale + scale / 2;
    int cy = tile_y * scale + scale / 2;
    int rad = scale + 1;
    for (int dy = -rad; dy <= rad; dy++) {
        for (int dx = -rad; dx <= rad; dx++) {
            int px = cx + dx;
            int py = cy + dy;
            if (px < 0 || py < 0 || px >= r->width || py >= r->height) {
                continue;
            }
            if (dx * dx + dy * dy <= rad * rad) {
                r->pixels[py * r->width + px] = bgra;
            }
        }
    }
}
