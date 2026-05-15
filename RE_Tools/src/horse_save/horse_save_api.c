#include "horse_save.h"

HorseSaveStatus horse_save_load_path(HorseSaveFile *sf, const char *path) {
    if (!sf) {
        return HORSE_SAVE_ERR_PARSE;
    }
    HorseSaveStatus st = horse_save_file_read_path(sf, path);
    if (st != HORSE_SAVE_OK) {
        return st;
    }
    st = horse_save_parse_stream(sf);
    if (st != HORSE_SAVE_OK) {
        return st;
    }
    st = horse_save_parse_main_nested(sf);
    if (st != HORSE_SAVE_OK) {
        return st;
    }
    st = horse_save_parse_grid_summary(sf);
    if (st != HORSE_SAVE_OK) {
        return st;
    }
    st = horse_save_parse_footer(sf);
    if (st != HORSE_SAVE_OK) {
        return st;
    }
    return horse_save_decode_inventory_genes(sf);
}

const HorseSaveInventorySlot *horse_save_get_inventory_slot(
    const HorseSaveFile *sf,
    uint32_t slot) {
    if (!sf || !sf->inventory || slot >= sf->inventory_count) {
        return NULL;
    }
    return &sf->inventory[slot];
}
