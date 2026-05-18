#ifndef HORSE_DATA_BMFONT_TXT_H
#define HORSE_DATA_BMFONT_TXT_H

#include "horse_data/genes_dat.h"

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define HORSE_DATA_BMFONT_ADVANCES_MAX 512

typedef struct HorseDataBMFont {
    char name[64];
    int32_t size;
    int32_t ascent;
    int32_t descent;
    uint32_t char_count;
    uint32_t kerning_count;
    int32_t advances[HORSE_DATA_BMFONT_ADVANCES_MAX];
    uint32_t advance_count;
} HorseDataBMFont;

HorseDataStatus horse_data_bmfont_load_file(const char *path, HorseDataBMFont *out);

#ifdef __cplusplus
}
#endif

#endif /* HORSE_DATA_BMFONT_TXT_H */
