/**
 * Save game-state layout for Save_Write @ 0x6DAB0 (Horsey.exe).
 *
 * Verified:
 *   - Capstone disasm 0x6DCBB+ (RE_Tools/analysis/disasm_phase1_extended.txt)
 *   - save_buffer_dump.bin == Game/save/save1.dat
 *   - Frida save_writer_trace.json (compact, May 2026)
 *
 * FILE LAYOUT (high level):
 *   0x00  u32 12
 *   0x04  u64  global (0xC3100 @ 0x6FE70)
 *   0x0C  u32  global dword (0xC3100)
 *   0x10  u32  count — global horse-name table (0xC3100 @ 0x6FED0)
 *   0x14  WriteStdString × count
 *   ...   ctx[rdi] block (offset varies with global table size)
 *   ...   horse u16 vector @ rdi+0x280 (count + N×8 bytes)
 *   ...   grid @ rdi+0x270, nested @ 0x6D440
 */
#ifndef HORSESDK_SAVE_CONTEXT_H
#define HORSESDK_SAVE_CONTEXT_H

#include <stdint.h>

#define SAVE_FORMAT_VERSION 12

#pragma pack(push, 1)

/** Per global-registry entry written inside 0xC3100 (std::string + flags). */
typedef struct SaveGlobalHorseName {
    /* serialized via 0x6FFF0 + WriteU8 flags in C3100 loop */
    uint32_t _unknown;
} SaveGlobalHorseName;

/** Six 8-byte slots at ctx+0x31C (disk 12 B each). Insn 0x6DD71. */
typedef struct SaveSlot6 {
    uint32_t dword0;     /* [rbx+0]  WriteU32 */
    uint8_t byte4;       /* [rbx+4]  -> WriteU32FromU8 on disk */
    uint8_t byte5;       /* [rbx+5]  -> WriteU32FromU8 on disk */
    uint8_t _pad[2];
} SaveSlot6;

/** Thirteen rows at ctx+0x2CC (disk 8 B each). Insn 0x6DDA3. */
typedef struct SaveRow13 {
    uint32_t field_m34;  /* [rbx-0x34] */
    uint32_t field_0;    /* [rbx] */
} SaveRow13;

/** In-memory horse record (vector ctx+0x280); disk = 4×u16. Insn 0x6DE30. */
typedef struct SaveHorseRecordMem {
    uint8_t data[0x24];
} SaveHorseRecordMem;

/**
 * Main save context (rdi in Save_Write).
 * Only documented fields are those with confirmed Write* in disasm.
 */
typedef struct SaveContext {
    uint8_t _pad_00[0x114];
    float field_114;              /* 0x6DCEB WriteF32 */
    uint8_t _pad_118[0x254 - 0x118];
    uint32_t field_254;           /* 0x6DCCA WriteU32 — after C3100 blob */
    uint8_t _pad_258[0x268 - 0x258];
    uint32_t field_268;           /* 0x6DCE0 — e.g. 21 in save1.dat */
    uint8_t _pad_26C[0x270 - 0x26C];
    /* +0x270  grid cell array pointer; cells are 0x28 bytes in memory (0x6DF30) */
    void *grid_cells;             /* qword ptr [rdi+0x270] */
    uint32_t field_278;           /* 0x6DEA9 — after u16 vector */
    uint32_t field_27C;           /* 0x6DEB7 */
    /* +0x280 .. +0x288  vector<SaveHorseRecordMem, 0x24 stride> */
    uint8_t _vec[0x308 - 0x280];
    uint32_t field_308_name_u32;  /* 0x6DD09 — "Dale" fourcc */
    uint8_t _pad_30C[0x314 - 0x30C];
    uint32_t field_314;           /* 0x6DCD5 */
    uint32_t field_318;           /* 0x6DCFE — often name-related length */
    SaveSlot6 slots6[6];          /* 0x31C, insn 0x6DD71 */
    uint32_t field_37C;           /* 0x6DD31 */
    uint8_t _pad_37D[0x39C - 0x381];
    float field_39C_xy[2];        /* 0x6DD61 WriteVec2F32 */
    uint8_t _pad_3A4[0x410 - 0x3A4];
    uint32_t field_410;           /* 0x6DD6C */
    uint8_t field_414;            /* 0x6DD19 -> 4 bytes on disk */
    uint8_t field_415;            /* 0x6DD25 */
    uint8_t _pad_416[0x418 - 0x416];
    uint32_t field_418;           /* 0x6DD43 */
    uint8_t field_41C;            /* 0x6DD4E */
    uint8_t _pad_41D[0x420 - 0x41D];
    /* +0x420 .. +0x428  (u32,u32) pairs @ 0x6E043 */
    uint8_t _pairs[0x440 - 0x428];
    uint32_t field_440;           /* 0x6DD14 — 0x100 in sample */
    SaveRow13 rows13[13];         /* 0x2CC, insn 0x6DDA3 */
} SaveContext;

/** In-memory grid cell (stride 0x28). Serialized via WriteU8 @ 0x6FEB0 in 0x6DF30 loop. */
typedef struct SaveGridCell {
    uint32_t type;       /* +0x00 — 6 = empty, skip write */
    uint8_t  extra;      /* +0x04 — written if GridTypeLookup @ 0x1167B0 returns > 0 */
    uint8_t  _pad5[3];
    uint32_t layer;      /* +0x08 — height/layer index */
    uint8_t  flag_c;     /* +0x0C — encoding flag (OR 0x40 path) */
    uint8_t  flag_d;     /* +0x0D — encoding flag (OR 0x80 path) */
    uint8_t  _pad_e[0x28 - 0x0E];
} SaveGridCell;

#pragma pack(pop)

#endif /* HORSESDK_SAVE_CONTEXT_H */
