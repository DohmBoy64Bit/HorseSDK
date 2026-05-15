#include "horse_save.h"
#include "horse_save_stream.h"

#include <string.h>

#define INV_GENE_OFF 0x51u

HorseSaveStatus horse_save_read_nested_block(
    HorseSaveStream *s,
    uint32_t file_offset,
    uint32_t block_size,
    HorseSaveInventorySlot *slot) {
    if (!s || !slot || block_size == 0) {
        return HORSE_SAVE_ERR_PARSE;
    }
    s->pos = file_offset;
    uint32_t start = file_offset;

    uint32_t name_len = 0;
    HorseSaveStatus st = horse_save_read_u32(s, &name_len);
    if (st != HORSE_SAVE_OK) {
        return st;
    }
    if (name_len > 256 || name_len + 4u > block_size) {
        return HORSE_SAVE_ERR_PARSE;
    }
    if (name_len > 0) {
        st = horse_save_skip_bytes(s, name_len);
        if (st != HORSE_SAVE_OK) {
            return st;
        }
    }

    memset(slot, 0, sizeof(*slot));
    slot->file_offset = start;
    slot->name_len = name_len;

    if (s->pos + 4u <= start + block_size) {
        uint32_t ptr = 0;
        st = horse_save_read_u32(s, &ptr);
        if (st != HORSE_SAVE_OK) {
            return st;
        }
        slot->ptr_item_count = ptr;
    }
    if (s->pos + 8u <= start + block_size) {
        st = horse_save_skip_bytes(s, 8);
        if (st != HORSE_SAVE_OK) {
            return st;
        }
    }

    if (start + INV_GENE_OFF + HORSE_SAVE_GENE_PACK_BYTES <= start + block_size) {
        const uint8_t *gene = s->data + start + INV_GENE_OFF;
        (void)horse_save_gene_unpack(gene, &slot->genes);
    }

    s->pos = start + block_size;
    return HORSE_SAVE_OK;
}
