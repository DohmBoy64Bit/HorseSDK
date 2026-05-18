#include "map_atlas.h"

#include <horse_data/png_rgba.h>

#include <stdio.h>
#include <string.h>

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

static void path_join(char *out, size_t outsz, const char *dir, const char *file)
{
    if (dir == NULL || file == NULL) {
        out[0] = '\0';
        return;
    }
    snprintf(out, outsz, "%s\\%s", dir, file);
}

int map_atlas_init(MapAtlas *a, const char *data_dir)
{
    char path[MAX_PATH];
    if (a == NULL || data_dir == NULL) {
        return 0;
    }
    memset(a, 0, sizeof(*a));
    strncpy(a->data_dir, data_dir, sizeof(a->data_dir) - 1);
    a->data_dir[sizeof(a->data_dir) - 1] = '\0';

    path_join(path, sizeof(path), data_dir, "terrain.xml");
    if (horse_data_atlas_load_file(path, &a->terrain_xml) != HORSE_DATA_OK) {
        return 0;
    }
    path_join(path, sizeof(path), data_dir, "terrain.png");
    if (horse_data_png_load_rgba(path, &a->terrain_pixels, &a->terrain_w, &a->terrain_h) != HORSE_DATA_OK) {
        return 0;
    }

    path_join(path, sizeof(path), data_dir, "locs.xml");
    if (horse_data_atlas_load_file(path, &a->locs_xml) != HORSE_DATA_OK) {
        return 0;
    }
    path_join(path, sizeof(path), data_dir, "locs.png");
    if (horse_data_png_load_rgba(path, &a->locs_pixels, &a->locs_w, &a->locs_h) != HORSE_DATA_OK) {
        return 0;
    }

    a->ready = 1;
    return 1;
}

void map_atlas_free(MapAtlas *a)
{
    if (a == NULL) {
        return;
    }
    horse_data_png_free(a->terrain_pixels);
    horse_data_png_free(a->locs_pixels);
    memset(a, 0, sizeof(*a));
}

int map_atlas_sprite_for_gid(const MapAtlas *a, const HorseDataTmxMap *map, uint32_t gid,
                             const HorseDataAtlasSprite **spr, int *atlas_kind)
{
    const HorseDataTextureAtlas *atlas = NULL;
    uint32_t local_id = 0;
    int kind = 0;

    if (a == NULL || !a->ready || map == NULL || spr == NULL || gid == 0) {
        return 0;
    }

    const HorseDataTmxTileset *chosen = NULL;
    for (uint32_t i = 0; i < map->tileset_count; i++) {
        const HorseDataTmxTileset *ts = &map->tilesets[i];
        if (gid >= ts->first_gid) {
            if (chosen == NULL || ts->first_gid > chosen->first_gid) {
                chosen = ts;
            }
        }
    }
    if (chosen == NULL) {
        return 0;
    }

    local_id = gid - chosen->first_gid;
    if (strstr(chosen->source, "locs") != NULL) {
        atlas = &a->locs_xml;
        kind = 1;
    } else {
        atlas = &a->terrain_xml;
        kind = 0;
    }
    if (local_id >= atlas->sprite_count) {
        return 0;
    }
    *spr = &atlas->sprites[local_id];
    if (atlas_kind) {
        *atlas_kind = kind;
    }
    return 1;
}
