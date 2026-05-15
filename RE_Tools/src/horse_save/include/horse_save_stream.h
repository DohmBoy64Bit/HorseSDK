#ifndef HORSE_SAVE_STREAM_H
#define HORSE_SAVE_STREAM_H

#include <stddef.h>
#include <stdint.h>

#include "horse_save.h"

typedef struct HorseSaveStream {
    const uint8_t *data;
    size_t size;
    size_t pos;
} HorseSaveStream;

void horse_save_stream_init(HorseSaveStream *s, const uint8_t *data, size_t len);

HorseSaveStatus horse_save_read_u8(HorseSaveStream *s, uint8_t *out);
HorseSaveStatus horse_save_read_u16(HorseSaveStream *s, uint16_t *out);
HorseSaveStatus horse_save_read_u32(HorseSaveStream *s, uint32_t *out);
HorseSaveStatus horse_save_read_f32(HorseSaveStream *s, float *out);
HorseSaveStatus horse_save_read_bytes(HorseSaveStream *s, uint8_t *dst, size_t n);
HorseSaveStatus horse_save_read_string(HorseSaveStream *s, char *buf, size_t buf_cap, uint32_t *out_len);
HorseSaveStatus horse_save_skip_bytes(HorseSaveStream *s, size_t n);

/** Mirror grid read loop @ 0x6E700 until width*height cells consumed. */
HorseSaveStatus horse_save_skip_grid(HorseSaveStream *s, uint32_t width, uint32_t height);

#endif /* HORSE_SAVE_STREAM_H */
