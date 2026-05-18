/**
 * HorseSDK save loader — mirrors Horsey.exe Save_Load @ 0x6E2B0 / Save_Write @ 0x6DAB0.
 *
 * Verified: Game/Horsey.exe, save_buffer_dump.bin, RE_Tools/docs/SaveGhidraCrossref.md
 */
#ifndef HORSE_SAVE_H
#define HORSE_SAVE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define HORSE_SAVE_FORMAT_VERSION 12
#define HORSE_SAVE_GENE_COUNT 240
#define HORSE_SAVE_GENE_PACK_BYTES 0xF0
#define HORSE_SAVE_GENE_UNPACKED_BYTES 0x1E0
#define HORSE_SAVE_INVENTORY_RECORD 352
#define HORSE_SAVE_INVENTORY_GENE_OFF 0x51
#define HORSE_SAVE_INVENTORY_SLOTS 410

/** Section anchors — save_buffer_dump.bin / save_complete_format.json (format v12). */
#define HORSE_SAVE_OFF_GLOBALS_END 2393u
#define HORSE_SAVE_OFF_CTX_END 2621u
#define HORSE_SAVE_OFF_GRID_DIM_END 2657u
#define HORSE_SAVE_OFF_GRID_END 56999u /* 0xDEA7 */
#define HORSE_SAVE_OFF_PAIRS_END 57035u /* 0xDECB — main nested */
#define HORSE_SAVE_OFF_INVENTORY_DEFAULT 58169u /* 0xE339 */
#define HORSE_SAVE_OFF_INVENTORY_END_DEFAULT 203545u /* 0x31B19 */
#define HORSE_SAVE_MAIN_NESTED_BYTES 1134u
#define HORSE_SAVE_B8_BLOB_BYTES 1079u
#define HORSE_SAVE_B8_TYPE2_BLOCK 164u
#define HORSE_SAVE_B8_TYPE2_INNER 40u

typedef enum HorseSaveStatus {
    HORSE_SAVE_OK = 0,
    HORSE_SAVE_ERR_IO = 1,
    HORSE_SAVE_ERR_TRUNCATED = 2,
    HORSE_SAVE_ERR_VERSION = 3,
    HORSE_SAVE_ERR_PARSE = 4,
    HORSE_SAVE_ERR_GENE = 5,
} HorseSaveStatus;

typedef struct HorseSaveGeneTracks {
    uint8_t track_a[HORSE_SAVE_GENE_COUNT];
    uint8_t track_b[HORSE_SAVE_GENE_COUNT];
} HorseSaveGeneTracks;

typedef struct HorseSaveInventorySlot {
    uint32_t slot;
    uint32_t file_offset;
    uint32_t name_len;
    uint32_t ptr_item_count;
    HorseSaveGeneTracks genes;
} HorseSaveInventorySlot;

typedef struct HorseSaveType0Packed {
    uint8_t packed;
    int32_t dword_38;
    uint8_t flag_10;
    uint8_t flag_11;
} HorseSaveType0Packed;

typedef struct HorseSaveMainNested {
    char name[64];
    uint32_t file_offset;
    uint32_t b8_header_count;
    uint32_t b8_blob_bytes;
    uint32_t type1_records;
    uint32_t type2_blocks;
    uint32_t type2_inners;
    uint32_t type0_tail_bytes;
    uint32_t on_disk_slots;
    uint32_t implicit_eof_slots;
} HorseSaveMainNested;

typedef struct HorseSaveGridSummary {
    uint32_t width;
    uint32_t height;
    uint32_t cells_expected;
    uint32_t cells_decoded;
    uint32_t stream_bytes;
    uint32_t pad_bytes;
    uint32_t prefix_bytes;
    uint32_t type6_cells;
} HorseSaveGridSummary;

/** FooterExtra_Write @ 0x1017C0 — 7 B tail in footer blob (rel 833). */
typedef struct HorseSaveFooterExtra {
    uint32_t dword_25c;
    uint8_t byte_261;
    uint8_t byte_262;
    uint8_t byte_263;
} HorseSaveFooterExtra;

/** Global footer @ 0x31B19 — DAT_14031a660 @ Save_Write 0x6E103. */
typedef struct HorseSaveFooter {
    uint32_t file_offset;
    uint32_t byte_size;
    char track_display_name[64];
    float world_vec2[2];
    float camera_vec2[2];
    uint32_t gene_settings_offset;
    uint32_t gene_track_offset;
    HorseSaveGeneTracks gene_settings;
    HorseSaveGeneTracks gene_track;
    HorseSaveFooterExtra extra;
    int has_gene_settings;
    int has_gene_track;
    int has_footer_extra;
} HorseSaveFooter;

typedef struct HorseSaveFile {
    uint8_t *data;
    size_t size;
    uint32_t format_version;
    uint32_t global_name_count;
    uint32_t grid_width;
    uint32_t grid_height;
    size_t cursor;
    size_t inventory_offset;
    size_t inventory_end;
    HorseSaveInventorySlot *inventory;
    uint32_t inventory_count;
    HorseSaveMainNested main_nested;
    HorseSaveGridSummary grid;
    HorseSaveFooter footer;
    int has_main_nested;
    int has_grid;
    int has_footer;
} HorseSaveFile;

const char *horse_save_status_string(HorseSaveStatus st);

/** Load entire file into memory. */
HorseSaveStatus horse_save_file_read_path(HorseSaveFile *out, const char *path);
HorseSaveStatus horse_save_file_read_buffer(HorseSaveFile *out, const uint8_t *data, size_t len);
void horse_save_file_free(HorseSaveFile *sf);

/**
 * Sequential parse (version, globals, ctx, horse vector, grid, pairs).
 * Sets inventory_offset to stream cursor on success (should match save1 @ 58169).
 */
HorseSaveStatus horse_save_parse_stream(HorseSaveFile *sf);

/**
 * Decode all inventory gene packs (413 × 0xF0 @ record+0x51).
 * Uses sf->inventory_offset or HORSE_SAVE_OFF_INVENTORY_DEFAULT when zero.
 */
HorseSaveStatus horse_save_decode_inventory_genes(HorseSaveFile *sf);

/** Unpack 0x6D3B0 — 0xF0 packed bytes -> track A/B (allele indices 0..3). */
HorseSaveStatus horse_save_gene_unpack(
    const uint8_t packed[HORSE_SAVE_GENE_PACK_BYTES],
    HorseSaveGeneTracks *out);

/** Load path + inventory genes in one call. */
HorseSaveStatus horse_save_load_path(HorseSaveFile *sf, const char *path);

/**
 * Write save bytes (preserves on-disk layout from load).
 * Mirrors Python save_file_codec.write_save_bytes @ Save_Write 0x6DAB0.
 */
HorseSaveStatus horse_save_write_buffer(
    const HorseSaveFile *sf,
    uint8_t **out_data,
    size_t *out_len);

HorseSaveStatus horse_save_write_path(const HorseSaveFile *sf, const char *path);

/** Section-ordered emit (format v12 milestones); must match `sf->size` for unchanged dumps. */
HorseSaveStatus horse_save_write_structured(
    const HorseSaveFile *sf,
    uint8_t **out_data,
    size_t *out_len);

/** Pointer to slot genes after horse_save_load_path (NULL if out of range). */
const HorseSaveInventorySlot *horse_save_get_inventory_slot(
    const HorseSaveFile *sf,
    uint32_t slot);

/** FUN_14006d960 — unpack type-0 packed u8. */
HorseSaveStatus horse_save_unpack_type0_packed(uint8_t packed, HorseSaveType0Packed *out);

/** Main nested @ 0xDECB — b8 blob summary (0x6D5C0 / nested_b8_codec.py). */
HorseSaveStatus horse_save_parse_main_nested(HorseSaveFile *sf);

/** Grid u8 stream stats @ 0x6DF30 (decode_grid_cells.py). */
HorseSaveStatus horse_save_parse_grid_summary(HorseSaveFile *sf);

/** Footer @ 0x31B19 (decode_save_footer_fields.py / SaveFooterFormat.md). */
HorseSaveStatus horse_save_parse_footer(HorseSaveFile *sf);

const HorseSaveMainNested *horse_save_get_main_nested(const HorseSaveFile *sf);

const HorseSaveGridSummary *horse_save_get_grid_summary(const HorseSaveFile *sf);

const HorseSaveFooter *horse_save_get_footer(const HorseSaveFile *sf);

#ifdef __cplusplus
}
#endif

#endif /* HORSE_SAVE_H */
