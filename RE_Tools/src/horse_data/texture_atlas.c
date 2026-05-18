#include "horse_data/texture_atlas.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const char *attr(const char *tag, const char *name, char *buf, size_t bufsz)
{
    char key[80];
    snprintf(key, sizeof(key), "%s=\"", name);
    const char *p = strstr(tag, key);
    if (p == NULL) {
        return NULL;
    }
    p += strlen(key);
    const char *end = strchr(p, '"');
    if (end == NULL) {
        return NULL;
    }
    size_t n = (size_t)(end - p);
    if (n >= bufsz) {
        n = bufsz - 1;
    }
    memcpy(buf, p, n);
    buf[n] = '\0';
    return buf;
}

HorseDataStatus horse_data_atlas_load_file(const char *path, HorseDataTextureAtlas *out)
{
    if (path == NULL || out == NULL) {
        return HORSE_DATA_ERR_IO;
    }
    memset(out, 0, sizeof(*out));
    FILE *fp = fopen(path, "rb");
    if (fp == NULL) {
        return HORSE_DATA_ERR_IO;
    }
    fseek(fp, 0, SEEK_END);
    long sz = ftell(fp);
    if (sz <= 0 || sz > 8 * 1024 * 1024) {
        fclose(fp);
        return HORSE_DATA_ERR_IO;
    }
    rewind(fp);
    char *text = (char *)malloc((size_t)sz + 1);
    if (text == NULL) {
        fclose(fp);
        return HORSE_DATA_ERR_IO;
    }
    fread(text, 1, (size_t)sz, fp);
    fclose(fp);
    text[sz] = '\0';

    if (strstr(text, "<TextureAtlas") == NULL) {
        free(text);
        return HORSE_DATA_ERR_PARSE;
    }

    const char *scan = text;
    while (out->sprite_count < HORSE_DATA_ATLAS_SPRITES_MAX) {
        const char *sp = strstr(scan, "<sprite");
        if (sp == NULL) {
            break;
        }
        const char *end = strchr(sp, '>');
        if (end == NULL) {
            break;
        }
        char tag[512];
        size_t len = (size_t)(end - sp + 1);
        if (len >= sizeof(tag)) {
            len = sizeof(tag) - 1;
        }
        memcpy(tag, sp, len);
        tag[len] = '\0';

        HorseDataAtlasSprite *S = &out->sprites[out->sprite_count++];
        char buf[64];
        if (attr(tag, "n", S->name, sizeof(S->name)) == NULL) {
            attr(tag, "name", S->name, sizeof(S->name));
        }
        S->x = attr(tag, "x", buf, sizeof(buf)) ? (int32_t)strtol(buf, NULL, 10) : 0;
        S->y = attr(tag, "y", buf, sizeof(buf)) ? (int32_t)strtol(buf, NULL, 10) : 0;
        S->width = attr(tag, "w", buf, sizeof(buf)) ? (int32_t)strtol(buf, NULL, 10) : 0;
        S->height = attr(tag, "h", buf, sizeof(buf)) ? (int32_t)strtol(buf, NULL, 10) : 0;
        S->frame_count = attr(tag, "c", buf, sizeof(buf)) ? (int32_t)strtol(buf, NULL, 10) : -1;
        scan = end + 1;
    }

    free(text);
    return HORSE_DATA_OK;
}
