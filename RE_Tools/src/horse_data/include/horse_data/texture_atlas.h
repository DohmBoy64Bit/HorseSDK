#ifndef HORSE_DATA_TEXTURE_ATLAS_H
#define HORSE_DATA_TEXTURE_ATLAS_H

#include "horse_data/genes_dat.h"

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define HORSE_DATA_ATLAS_SPRITES_MAX 4096
#define HORSE_DATA_ATLAS_NAME_MAX 64

typedef struct HorseDataAtlasSprite {
    char name[HORSE_DATA_ATLAS_NAME_MAX];
    int32_t x;
    int32_t y;
    int32_t width;
    int32_t height;
    int32_t frame_count; /* -1 if absent */
} HorseDataAtlasSprite;

typedef struct HorseDataTextureAtlas {
    HorseDataAtlasSprite sprites[HORSE_DATA_ATLAS_SPRITES_MAX];
    uint32_t sprite_count;
} HorseDataTextureAtlas;

HorseDataStatus horse_data_atlas_load_file(const char *path, HorseDataTextureAtlas *out);

#ifdef __cplusplus
}
#endif

#endif /* HORSE_DATA_TEXTURE_ATLAS_H */
