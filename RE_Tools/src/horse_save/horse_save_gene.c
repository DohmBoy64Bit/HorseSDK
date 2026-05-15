#include "horse_save.h"

#include <string.h>

/* Mirror inventory_pack_codec.py / Horsey.exe 0x6D3B0 */

static uint8_t nib_decode(uint8_t b) {
    return (uint8_t)(((b & 7) - 1) & 0xFF);
}

HorseSaveStatus horse_save_gene_unpack(
    const uint8_t packed[HORSE_SAVE_GENE_PACK_BYTES],
    HorseSaveGeneTracks *out) {
    if (!packed || !out) {
        return HORSE_SAVE_ERR_PARSE;
    }

    memset(out, 0, sizeof(*out));
    uint32_t rax = 1;

    for (int iter = 0; iter < 0x78; ++iter) {
        if (rax < 1 || rax > HORSE_SAVE_GENE_PACK_BYTES) {
            return HORSE_SAVE_ERR_GENE;
        }
        uint8_t b0 = packed[rax - 1];
        rax += 2;
        if (rax < 3) {
            return HORSE_SAVE_ERR_GENE;
        }

        uint32_t idx_a = rax - 3;
        if (idx_a < HORSE_SAVE_GENE_COUNT) {
            out->track_a[idx_a] = nib_decode(b0);
        }
        uint32_t idx_b = idx_a + HORSE_SAVE_GENE_COUNT;
        if (idx_b < HORSE_SAVE_GENE_COUNT * 2) {
            out->track_b[idx_a] = nib_decode((uint8_t)((b0 >> 3) & 0xFF));
        }

        uint8_t b1 = packed[rax - 2];
        uint32_t idx_a2 = rax - 2;
        if (idx_a2 < HORSE_SAVE_GENE_COUNT) {
            out->track_a[idx_a2] = nib_decode(b1);
        }
        if (idx_a2 + HORSE_SAVE_GENE_COUNT < HORSE_SAVE_GENE_COUNT * 2) {
            out->track_b[idx_a2] = nib_decode((uint8_t)((b1 >> 3) & 0xFF));
        }
    }

    return HORSE_SAVE_OK;
}
