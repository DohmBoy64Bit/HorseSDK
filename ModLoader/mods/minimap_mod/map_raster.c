#include "map_raster.h"

#include "map_atlas.h"

#include <stdlib.h>
#include <string.h>

static uint32_t gid_color_fallback(uint32_t gid)
{
    if (gid == 0) {
        return 0xFF1A2818;
    }
    uint32_t g = gid & 0xFFFF;
    uint8_t r = (uint8_t)((g * 47) & 0xFF);
    uint8_t gch = (uint8_t)((g * 91 + 40) & 0xFF);
    uint8_t b = (uint8_t)((g * 13 + 60) & 0xFF);
    return (uint32_t)b | ((uint32_t)gch << 8) | ((uint32_t)r << 16) | 0xFF000000u;
}

static void blit_tile_bgra(MapRaster *out, int dst_x, int dst_y, int scale,
                           const uint32_t *atlas_px, int atlas_w, int atlas_h,
                           int sx, int sy, int sw, int sh)
{
    if (out == NULL || out->pixels == NULL || atlas_px == NULL || scale < 1) {
        return;
    }
    if (sw <= 0 || sh <= 0) {
        return;
    }
    for (int ty = 0; ty < scale; ty++) {
        for (int tx = 0; tx < scale; tx++) {
            int px = dst_x * scale + tx;
            int py = dst_y * scale + ty;
            if (px < 0 || py < 0 || px >= out->width || py >= out->height) {
                continue;
            }
            int asx = sx + (tx * sw) / scale;
            int asy = sy + (ty * sh) / scale;
            if (asx < 0 || asy < 0 || asx >= atlas_w || asy >= atlas_h) {
                continue;
            }
            uint32_t c = atlas_px[asy * atlas_w + asx];
            if ((c & 0xFF000000u) == 0) {
                continue;
            }
            out->pixels[py * out->width + px] = c;
        }
    }
}

int map_raster_from_tmx(const HorseDataTmxMap *map, int scale, MapRaster *out)
{
    return map_raster_from_tmx_atlas(map, NULL, scale, out);
}

int map_raster_from_tmx_atlas(const HorseDataTmxMap *map, const MapAtlas *atlas, int scale, MapRaster *out)
{
    if (map == NULL || out == NULL || scale < 1) {
        return 0;
    }
    map_raster_free(out);
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

    for (uint32_t ty = 0; ty < h; ty++) {
        for (uint32_t tx = 0; tx < w; tx++) {
            uint32_t gid = 0;
            for (uint32_t ly = 0; ly < map->layer_count; ly++) {
                const HorseDataTmxLayer *L = &map->layers[ly];
                if (L->cells == NULL || L->width != w || L->height != h) {
                    continue;
                }
                uint32_t g = L->cells[ty * w + tx];
                if (g != 0) {
                    gid = g;
                }
            }
            if (gid == 0) {
                continue;
            }

            const HorseDataAtlasSprite *spr = NULL;
            int kind = 0;
            if (atlas != NULL && atlas->ready &&
                map_atlas_sprite_for_gid(atlas, map, gid, &spr, &kind)) {
                const uint32_t *px = kind ? atlas->locs_pixels : atlas->terrain_pixels;
                int aw = kind ? atlas->locs_w : atlas->terrain_w;
                int ah = kind ? atlas->locs_h : atlas->terrain_h;
                int sw = spr->width > 0 ? spr->width : (int)map->tile_width;
                int sh = spr->height > 0 ? spr->height : (int)map->tile_height;
                blit_tile_bgra(out, (int)tx, (int)ty, scale, px, aw, ah, spr->x, spr->y, sw, sh);
            } else {
                uint32_t c = gid_color_fallback(gid);
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
