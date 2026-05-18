#include "horse_data/png_rgba.h"

#define STB_IMAGE_IMPLEMENTATION
#define STBI_ONLY_PNG
#define STBI_NO_STDIO
#include "../../../ThirdParty/stb/stb_image.h"

#include <stdio.h>
#include <stdlib.h>

HorseDataStatus horse_data_png_load_rgba(const char *path, uint32_t **pixels, int *width, int *height)
{
    if (path == NULL || pixels == NULL || width == NULL || height == NULL) {
        return HORSE_DATA_ERR_IO;
    }
    *pixels = NULL;
    *width = 0;
    *height = 0;

    FILE *fp = fopen(path, "rb");
    if (fp == NULL) {
        return HORSE_DATA_ERR_IO;
    }
    fseek(fp, 0, SEEK_END);
    long sz = ftell(fp);
    if (sz <= 0 || sz > 64 * 1024 * 1024) {
        fclose(fp);
        return HORSE_DATA_ERR_IO;
    }
    rewind(fp);
    unsigned char *file_buf = (unsigned char *)malloc((size_t)sz);
    if (file_buf == NULL) {
        fclose(fp);
        return HORSE_DATA_ERR_IO;
    }
    if (fread(file_buf, 1, (size_t)sz, fp) != (size_t)sz) {
        free(file_buf);
        fclose(fp);
        return HORSE_DATA_ERR_IO;
    }
    fclose(fp);

    int w = 0;
    int h = 0;
    int comp = 0;
    unsigned char *rgba = stbi_load_from_memory(file_buf, (int)sz, &w, &h, &comp, 4);
    free(file_buf);
    if (rgba == NULL || w <= 0 || h <= 0) {
        if (rgba) {
            stbi_image_free(rgba);
        }
        return HORSE_DATA_ERR_PARSE;
    }

    size_t n = (size_t)w * (size_t)h;
    uint32_t *out = (uint32_t *)malloc(n * sizeof(uint32_t));
    if (out == NULL) {
        stbi_image_free(rgba);
        return HORSE_DATA_ERR_IO;
    }
    for (size_t i = 0; i < n; i++) {
        unsigned char r = rgba[i * 4 + 0];
        unsigned char g = rgba[i * 4 + 1];
        unsigned char b = rgba[i * 4 + 2];
        unsigned char a = rgba[i * 4 + 3];
        out[i] = ((uint32_t)a << 24) | ((uint32_t)r << 16) | ((uint32_t)g << 8) | (uint32_t)b;
    }
    stbi_image_free(rgba);
    *pixels = out;
    *width = w;
    *height = h;
    return HORSE_DATA_OK;
}

void horse_data_png_free(uint32_t *pixels)
{
    free(pixels);
}
