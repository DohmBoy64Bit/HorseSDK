/**
 * Save write @ Horsey.exe Save_Write 0x6DAB0 — byte-preserving round-trip.
 *
 * Mirrors save_file_codec.write_save_bytes: re-emits loaded buffer unchanged.
 * Verified: save_write_codec.py match on save_buffer_dump.bin.
 */
#include "horse_save.h"
#include "horse_save_stream.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static HorseSaveStatus append_slice(
    HorseSaveOut *o,
    const HorseSaveFile *sf,
    size_t off,
    size_t len) {
    if (off + len > sf->size) {
        return HORSE_SAVE_ERR_TRUNCATED;
    }
    return horse_save_out_write(o, sf->data + off, len);
}

/**
 * Section-ordered write matching Save_Write @ 0x6DAB0 (format v12).
 * Uses on-disk slices from loaded file — same layout as Python write_save_bytes raw path.
 */
HorseSaveStatus horse_save_write_structured(
    const HorseSaveFile *sf,
    uint8_t **out_data,
    size_t *out_len) {
    if (!sf || !out_data || !out_len || !sf->data) {
        return HORSE_SAVE_ERR_PARSE;
    }
    HorseSaveOut o;
    horse_save_out_init(&o);
    HorseSaveStatus st = HORSE_SAVE_OK;

    st = append_slice(&o, sf, 0, HORSE_SAVE_OFF_GLOBALS_END);
    if (st == HORSE_SAVE_OK) {
        st = append_slice(
            &o,
            sf,
            HORSE_SAVE_OFF_GLOBALS_END,
            HORSE_SAVE_OFF_CTX_END - HORSE_SAVE_OFF_GLOBALS_END);
    }
    if (st == HORSE_SAVE_OK) {
        st = append_slice(
            &o,
            sf,
            HORSE_SAVE_OFF_CTX_END,
            HORSE_SAVE_OFF_GRID_DIM_END - HORSE_SAVE_OFF_CTX_END);
    }
    if (st == HORSE_SAVE_OK) {
        st = append_slice(
            &o,
            sf,
            HORSE_SAVE_OFF_GRID_DIM_END,
            HORSE_SAVE_OFF_GRID_END - HORSE_SAVE_OFF_GRID_DIM_END);
    }
    if (st == HORSE_SAVE_OK) {
        st = append_slice(
            &o,
            sf,
            HORSE_SAVE_OFF_GRID_END,
            HORSE_SAVE_OFF_PAIRS_END - HORSE_SAVE_OFF_GRID_END);
    }
    if (st == HORSE_SAVE_OK) {
        st = append_slice(
            &o,
            sf,
            HORSE_SAVE_OFF_PAIRS_END,
            HORSE_SAVE_MAIN_NESTED_BYTES);
    }
    if (st == HORSE_SAVE_OK) {
        size_t inv_off =
            sf->inventory_offset ? sf->inventory_offset : HORSE_SAVE_OFF_INVENTORY_DEFAULT;
        size_t inv_end =
            sf->inventory_end ? sf->inventory_end : HORSE_SAVE_OFF_INVENTORY_END_DEFAULT;
        if (inv_end > inv_off) {
            st = append_slice(&o, sf, inv_off, inv_end - inv_off);
        }
        if (st == HORSE_SAVE_OK && sf->size > inv_end) {
            st = append_slice(&o, sf, inv_end, sf->size - inv_end);
        }
    }

    if (st != HORSE_SAVE_OK) {
        horse_save_out_free(&o);
        return st;
    }
    *out_data = o.data;
    *out_len = o.size;
    o.data = NULL;
    o.cap = 0;
    o.size = 0;
    return HORSE_SAVE_OK;
}

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
