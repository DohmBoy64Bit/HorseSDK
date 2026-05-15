#include "horse_save_stream.h"

#include <stdlib.h>
#include <string.h>

void horse_save_stream_init(HorseSaveStream *s, const uint8_t *data, size_t len) {
    s->data = data;
    s->size = len;
    s->pos = 0;
}

static HorseSaveStatus need(const HorseSaveStream *s, size_t n) {
    if (s->pos + n > s->size) {
        return HORSE_SAVE_ERR_TRUNCATED;
    }
    return HORSE_SAVE_OK;
}

HorseSaveStatus horse_save_read_u8(HorseSaveStream *s, uint8_t *out) {
    HorseSaveStatus st = need(s, 1);
    if (st != HORSE_SAVE_OK) {
        return st;
    }
    *out = s->data[s->pos++];
    return HORSE_SAVE_OK;
}

HorseSaveStatus horse_save_read_u16(HorseSaveStream *s, uint16_t *out) {
    HorseSaveStatus st = need(s, 2);
    if (st != HORSE_SAVE_OK) {
        return st;
    }
    *out = (uint16_t)(s->data[s->pos] | ((uint16_t)s->data[s->pos + 1] << 8));
    s->pos += 2;
    return HORSE_SAVE_OK;
}

HorseSaveStatus horse_save_read_u32(HorseSaveStream *s, uint32_t *out) {
    HorseSaveStatus st = need(s, 4);
    if (st != HORSE_SAVE_OK) {
        return st;
    }
    *out = (uint32_t)s->data[s->pos] | ((uint32_t)s->data[s->pos + 1] << 8) |
           ((uint32_t)s->data[s->pos + 2] << 16) | ((uint32_t)s->data[s->pos + 3] << 24);
    s->pos += 4;
    return HORSE_SAVE_OK;
}

HorseSaveStatus horse_save_read_f32(HorseSaveStream *s, float *out) {
    uint32_t bits = 0;
    HorseSaveStatus st = horse_save_read_u32(s, &bits);
    if (st != HORSE_SAVE_OK) {
        return st;
    }
    memcpy(out, &bits, sizeof(float));
    return HORSE_SAVE_OK;
}

HorseSaveStatus horse_save_read_bytes(HorseSaveStream *s, uint8_t *dst, size_t n) {
    HorseSaveStatus st = need(s, n);
    if (st != HORSE_SAVE_OK) {
        return st;
    }
    memcpy(dst, s->data + s->pos, n);
    s->pos += n;
    return HORSE_SAVE_OK;
}

HorseSaveStatus horse_save_skip_bytes(HorseSaveStream *s, size_t n) {
    HorseSaveStatus st = need(s, n);
    if (st != HORSE_SAVE_OK) {
        return st;
    }
    s->pos += n;
    return HORSE_SAVE_OK;
}

HorseSaveStatus horse_save_read_string(HorseSaveStream *s, char *buf, size_t buf_cap, uint32_t *out_len) {
    uint32_t n = 0;
    HorseSaveStatus st = horse_save_read_u32(s, &n);
    if (st != HORSE_SAVE_OK) {
        return st;
    }
    if (out_len) {
        *out_len = n;
    }
    st = need(s, n);
    if (st != HORSE_SAVE_OK) {
        return st;
    }
    if (buf && buf_cap > 0) {
        size_t copy = n;
        if (copy >= buf_cap) {
            copy = buf_cap - 1;
        }
        memcpy(buf, s->data + s->pos, copy);
        buf[copy] = '\0';
    }
    s->pos += n;
    return HORSE_SAVE_OK;
}

/* Grid read @ 0x6E700 — see decode_grid_cells.py (index = width*height, not stream EOF) */
HorseSaveStatus horse_save_skip_grid(HorseSaveStream *s, uint32_t width, uint32_t height) {
    uint64_t target = (uint64_t)width * (uint64_t)height;
    uint64_t cells = 0;
    uint64_t skip_run = 0;

    while (cells < target) {
        if (skip_run > 0) {
            skip_run -= 1;
            cells += 1;
            continue;
        }

        uint8_t b = 0;
        HorseSaveStatus st = horse_save_read_u8(s, &b);
        if (st != HORSE_SAVE_OK) {
            cells += 1;
            continue;
        }

        if (b == 0x3F) {
            uint8_t run = 0;
            st = horse_save_read_u8(s, &run);
            if (st != HORSE_SAVE_OK) {
                skip_run = 0;
            } else {
                skip_run = run > 0 ? (uint64_t)(run - 1) : 0;
            }
            cells += 1;
            continue;
        }

        if (b >= 0x3B && b <= 0x3E) {
            cells += 1;
            continue;
        }

        st = horse_save_read_u8(s, &b);
        if (st != HORSE_SAVE_OK) {
            cells += 1;
            continue;
        }
        cells += 1;
    }
    return HORSE_SAVE_OK;
}

void horse_save_out_init(HorseSaveOut *o) {
    if (o) {
        o->data = NULL;
        o->size = 0;
        o->cap = 0;
    }
}

void horse_save_out_free(HorseSaveOut *o) {
    if (o) {
        free(o->data);
        o->data = NULL;
        o->size = 0;
        o->cap = 0;
    }
}

HorseSaveStatus horse_save_out_reserve(HorseSaveOut *o, size_t extra) {
    if (!o) {
        return HORSE_SAVE_ERR_PARSE;
    }
    size_t need = o->size + extra;
    if (need <= o->cap) {
        return HORSE_SAVE_OK;
    }
    size_t cap = o->cap ? o->cap : 4096;
    while (cap < need) {
        cap *= 2;
    }
    uint8_t *p = (uint8_t *)realloc(o->data, cap);
    if (!p) {
        return HORSE_SAVE_ERR_IO;
    }
    o->data = p;
    o->cap = cap;
    return HORSE_SAVE_OK;
}

HorseSaveStatus horse_save_out_write(HorseSaveOut *o, const void *src, size_t n) {
    if (!o || (n > 0 && !src)) {
        return HORSE_SAVE_ERR_PARSE;
    }
    if (n == 0) {
        return HORSE_SAVE_OK;
    }
    HorseSaveStatus st = horse_save_out_reserve(o, n);
    if (st != HORSE_SAVE_OK) {
        return st;
    }
    memcpy(o->data + o->size, src, n);
    o->size += n;
    return HORSE_SAVE_OK;
}

HorseSaveStatus horse_save_out_write_u32(HorseSaveOut *o, uint32_t v) {
    uint8_t b[4];
    b[0] = (uint8_t)(v);
    b[1] = (uint8_t)(v >> 8);
    b[2] = (uint8_t)(v >> 16);
    b[3] = (uint8_t)(v >> 24);
    return horse_save_out_write(o, b, 4);
}

HorseSaveStatus horse_save_out_write_u8(HorseSaveOut *o, uint8_t v) {
    return horse_save_out_write(o, &v, 1);
}
