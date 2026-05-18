#include "horse_save.h"
#include "horse_save_stream.h"

#include <string.h>

#define GRID_PREFIX_BYTES 802u
#define GRID_STREAM_BYTES 52664u
#define GRID_PAD_BYTES 876u
#define MAIN_NESTED_FILE_OFF 57035u
#define FOOTER_FILE_OFF 203545u
#define FOOTER_BYTES 841u
/* Sample save1.dat — from save_footer_layout.json trace */
#define FOOTER_OFF_WORLD_VEC2 343u
#define FOOTER_OFF_CAMERA_VEC2 394u
#define FOOTER_OFF_TRACK_LEN 359u
#define FOOTER_GENE_SETTINGS_OFF 0x31B41u
#define FOOTER_GENE_TRACK_OFF 0x31CE6u
/* FooterExtra_Write @ 0x1017C0 — rel 833 in 841 B blob (decode_footer_extra_wire.py) */
#define FOOTER_OFF_EXTRA 833u
#define FOOTER_EXTRA_BYTES 7u

static HorseSaveStatus read_std_string(
    HorseSaveStream *s,
    char *out,
    size_t out_cap,
    uint32_t *name_len) {
    uint32_t n = 0;
    HorseSaveStatus st = horse_save_read_u32(s, &n);
    if (st != HORSE_SAVE_OK) {
        return st;
    }
    if (name_len) {
        *name_len = n;
    }
    if (n == 0) {
        if (out_cap) {
            out[0] = '\0';
        }
        return HORSE_SAVE_OK;
    }
    if (n >= out_cap || s->pos + n > s->size) {
        return HORSE_SAVE_ERR_TRUNCATED;
    }
    memcpy(out, s->data + s->pos, n);
    out[n < out_cap ? n : out_cap - 1] = '\0';
    s->pos += n;
    return HORSE_SAVE_OK;
}

HorseSaveStatus horse_save_unpack_type0_packed(uint8_t packed, HorseSaveType0Packed *out) {
    if (!out) {
        return HORSE_SAVE_ERR_PARSE;
    }
    out->packed = packed;
    out->dword_38 = (int32_t)((packed & 7u) - 1u);
    out->flag_10 = (uint8_t)((packed >> 3) & 1u);
    out->flag_11 = (uint8_t)((packed >> 4) & 1u);
    return HORSE_SAVE_OK;
}

static uint32_t type1_payload_end(const uint8_t *blob, uint32_t len) {
    uint32_t limit = len < 256u ? len : 256u;
    for (uint32_t pos = 4; pos + HORSE_SAVE_B8_TYPE2_BLOCK <= len && pos < limit; ++pos) {
        uint32_t tag = 0;
        memcpy(&tag, blob + pos, 4);
        if (tag == 2u) {
            return pos;
        }
    }
    return len < 61u ? len : 61u;
}

HorseSaveStatus horse_save_parse_main_nested(HorseSaveFile *sf) {
    if (!sf || !sf->data) {
        return HORSE_SAVE_ERR_PARSE;
    }
    memset(&sf->main_nested, 0, sizeof(sf->main_nested));
    sf->has_main_nested = 0;

    if (sf->size < MAIN_NESTED_FILE_OFF + HORSE_SAVE_MAIN_NESTED_BYTES) {
        return HORSE_SAVE_ERR_TRUNCATED;
    }

    HorseSaveStream s;
    horse_save_stream_init(&s, sf->data, sf->size);
    s.pos = MAIN_NESTED_FILE_OFF;

    HorseSaveStatus st = read_std_string(&s, sf->main_nested.name, sizeof(sf->main_nested.name), NULL);
    if (st != HORSE_SAVE_OK) {
        return st;
    }

    uint32_t ptr = 0, merge = 0;
    st = horse_save_read_u32(&s, &ptr);
    if (st != HORSE_SAVE_OK) {
        return st;
    }
    st = horse_save_read_u32(&s, &merge);
    if (st != HORSE_SAVE_OK) {
        return st;
    }
    st = horse_save_read_u32(&s, &sf->main_nested.b8_header_count);
    if (st != HORSE_SAVE_OK) {
        return st;
    }

    if (s.pos + HORSE_SAVE_B8_BLOB_BYTES > sf->size) {
        return HORSE_SAVE_ERR_TRUNCATED;
    }

  {
    const uint8_t *blob = sf->data + s.pos;
    uint32_t pos = 0;
    uint32_t on_disk = 0;

    sf->main_nested.file_offset = MAIN_NESTED_FILE_OFF;
    sf->main_nested.b8_blob_bytes = HORSE_SAVE_B8_BLOB_BYTES;

    if (HORSE_SAVE_B8_BLOB_BYTES >= 4) {
        uint32_t tag = 0;
        memcpy(&tag, blob, 4);
        if (tag == 1u) {
            sf->main_nested.type1_records = 1;
            pos = type1_payload_end(blob, HORSE_SAVE_B8_BLOB_BYTES);
        }
    }

    while (pos + HORSE_SAVE_B8_TYPE2_BLOCK <= HORSE_SAVE_B8_BLOB_BYTES) {
        uint32_t tag = 0;
        memcpy(&tag, blob + pos, 4);
        if (tag != 2u) {
            break;
        }
        sf->main_nested.type2_blocks += 1u;
        pos += HORSE_SAVE_B8_TYPE2_BLOCK;
    }
    sf->main_nested.type2_inners = sf->main_nested.type2_blocks * 4u;

    if (pos < HORSE_SAVE_B8_BLOB_BYTES) {
        sf->main_nested.type0_tail_bytes = HORSE_SAVE_B8_BLOB_BYTES - pos;
    }

    on_disk = sf->main_nested.type1_records + sf->main_nested.type2_inners
              + sf->main_nested.type0_tail_bytes;

    sf->main_nested.on_disk_slots = on_disk;
    if (sf->main_nested.b8_header_count > on_disk) {
        sf->main_nested.implicit_eof_slots = sf->main_nested.b8_header_count - on_disk;
    }
  }

    sf->has_main_nested = 1;
    return HORSE_SAVE_OK;
}

HorseSaveStatus horse_save_parse_grid_summary(HorseSaveFile *sf) {
    if (!sf || !sf->data) {
        return HORSE_SAVE_ERR_PARSE;
    }
    memset(&sf->grid, 0, sizeof(sf->grid));
    sf->grid.width = sf->grid_width;
    sf->grid.height = sf->grid_height;
    sf->grid.cells_expected = sf->grid_width * sf->grid_height;
    sf->grid.prefix_bytes = GRID_PREFIX_BYTES;
    sf->grid.stream_bytes = GRID_STREAM_BYTES;
    sf->grid.pad_bytes = GRID_PAD_BYTES;

    if (sf->size < HORSE_SAVE_OFF_GRID_DIM_END) {
        return HORSE_SAVE_ERR_TRUNCATED;
    }

    const uint8_t *grid = sf->data + HORSE_SAVE_OFF_GRID_DIM_END + GRID_PREFIX_BYTES;
    size_t grid_len = (size_t)GRID_STREAM_BYTES;
    if (HORSE_SAVE_OFF_GRID_DIM_END + grid_len > sf->size) {
        return HORSE_SAVE_ERR_TRUNCATED;
    }

    size_t pos = 0;
    size_t skip_run = 0;
    uint32_t cells = 0;
    uint32_t type6 = 0;

    /* Mirror Save_Load grid index loop @ 0x6E700: always width*height cells.
     * Stream may end with a pending 0x3F skip run (150 cells in save1) plus a short
     * tail of implicit type-6 slots — see decode_grid_cells.py / disasm_save_grid.txt */
    while (cells < sf->grid.cells_expected) {
        if (skip_run > 0) {
            type6 += 1;
            skip_run -= 1;
            cells += 1;
            continue;
        }
        if (pos >= grid_len) {
            type6 += 1;
            cells += 1;
            continue;
        }
        uint8_t b = grid[pos++];
        if (b == 0x3Fu) {
            if (pos >= grid_len) {
                skip_run = 0;
            } else {
                uint8_t b2 = grid[pos++];
                skip_run = b2 > 0 ? (size_t)(b2 - 1u) : 0u;
            }
            type6 += 1;
            cells += 1;
            continue;
        }
        if (b >= 0x3Bu && b <= 0x3Eu) {
            cells += 1;
            continue;
        }
        if (pos >= grid_len) {
            cells += 1;
            continue;
        }
        pos += 1;
        cells += 1;
    }

    sf->grid.cells_decoded = cells;
    sf->grid.stream_bytes = (uint32_t)(pos <= grid_len ? pos : grid_len);
    sf->grid.type6_cells = type6;
    sf->has_grid = 1;
    return HORSE_SAVE_OK;
}

const HorseSaveMainNested *horse_save_get_main_nested(const HorseSaveFile *sf) {
    if (!sf || !sf->has_main_nested) {
        return NULL;
    }
    return &sf->main_nested;
}

const HorseSaveGridSummary *horse_save_get_grid_summary(const HorseSaveFile *sf) {
    if (!sf || !sf->has_grid) {
        return NULL;
    }
    return &sf->grid;
}

static void footer_scan_strings(const uint8_t *blob, uint32_t len, HorseSaveFooter *out) {
    uint32_t pos = 0;
    while (pos + 4 <= len) {
        uint32_t n = 0;
        memcpy(&n, blob + pos, 4);
        if (n == 0 || n >= sizeof(out->track_display_name)) {
            pos += 1;
            continue;
        }
        if (pos + 4 + n > len) {
            break;
        }
        const char *text = (const char *)(blob + pos + 4);
        if (n >= 4 && text[0] >= 32 && text[0] < 127) {
            if (out->track_display_name[0] == '\0' || n > 10) {
                memcpy(out->track_display_name, text, n);
                out->track_display_name[n < 63 ? n : 63] = '\0';
            }
        }
        pos += 4 + n;
    }
}

HorseSaveStatus horse_save_parse_footer(HorseSaveFile *sf) {
    if (!sf || !sf->data) {
        return HORSE_SAVE_ERR_PARSE;
    }
    memset(&sf->footer, 0, sizeof(sf->footer));
    sf->has_footer = 0;

    if (sf->size < FOOTER_FILE_OFF + FOOTER_BYTES) {
        return HORSE_SAVE_ERR_TRUNCATED;
    }

    const uint8_t *blob = sf->data + FOOTER_FILE_OFF;
    sf->footer.file_offset = FOOTER_FILE_OFF;
    sf->footer.byte_size = FOOTER_BYTES;

    if (FOOTER_OFF_WORLD_VEC2 + 8 <= FOOTER_BYTES) {
        memcpy(sf->footer.world_vec2, blob + FOOTER_OFF_WORLD_VEC2, 8);
    }
    if (FOOTER_OFF_CAMERA_VEC2 + 8 <= FOOTER_BYTES) {
        memcpy(sf->footer.camera_vec2, blob + FOOTER_OFF_CAMERA_VEC2, 8);
    }
    if (FOOTER_OFF_TRACK_LEN + 4 <= FOOTER_BYTES) {
        uint32_t n = 0;
        memcpy(&n, blob + FOOTER_OFF_TRACK_LEN, 4);
        if (n > 0 && n < sizeof(sf->footer.track_display_name)
            && FOOTER_OFF_TRACK_LEN + 4 + n <= FOOTER_BYTES) {
            memcpy(sf->footer.track_display_name, blob + FOOTER_OFF_TRACK_LEN + 4, n);
            sf->footer.track_display_name[n < 63 ? n : 63] = '\0';
        }
    }

    if (sf->footer.track_display_name[0] == '\0') {
        footer_scan_strings(blob, FOOTER_BYTES, &sf->footer);
    }

    sf->footer.gene_settings_offset = FOOTER_GENE_SETTINGS_OFF;
    sf->footer.gene_track_offset = FOOTER_GENE_TRACK_OFF;
    if (FOOTER_GENE_SETTINGS_OFF + HORSE_SAVE_GENE_PACK_BYTES <= FOOTER_FILE_OFF + FOOTER_BYTES) {
        const uint8_t *packed = sf->data + FOOTER_GENE_SETTINGS_OFF;
        if (horse_save_gene_unpack(packed, &sf->footer.gene_settings) == HORSE_SAVE_OK) {
            sf->footer.has_gene_settings = 1;
        }
    }
    if (FOOTER_GENE_TRACK_OFF + HORSE_SAVE_GENE_PACK_BYTES <= FOOTER_FILE_OFF + FOOTER_BYTES) {
        const uint8_t *packed = sf->data + FOOTER_GENE_TRACK_OFF;
        if (horse_save_gene_unpack(packed, &sf->footer.gene_track) == HORSE_SAVE_OK) {
            sf->footer.has_gene_track = 1;
        }
    }

    if (FOOTER_OFF_EXTRA + FOOTER_EXTRA_BYTES <= FOOTER_BYTES) {
        const uint8_t *ex = blob + FOOTER_OFF_EXTRA;
        memcpy(&sf->footer.extra.dword_25c, ex, 4);
        sf->footer.extra.byte_261 = ex[4];
        sf->footer.extra.byte_262 = ex[5];
        sf->footer.extra.byte_263 = ex[6];
        sf->footer.has_footer_extra = 1;
    }

    sf->has_footer = 1;
    return HORSE_SAVE_OK;
}

const HorseSaveFooter *horse_save_get_footer(const HorseSaveFile *sf) {
    if (!sf || !sf->has_footer) {
        return NULL;
    }
    return &sf->footer;
}
