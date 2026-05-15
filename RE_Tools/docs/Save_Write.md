# `Save_Write` @ `0x6DAB0`

**Ghidra:** `FUN_14006dab0` · **Span:** `0x6DAB0`–`0x6E179` (`ret`)  
**Raw listing:** [`ghidra_exports/Save_Write.c.txt`](ghidra_exports/Save_Write.c.txt) (disasm) · **Decompile:** [`Save_Write_decompiled.c.txt`](ghidra_exports/Save_Write_decompiled.c.txt)

**Frida signature:** `void Save_Write(GameContext* ctx /* RDI */, int mode /* EDX */)` — `edx=1` on load/autosave/quit.

---

## Callers (XREF)

| RVA | Context |
|-----|---------|
| `0x10A2C2` | Auto-save (frame loop) |
| `0x10A822` | Paired flush after auto-save |
| `0x098680` | Shutdown prep path |
| `0x098040` | Aux update path |
| `0x098680` | Shutdown prep (`GameMain` @ `0xBED0C`) — no direct `0x6DAB0` in scanned span |

**Quit path:** `0xBED0C` → **`0x98680`** (shutdown prep — **includes `Save_Write`**) → **`0xBED11`** → **`0x71F60`** (`Settings_Save`). See [QuitSaveTrace.md](QuitSaveTrace.md).
| `0x9828C` | Startup-related write |

**Load** uses separate **`Save_Load` @ `0x6E2B0`** — not this function.

---

## High-level flow

```c
void Save_Write(GameContext* ctx, int mode /* EDX */) {
    Save_Write_Preamble(ctx);           // 0x0BEE80

    // Mode / UI state dispatch on ctx->mode @ [ctx+0x25C]
    switch (ctx->mode) {
    case 0x1C: /* ... nested panel @ [ctx+0x438]+0xE0 ... */
    case -1:
    case 0x0D: /* ... */
    default:
        FUN_14003F360();              // lock?
        FUN_1400DCBB0(panel);         // per-panel hook
        FUN_14003F360();
    }

    if (ctx->mode == 0x0D)
        FUN_140060540(...);

    // Build path: Game\save\save%d.dat
    FUN_140088000(path_buf);          // 0x088000 — string format
    FUN_1400BFB60();                  // alloc write buffer
    FUN_14006F3C0(stream, path);      // 0x06F3C0 — serialize into heap buffer

    if (ctx->mode == dword@0x2F14B8)  // special slot -1 path
        goto alt_tail;

    // === Serialize ctx to stream (matches Python round-trip) ===
    StreamOpen(0x3D090);              // 0x6FD40
    WriteU32(12);                     // format version @ file 0x00

    FUN_1400C3100(ctx);                // global name registry @ 0xC3100

    WriteU32([ctx+0x254]);            // 0x6FE10 family
    WriteU32([ctx+0x314]);
    WriteU32([ctx+0x268]);
    WriteU8/WriteF32 fields ...      // [ctx+0x414], [ctx+0x415], [ctx+0x37C], f32 @ [ctx+0x114] area

  // Horse stat rows @ [ctx+0x31C] — loop 6× (u8/u32 pairs)
  // Grid-related rows @ [ctx+0x2CC] — loop 13× WriteU32 pairs

    FUN_14006FDF0();                  // section boundary / nested header

  // Horse vector @ [ctx+0x280] — loop: WriteU16×4 per horse (0x6FE50)

    FUN_14006FDF0();

  // Grid cells @ [ctx+0x270] — type-6 runs + per-cell nested (0x6DF30 mirror)
    // loop: cmp type==6, WriteU8 0x3F runs, else WriteNestedItem path

    FUN_14006D440();                  // nested container footer

  // Dynamic panel table @ [ctx+0x438] — per slot WriteU8 + vcall [+0xB0]  (gene packs)

    FUN_14006FD90(stream);            // 0x6FD90 — finalize buffer → disk

    // free path strings (std::string)
    return;
}
```

Cross-check: [SaveLoadPath.md](SaveLoadPath.md), [SaveCompleteFormat.md](SaveCompleteFormat.md), Frida dump **`save_buffer_dump.bin`** (byte-identical to `save1.dat`).

---

## Write API callees (Ghidra + prior Capstone)

| RVA | Name | Role |
|-----|------|------|
| `0x6FD40` | `StreamOpen` | Reserve ~250 KiB stream |
| `0x6FE10` | `WriteU32` | Most fields |
| `0x6FEF0` | `WriteU8` | Bytes / grid runs |
| `0x6FEB0` | `WriteU8Bulk` | Grid skip `0x3F` runs |
| `0x6FE50` | `WriteU16` | Horse vector u16×4 |
| `0x6FF10` | `WriteF32` | Float fields |
| `0x6FDF0` | `WriteSection` | Nested block headers |
| `0x6FF30` | `WriteString` | `[ctx+0x39C]` blob |
| `0x6D440` | `WriteNestedSave` | Inventory/main nested |
| `0x6EC40` | `WriteNestedItem` | Per nested slot (via grid loop) |
| `0xC3100` | `WriteGlobalRegistry` | 71 global names |
| `0x6F3C0` | `SerializeToBuffer` | Heap file buffer |
| `0x6FD90` | `FlushBufferToFile` | Write `save%d.dat` |
| `0x88000` | `BuildSavePath` | `save%d.dat` under `Game\save\` |

---

## `ctx` offsets observed in serialize block

| Offset | Writer | Notes |
|--------|--------|-------|
| `+0x254` | `WriteU32` | Early ctx field |
| `+0x314` | `WriteU32` | |
| `+0x268` | `WriteU32` | |
| `+0x318` | `WriteU32` | |
| `+0x308` | `WriteU32` | |
| `+0x440` | `WriteU32` | |
| `+0x414`, `+0x415` | `WriteU8` | |
| `+0x37C` | `WriteU32` | |
| `+0x418` | `WriteU32` | |
| `+0x41C` | `WriteU8` | |
| `+0x410` | `WriteU32` | |
| `+0x39C` | `WriteString` | |
| `+0x31C` | loop ×6 | Horse-related u8/u32 |
| `+0x2CC` | loop ×13 | Grid metadata u32 pairs |
| `+0x280`–`+0x288` | horse vector | u16×4 per entry |
| `+0x270` | grid array | type-6 + nested cells |
| `+0x420`–`+0x428` | pairs | u32 + u16 |
| `+0x438` | panel ptrs | footer `vtable+0xB0` |

Full layout: [SaveFieldLayout.md](SaveFieldLayout.md), [SaveSemanticsCoverage.md](SaveSemanticsCoverage.md).

---

## Footer / gene packs (Ghidra confirms)

```text
14006e0e9  call qword ptr [RAX + 0xb0]   ; per panel slot — matches SaveFooterFormat.md
14006e112  call qword ptr [RAX + 0xb0]   ; final panel pass
```

These are the **`0xF0`** gene pack writers (`0x6D2A0` family), not the old “opaque 240 B” mislabel.

---

## Path strings

| RVA | String |
|-----|--------|
| `0x263830` | `save%d.dat` |
| `0x263820` | `_saving_` flag |

Built via **`FUN_140088000`** after **`FUN_1400BFB60`** buffer setup.

---

## Ghidra renames

| From | To |
|------|-----|
| `FUN_14006dab0` | `Save_Write` |
| `FUN_14006e2b0` | `Save_Load` |
| `FUN_14006f3c0` | `SerializeSaveToBuffer` |
| `FUN_14006fe10` | `WriteU32` |
| `FUN_1400c3100` | `WriteGlobalRegistry` |

---

## Still open

- [ ] Map each `WriteU32([ctx+offset])` to named field in `SaveContext.h`
- [ ] Decompile **`0x6EC40`** (`WriteNestedItem`) for b8 type tags
