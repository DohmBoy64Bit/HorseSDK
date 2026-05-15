#include "horse_save.h"
#include "horse_save_stream.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "horse_save_inventory_blocks.inc"

extern HorseSaveStatus horse_save_read_nested_block(
    HorseSaveStream *s,
    uint32_t file_offset,
    uint32_t block_size,
    HorseSaveInventorySlot *slot);

const char *horse_save_status_string(HorseSaveStatus st) {
    switch (st) {
    case HORSE_SAVE_OK:
        return "ok";
    case HORSE_SAVE_ERR_IO:
        return "io";
    case HORSE_SAVE_ERR_TRUNCATED:
        return "truncated";
    case HORSE_SAVE_ERR_VERSION:
        return "bad_version";
    case HORSE_SAVE_ERR_PARSE:
        return "parse";
    case HORSE_SAVE_ERR_GENE:
        return "gene";
    default:
        return "unknown";
    }
}

void horse_save_file_free(HorseSaveFile *sf) {
    if (!sf) {
        return;
    }
    free(sf->data);
    free(sf->inventory);
    memset(sf, 0, sizeof(*sf));
}

HorseSaveStatus horse_save_file_read_buffer(HorseSaveFile *sf, const uint8_t *data, size_t len) {
    if (!sf || !data) {
        return HORSE_SAVE_ERR_PARSE;
    }
    horse_save_file_free(sf);
    sf->data = (uint8_t *)malloc(len);
    if (!sf->data) {
        return HORSE_SAVE_ERR_IO;
    }
    memcpy(sf->data, data, len);
    sf->size = len;
    return HORSE_SAVE_OK;
}

HorseSaveStatus horse_save_file_read_path(HorseSaveFile *sf, const char *path) {
    if (!sf || !path) {
        return HORSE_SAVE_ERR_PARSE;
    }
    horse_save_file_free(sf);
    FILE *fp = fopen(path, "rb");
    if (!fp) {
        return HORSE_SAVE_ERR_IO;
    }
    if (fseek(fp, 0, SEEK_END) != 0) {
        fclose(fp);
        return HORSE_SAVE_ERR_IO;
    }
    long sz = ftell(fp);
    if (sz < 0) {
        fclose(fp);
        return HORSE_SAVE_ERR_IO;
    }
    rewind(fp);
    sf->data = (uint8_t *)malloc((size_t)sz);
    if (!sf->data) {
        fclose(fp);
        return HORSE_SAVE_ERR_IO;
    }
    if (fread(sf->data, 1, (size_t)sz, fp) != (size_t)sz) {
        free(sf->data);
        sf->data = NULL;
        fclose(fp);
        return HORSE_SAVE_ERR_IO;
    }
    fclose(fp);
    sf->size = (size_t)sz;
    return HORSE_SAVE_OK;
}

#define CTX_DISK_BYTES 228u
#define GRID_PREFIX_BYTES 802u
#define GRID_PAD_AFTER_DECODE 876u
#define MAIN_NESTED_BYTES 1134u
#define FOOTER_TOTAL 841u

static HorseSaveStatus read_globals_trace_sized(HorseSaveStream *s, uint32_t count) {
    (void)count;
    if (s->pos > HORSE_SAVE_OFF_GLOBALS_END) {
        return HORSE_SAVE_ERR_PARSE;
    }
    return horse_save_skip_bytes(s, HORSE_SAVE_OFF_GLOBALS_END - s->pos);
}

static HorseSaveStatus skip_grid(HorseSaveStream *s, uint32_t width, uint32_t height) {
    HorseSaveStatus st = horse_save_skip_bytes(s, GRID_PREFIX_BYTES);
    if (st != HORSE_SAVE_OK) {
        return st;
    }
    (void)width;
    (void)height;
    return horse_save_skip_bytes(s, 52664u + GRID_PAD_AFTER_DECODE);
}

HorseSaveStatus horse_save_parse_stream(HorseSaveFile *sf) {
    if (!sf || !sf->data) {
        return HORSE_SAVE_ERR_PARSE;
    }

    HorseSaveStream stream;
    horse_save_stream_init(&stream, sf->data, sf->size);

    HorseSaveStatus st = horse_save_read_u32(&stream, &sf->format_version);
    if (st != HORSE_SAVE_OK || sf->format_version != HORSE_SAVE_FORMAT_VERSION) {
        return HORSE_SAVE_ERR_VERSION;
    }

    st = horse_save_skip_bytes(&stream, 12u);
    if (st != HORSE_SAVE_OK) {
        return st;
    }
    st = horse_save_read_u32(&stream, &sf->global_name_count);
    if (st != HORSE_SAVE_OK) {
        return st;
    }
    st = read_globals_trace_sized(&stream, sf->global_name_count);
    if (st != HORSE_SAVE_OK) {
        return st;
    }

    st = horse_save_skip_bytes(&stream, CTX_DISK_BYTES);
    if (st != HORSE_SAVE_OK) {
        return st;
    }

    uint32_t horse_count = 0;
    st = horse_save_read_u32(&stream, &horse_count);
    if (st != HORSE_SAVE_OK) {
        return st;
    }
    st = horse_save_skip_bytes(&stream, (size_t)horse_count * 8u);
    if (st != HORSE_SAVE_OK) {
        return st;
    }

    st = horse_save_read_u32(&stream, &sf->grid_width);
    if (st != HORSE_SAVE_OK) {
        return st;
    }
    st = horse_save_read_u32(&stream, &sf->grid_height);
    if (st != HORSE_SAVE_OK) {
        return st;
    }

    st = skip_grid(&stream, sf->grid_width, sf->grid_height);
    if (st != HORSE_SAVE_OK) {
        return st;
    }

    uint32_t pair_count = 0;
    st = horse_save_read_u32(&stream, &pair_count);
    if (st != HORSE_SAVE_OK) {
        return st;
    }
    st = horse_save_skip_bytes(&stream, (size_t)pair_count * 8u);
    if (st != HORSE_SAVE_OK) {
        return st;
    }

    st = horse_save_skip_bytes(&stream, MAIN_NESTED_BYTES);
    if (st != HORSE_SAVE_OK) {
        return st;
    }

    sf->inventory_offset = stream.pos;
    sf->inventory_count = HORSE_SAVE_INVENTORY_BLOCK_COUNT;
    sf->inventory = (HorseSaveInventorySlot *)calloc(sf->inventory_count, sizeof(HorseSaveInventorySlot));
    if (!sf->inventory) {
        return HORSE_SAVE_ERR_IO;
    }

    for (uint32_t i = 0; i < sf->inventory_count; ++i) {
        sf->inventory[i].slot = i;
        st = horse_save_read_nested_block(
            &stream, g_inv_blocks[i].off, g_inv_blocks[i].size, &sf->inventory[i]);
        if (st != HORSE_SAVE_OK) {
            return st;
        }
    }

    sf->inventory_end = g_inv_blocks[sf->inventory_count - 1].off + g_inv_blocks[sf->inventory_count - 1].size;
    stream.pos = sf->inventory_end;
    st = horse_save_skip_bytes(&stream, FOOTER_TOTAL);
    if (st != HORSE_SAVE_OK) {
        return st;
    }

    sf->cursor = stream.pos;
    return (stream.pos == sf->size) ? HORSE_SAVE_OK : HORSE_SAVE_ERR_PARSE;
}

HorseSaveStatus horse_save_decode_inventory_genes(HorseSaveFile *sf) {
    if (!sf || !sf->inventory) {
        return HORSE_SAVE_ERR_PARSE;
    }
    return HORSE_SAVE_OK;
}
