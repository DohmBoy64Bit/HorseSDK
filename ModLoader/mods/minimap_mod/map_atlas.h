#ifndef MAP_ATLAS_H
#define MAP_ATLAS_H

#include <horse_data/texture_atlas.h>
#include <horse_data/tmx_map.h>

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct MapAtlas {
    int ready;
    char data_dir[MAX_PATH];
    uint32_t *terrain_pixels;
    int terrain_w;
    int terrain_h;
    HorseDataTextureAtlas terrain_xml;
    uint32_t *locs_pixels;
    int locs_w;
    int locs_h;
    HorseDataTextureAtlas locs_xml;
} MapAtlas;

int map_atlas_init(MapAtlas *a, const char *data_dir);
void map_atlas_free(MapAtlas *a);
int map_atlas_sprite_for_gid(const MapAtlas *a, const HorseDataTmxMap *map, uint32_t gid,
                             const HorseDataAtlasSprite **spr, int *atlas_kind);
/* atlas_kind: 0 terrain, 1 locs */

#ifdef __cplusplus
}
#endif

#endif /* MAP_ATLAS_H */
