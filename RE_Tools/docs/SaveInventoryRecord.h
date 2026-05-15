/**
 * Inventory slot on-disk record (352 bytes) and in-memory item (0x6EC40).
 *
 * Verified:
 *   Horsey.exe @ 0x6D440 (WriteNestedSave), caller 0x6E0D6
 *   @ 0x6EC40 (WriteNestedItem) when (end+0x138)-(beg+0x130) >> 3 > 0
 *   save_buffer_dump.bin @ file 0xE339 (sample slot)
 *   RE_Tools/analysis/save_inventory_record_layout.json
 */
#ifndef HORSESDK_SAVE_INVENTORY_RECORD_H
#define HORSESDK_SAVE_INVENTORY_RECORD_H

#include <stdint.h>

#define SAVE_INVENTORY_RECORD_SIZE 352

#pragma pack(push, 1)

/** On-disk: one inventory nested save from 0x6D440 @ 0x6E0D6. */
typedef struct SaveInventoryRecordDisk {
    uint32_t name_len;           /* WriteStdString — often 0 */
    /* char name[name_len]; */
    uint32_t ptr_item_count;     /* (obj+0x138 - obj+0x130) >> 3; 0 skips 0x6EC40 */
    uint32_t merge_run_index;    /* 0x6D4F1 */
    uint32_t vec_b8_count;       /* (obj+0xC0 - obj+0xB8) >> 3 */
    float    vec2_xy[2];         /* object+0x0C @ 0x6D574 */
    uint8_t  opaque[0xF0];       /* 6D2A0 pack @ item+0x2B8: 240 B diploid gene indices (see save_inventory_genes.json) */
    uint64_t field_2a8;          /* 0x6EC40 +0x2A8 — footer region @ ~+0x141 */
    uint32_t field_tail_u32;
    uint16_t field_tail_u16;
    uint8_t  pad[9];
    float    vec2_tail[2];
} SaveInventoryRecordDisk; /* sizeof must equal 352 — layout is logical, opaque spans middle */

/**
 * In-memory item serialized by 0x6EC40 (rbp = item object).
 * Write order from Capstone walk @ 0x6EC40.
 */
typedef struct SaveInventoryItemMem {
    uint8_t  _pad_00[0x1C];
    uint8_t  byte_1C;
    uint8_t  _pad_1D[0x22 - 0x1D];
    uint8_t  byte_22;
    uint8_t  byte_23;
    uint8_t  _pad_24[0x40 - 0x24];
    uint64_t qword_40[2];        /* +0x40 area: 3x WriteU32 + Vec2 in tail of 0x6EC40 */
    uint8_t  _pad_48[0xC0 - 0x50];
    float    field_C0;           /* WriteF32 @ 0x6FF80 */
    uint8_t  _pad_C4[0xCC - 0xC4];
    int32_t  gene_slots[20];     /* +0xCC..+0x118 sparse overrides; separate from +0x2B8 pack */
    uint8_t  _pad_118[0x160 - 0x118];
    uint8_t  byte_160;
    uint8_t  _pad_161[0x168 - 0x161];
    /* std::string @ +0x168 */
    uint8_t  _pad_168[0x1D4 - 0x168];
    float    vec2_1D4[2];
    uint32_t dword_1F8;
    uint8_t  byte_1FC;
    uint8_t  _pad_1FD[0x204 - 0x1FD];
    uint8_t  bytes_204_206[3];
    uint8_t  byte_210;
    uint8_t  byte_214;
    uint8_t  byte_21C;
    uint16_t word_220;
    uint8_t  byte_234;
    uint8_t  _pad_235[0x284 - 0x235];
    uint8_t  byte_284;
    uint8_t  _pad_285[0x2A8 - 0x285];
    uint64_t qword_2A8;
    /* +0x2B8 sub-call 0x6D2A0 */
} SaveInventoryItemMem;

#pragma pack(pop)

#endif /* HORSESDK_SAVE_INVENTORY_RECORD_H */
