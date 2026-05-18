#include "horse_data/tmx_map.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const char *find_attr(const char *tag, const char *attr, char *buf, size_t bufsz)
{
    char key[64];
    snprintf(key, sizeof(key), "%s=\"", attr);
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

static uint32_t parse_u32_attr(const char *tag, const char *attr, uint32_t def)
{
    char buf[32];
    if (find_attr(tag, attr, buf, sizeof(buf)) == NULL) {
        return def;
    }
    return (uint32_t)strtoul(buf, NULL, 10);
}

static int parse_csv_layer(const char *csv, uint32_t w, uint32_t h, uint32_t *cells)
{
    uint32_t need = w * h;
    uint32_t idx = 0;
    const char *p = csv;
    while (*p && idx < need) {
        while (*p == ',' || *p == '\n' || *p == '\r' || *p == ' ') {
            p++;
        }
        if (!*p) {
            break;
        }
        cells[idx++] = (uint32_t)strtoul(p, (char **)&p, 10);
    }
    return idx == need;
}

HorseDataStatus horse_data_tmx_load_file(const char *path, HorseDataTmxMap *out)
{
    if (path == NULL || out == NULL) {
        return HORSE_DATA_ERR_IO;
    }
    memset(out, 0, sizeof(*out));

    FILE *fp = fopen(path, "rb");
    if (fp == NULL) {
        return HORSE_DATA_ERR_IO;
    }
    if (fseek(fp, 0, SEEK_END) != 0) {
        fclose(fp);
        return HORSE_DATA_ERR_IO;
    }
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
    size_t n = fread(text, 1, (size_t)sz, fp);
    fclose(fp);
    text[n] = '\0';

    const char *map_tag = strstr(text, "<map ");
    if (map_tag == NULL) {
        free(text);
        return HORSE_DATA_ERR_PARSE;
    }
    out->width = parse_u32_attr(map_tag, "width", 0);
    out->height = parse_u32_attr(map_tag, "height", 0);
    out->tile_width = parse_u32_attr(map_tag, "tilewidth", 0);
    out->tile_height = parse_u32_attr(map_tag, "tileheight", 0);

    const char *scan = text;
    while (out->layer_count < HORSE_DATA_TMX_LAYERS_MAX) {
        const char *layer = strstr(scan, "<layer ");
        if (layer == NULL) {
            break;
        }
        HorseDataTmxLayer *L = &out->layers[out->layer_count];
        memset(L, 0, sizeof(*L));
        find_attr(layer, "name", L->name, sizeof(L->name));
        L->width = parse_u32_attr(layer, "width", out->width);
        L->height = parse_u32_attr(layer, "height", out->height);
        uint32_t need = L->width * L->height;
        if (need == 0 || need > HORSE_DATA_TMX_CELLS_MAX) {
            free(text);
            return HORSE_DATA_ERR_PARSE;
        }
        L->cells = (uint32_t *)calloc(need, sizeof(uint32_t));
        if (L->cells == NULL) {
            free(text);
            horse_data_tmx_free(out);
            return HORSE_DATA_ERR_IO;
        }
        const char *data_tag = strstr(layer, "<data");
        if (data_tag == NULL || strstr(data_tag, "encoding=\"csv\"") == NULL) {
            out->layer_count++;
            scan = layer + 6;
            continue;
        }
        const char *csv = strchr(data_tag, '>');
        if (csv == NULL) {
            free(text);
            horse_data_tmx_free(out);
            return HORSE_DATA_ERR_PARSE;
        }
        csv++;
        const char *end = strstr(csv, "</data>");
        if (end == NULL) {
            free(text);
            horse_data_tmx_free(out);
            return HORSE_DATA_ERR_PARSE;
        }
        char *csv_buf = (char *)malloc((size_t)(end - csv) + 1);
        if (csv_buf == NULL) {
            free(text);
            horse_data_tmx_free(out);
            return HORSE_DATA_ERR_IO;
        }
        memcpy(csv_buf, csv, (size_t)(end - csv));
        csv_buf[end - csv] = '\0';
        if (!parse_csv_layer(csv_buf, L->width, L->height, L->cells)) {
            free(csv_buf);
            free(text);
            horse_data_tmx_free(out);
            return HORSE_DATA_ERR_PARSE;
        }
        free(csv_buf);
        out->layer_count++;
        scan = end;
    }

    free(text);
    return HORSE_DATA_OK;
}

void horse_data_tmx_free(HorseDataTmxMap *map)
{
    if (map == NULL) {
        return;
    }
    for (uint32_t i = 0; i < map->layer_count; i++) {
        free(map->layers[i].cells);
        map->layers[i].cells = NULL;
    }
    map->layer_count = 0;
}
