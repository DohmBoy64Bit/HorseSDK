#include "horse_data/bmfont_txt.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void trim(char *s)
{
    size_t n = strlen(s);
    while (n > 0 && (s[n - 1] == '\r' || s[n - 1] == '\n' || s[n - 1] == ' ')) {
        s[--n] = '\0';
    }
}

HorseDataStatus horse_data_bmfont_load_file(const char *path, HorseDataBMFont *out)
{
    if (path == NULL || out == NULL) {
        return HORSE_DATA_ERR_IO;
    }
    memset(out, 0, sizeof(*out));
    FILE *fp = fopen(path, "r");
    if (fp == NULL) {
        return HORSE_DATA_ERR_IO;
    }
    char line[4096];
    while (fgets(line, sizeof(line), fp)) {
        trim(line);
        if (line[0] == '#' || line[0] == '\0') {
            continue;
        }
        char *eq = strchr(line, '=');
        if (eq == NULL) {
            continue;
        }
        *eq = '\0';
        char *key = line;
        char *val = eq + 1;
        trim(key);
        trim(val);
        if (strcmp(key, "name") == 0) {
            strncpy(out->name, val, sizeof(out->name) - 1);
        } else if (strcmp(key, "size") == 0) {
            out->size = (int32_t)strtol(val, NULL, 10);
        } else if (strcmp(key, "ascent") == 0) {
            out->ascent = (int32_t)strtol(val, NULL, 10);
        } else if (strcmp(key, "descent") == 0) {
            out->descent = (int32_t)strtol(val, NULL, 10);
        } else if (strcmp(key, "char_count") == 0) {
            out->char_count = (uint32_t)strtoul(val, NULL, 10);
        } else if (strcmp(key, "kerning_count") == 0) {
            out->kerning_count = (uint32_t)strtoul(val, NULL, 10);
        } else if (strcmp(key, "advance") == 0) {
            char *tok = strtok(val, ",");
            while (tok && out->advance_count < HORSE_DATA_BMFONT_ADVANCES_MAX) {
                out->advances[out->advance_count++] = (int32_t)strtol(tok, NULL, 10);
                tok = strtok(NULL, ",");
            }
        }
    }
    fclose(fp);
    return HORSE_DATA_OK;
}
