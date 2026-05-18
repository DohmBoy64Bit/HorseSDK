#ifndef HORSE_DATA_PNG_RGBA_H
#define HORSE_DATA_PNG_RGBA_H

#include "horse_data/genes_dat.h"

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/** Load PNG as top-down RGBA8888 (caller frees with horse_data_png_free). */
HorseDataStatus horse_data_png_load_rgba(const char *path, uint32_t **pixels, int *width, int *height);
void horse_data_png_free(uint32_t *pixels);

#ifdef __cplusplus
}
#endif

#endif /* HORSE_DATA_PNG_RGBA_H */
