/**
 * Save write @ Horsey.exe Save_Write 0x6DAB0 — byte-preserving round-trip.
 *
 * Mirrors save_file_codec.write_save_bytes: re-emits loaded buffer unchanged.
 * Verified: save_write_codec.py match on save_buffer_dump.bin.
 */
#include "horse_save.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

HorseSaveStatus horse_save_write_buffer(
    const HorseSaveFile *sf,
    uint8_t **out_data,
    size_t *out_len) {
    if (!sf || !out_data || !out_len) {
        return HORSE_SAVE_ERR_PARSE;
    }
    if (!sf->data || sf->size == 0) {
        return HORSE_SAVE_ERR_PARSE;
    }
    uint8_t *copy = (uint8_t *)malloc(sf->size);
    if (!copy) {
        return HORSE_SAVE_ERR_IO;
    }
    memcpy(copy, sf->data, sf->size);
    *out_data = copy;
    *out_len = sf->size;
    return HORSE_SAVE_OK;
}

HorseSaveStatus horse_save_write_path(const HorseSaveFile *sf, const char *path) {
    if (!sf || !path) {
        return HORSE_SAVE_ERR_PARSE;
    }
    uint8_t *buf = NULL;
    size_t len = 0;
    HorseSaveStatus st = horse_save_write_buffer(sf, &buf, &len);
    if (st != HORSE_SAVE_OK) {
        return st;
    }
    FILE *fp = fopen(path, "wb");
    if (!fp) {
        free(buf);
        return HORSE_SAVE_ERR_IO;
    }
    if (fwrite(buf, 1, len, fp) != len) {
        fclose(fp);
        free(buf);
        return HORSE_SAVE_ERR_IO;
    }
    fclose(fp);
    free(buf);
    return HORSE_SAVE_OK;
}
