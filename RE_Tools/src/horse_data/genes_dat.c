#include "horse_data/genes_dat.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static HorseDataStatus genes_parse_buffer(const uint8_t *data, size_t len, HorseDataGeneFile *out)
{
    if (out == NULL || data == NULL || len < 8) {
        return HORSE_DATA_ERR_PARSE;
    }
    memset(out, 0, sizeof(*out));

    uint32_t count = 0;
    uint32_t first_len = 0;
    memcpy(&count, data, 4);
    memcpy(&first_len, data + 4, 4);
    out->gene_count = count;
    out->first_name_length = first_len;

    size_t offset = 8;
    for (uint32_t i = 0; i < count; i++) {
        if (out->entry_count >= HORSE_DATA_GENE_MAX) {
            return HORSE_DATA_ERR_PARSE;
        }
        uint32_t name_len = (i == 0) ? first_len : (uint32_t)out->entries[i - 1].next_name_length;
        if (name_len >= HORSE_DATA_GENE_NAME_MAX || offset + name_len > len) {
            return HORSE_DATA_ERR_TRUNCATED;
        }
        HorseDataGeneEntry *e = &out->entries[out->entry_count++];
        e->file_offset = (uint32_t)offset;
        memcpy(e->name, data + offset, name_len);
        e->name[name_len] = '\0';
        offset += name_len;
        e->next_name_length = -1;
        if (i + 1 < count) {
            if (offset + 4 > len) {
                return HORSE_DATA_ERR_TRUNCATED;
            }
            uint32_t next_len = 0;
            memcpy(&next_len, data + offset, 4);
            e->next_name_length = (int32_t)next_len;
            offset += 4;
        }
    }
    if (offset != len) {
        return HORSE_DATA_ERR_PARSE;
    }
    return HORSE_DATA_OK;
}

HorseDataStatus horse_data_genes_load_buffer(const uint8_t *data, size_t len, HorseDataGeneFile *out)
{
    return genes_parse_buffer(data, len, out);
}

HorseDataStatus horse_data_genes_load_file(const char *path, HorseDataGeneFile *out)
{
    if (path == NULL || out == NULL) {
        return HORSE_DATA_ERR_IO;
    }
    FILE *fp = fopen(path, "rb");
    if (fp == NULL) {
        return HORSE_DATA_ERR_IO;
    }
    if (fseek(fp, 0, SEEK_END) != 0) {
        fclose(fp);
        return HORSE_DATA_ERR_IO;
    }
    long sz = ftell(fp);
    if (sz < 0 || sz > 4 * 1024 * 1024) {
        fclose(fp);
        return HORSE_DATA_ERR_IO;
    }
    rewind(fp);
    uint8_t *buf = (uint8_t *)malloc((size_t)sz);
    if (buf == NULL) {
        fclose(fp);
        return HORSE_DATA_ERR_IO;
    }
    size_t n = fread(buf, 1, (size_t)sz, fp);
    fclose(fp);
    if (n != (size_t)sz) {
        free(buf);
        return HORSE_DATA_ERR_IO;
    }
    HorseDataStatus st = genes_parse_buffer(buf, n, out);
    free(buf);
    return st;
}
