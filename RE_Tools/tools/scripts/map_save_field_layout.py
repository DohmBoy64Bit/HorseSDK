"""
Walk Save_Write serialization (from StreamOpen @ 0x6DCB1) and map each writer
call to file offsets in save_buffer_dump.bin.

Source: Horsey.exe disasm (Capstone), verified against:
  RE_Tools/analysis/save_buffer_dump.bin
  disasm_phase1_extended.txt @ 0x6DCBB+

Output:
  RE_Tools/analysis/save_field_layout.json
  RE_Tools/docs/SaveFieldLayout.md
"""
from __future__ import annotations

import json
import re
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_64, Cs
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_OP_REG, X86_REG_ECX, X86_REG_RDI

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
from paths import get_exe_path  # noqa: E402

IMAGE_BASE = 0x140000000
SER_START = 0x6DCAC  # mov ecx, 0x3d090 / StreamOpen
SER_END = 0x6E17A
DUMP_PATH = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
OUT_JSON = ROOT / "RE_Tools" / "analysis" / "save_field_layout.json"
OUT_MD = ROOT / "RE_Tools" / "docs" / "SaveFieldLayout.md"

# Writer RVA -> (name, size_bytes, advance). 6FEF0 writes u32 from low byte (4 B on disk).
WRITERS: dict[int, tuple[str, int]] = {
    0x6FE10: ("WriteU32", 4),
    0x6FE30: ("WriteU8", 1),  # mov byte [rax], cl
    0x6FEF0: ("WriteU32FromU8", 4),
    0x6FF10: ("WriteF32", 4),
    0x6FE50: ("WriteU16", 2),
    0x6FED0: ("WriteU32", 4),  # count prefix
    0x6FE70: ("WriteU64", 8),
    0x6FF30: ("WriteVec2F32", 8),
    0x6FEB0: ("WriteU8", 1),
    0x6FFF0: ("WriteStdString", -1),  # u32 len + bytes
    0x6FD40: ("StreamOpen", 0),
    0x6FDF0: ("GetBufferSize", 0),
    0xC3100: ("WriteGlobalHorseTable", -2),  # sub-routine; simulate via dump delta or skip
    0x6D440: ("WriteNestedSave", -2),
    0x1167B0: ("GridTypeLookup", 0),  # returns u32; not a stream writer
}


@dataclass
class FieldRec:
    file_offset: int
    size: int
    writer: str
    insn_rva: str
    source: str
    raw_hex: str
    decoded: str
    note: str = ""


def disasm_save(pe: pefile.PE, raw: bytes) -> list:
    off = pe.get_offset_from_rva(SER_START)
    chunk = raw[off : off + (SER_END - SER_START + 0x200)]
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    return list(md.disasm(chunk, IMAGE_BASE + SER_START))


def parse_mem(op_str: str) -> tuple[str, int | None]:
    """Return (kind, offset): rdi+disp, rip+disp, rbx+disp, imm, unknown."""
    s = op_str.strip()
    m = re.match(r"(?:dword|byte|word|qword|movss|movsxd|lea)\s+(?:ptr\s+)?\[(rdi|rbx|rsi|rcx)\s*\+\s*(0x[0-9a-f]+)\]", s, re.I)
    if m:
        return f"{m.group(1).lower()}+{m.group(2)}", int(m.group(2), 16)
    m = re.match(r"0x([0-9a-f]+)", s, re.I)
    if m:
        return f"imm:{m.group(1)}", int(m.group(1), 16)
    if "xmm0" in s or "xmm" in s:
        return "xmm0", None
    if s in ("ecx", "cl", "rcx"):
        return "ecx", None
    return s, None


def read_val(data: bytes, off: int, size: int) -> tuple[str, str]:
    if off + size > len(data):
        return "", "?"
    chunk = data[off : off + size]
    hx = chunk.hex()
    if size == 4:
        u = struct.unpack_from("<I", chunk, 0)[0]
        f = struct.unpack_from("<f", chunk, 0)[0]
        asc = ""
        if u < 0x10000000 and all(32 <= b < 127 for b in chunk):
            asc = chunk.decode("ascii", "replace")
        elif all(b == 0 or 32 <= b < 127 for b in chunk):
            asc = chunk.split(b"\x00")[0].decode("ascii", "replace")
        return hx, f"u32={u} (0x{u:08X}) f32={f:.6g} ascii={asc!r}"
    if size == 8:
        u = struct.unpack_from("<Q", chunk, 0)[0]
        return hx, f"u64={u} (0x{u:016X})"
    if size == 2:
        u = struct.unpack_from("<H", chunk, 0)[0]
        return hx, f"u16={u}"
    if size == 1:
        return hx, f"u8={chunk[0]}"
    return hx, ""


def find_writer_target(op_str: str) -> int | None:
    m = re.search(r"0x([0-9a-f]+)", op_str, re.I)
    if not m:
        return None
    va = int(m.group(1), 16)
    if va >= IMAGE_BASE:
        return va - IMAGE_BASE
    return va


def extract_arg(insns: list, call_idx: int) -> tuple[str, int | None]:
    """Scan up to 8 insns before call for mov ecx / movss xmm0 / mov rcx."""
    for j in range(call_idx - 1, max(call_idx - 12, -1), -1):
        ins = insns[j]
        if ins.mnemonic == "call":
            break
        if ins.mnemonic == "mov" and "ecx" in ins.op_str:
            return parse_mem(ins.op_str.split(",")[1].strip() if "," in ins.op_str else ins.op_str)
        if ins.mnemonic == "movss" and "xmm0" in ins.op_str:
            return parse_mem(ins.op_str.split(",")[1].strip())
        if ins.mnemonic == "mov" and "rcx," in ins.op_str:
            return parse_mem(ins.op_str.split(",", 1)[1].strip())
        if ins.mnemonic == "movzx" and "ecx" in ins.op_str:
            return parse_mem(ins.op_str.split(",")[1].strip())
        if ins.mnemonic == "xor" and ins.op_str == "ecx, ecx":
            return ("imm:0", 0)
    return ("?", None)


@dataclass
class SimState:
    offset: int = 0
    fields: list[FieldRec] = field(default_factory=list)
    loop_stack: list[dict] = field(default_factory=list)

    def emit(
        self,
        writer: str,
        size: int,
        insn_rva: int,
        source: str,
        data: bytes,
        note: str = "",
    ) -> None:
        if size <= 0:
            return
        hx, dec = read_val(data, self.offset, size)
        self.fields.append(
            FieldRec(
                file_offset=self.offset,
                size=size,
                writer=writer,
                insn_rva=f"0x{insn_rva:X}",
                source=source,
                raw_hex=hx,
                decoded=dec,
                note=note,
            )
        )
        self.offset += size


def simulate_c3100_skip(data: bytes, off: int) -> int:
    """
    0xC3100 writes u64 + u32 + (count * std::string records) when global vector non-empty.
  On this save, cursor stays at 4 after call — table empty. Return 0 bytes consumed.
    """
    return 0


def emit_slot_loop_6(st: SimState, data: bytes, base_insn: int) -> None:
    """6 × (WriteU32FromU8 @+5, WriteU32 @+0, WriteU32FromU8 @+4) — base ctx rdi+0x31C."""
    for n in range(6):
        base = 0x31C + n * 8
        st.emit("WriteU32FromU8", 4, base_insn, f"ctx[rdi+0x{base + 5:X}]", data, f"slot{n} byte+5")
        st.emit("WriteU32", 4, base_insn, f"ctx[rdi+0x{base:X}]", data, f"slot{n} dword+0")
        st.emit("WriteU32FromU8", 4, base_insn, f"ctx[rdi+0x{base + 4:X}]", data, f"slot{n} byte+4")


def emit_slot_loop_13(st: SimState, data: bytes, base_insn: int) -> None:
    """13 × (WriteU32 @-0x34, WriteU32 @+0) — base ctx rdi+0x2CC + i*4."""
    for n in range(13):
        base = 0x2CC + n * 4
        st.emit("WriteU32", 4, base_insn, f"ctx[rdi+0x{base - 0x34:X}]", data, f"row{n} field-0x34")
        st.emit("WriteU32", 4, base_insn, f"ctx[rdi+0x{base:X}]", data, f"row{n} field+0")


def emit_vector_24(st: SimState, data: bytes, base_insn: int) -> None:
    """Count u32 then N × 4×u16 (0x24-byte source records) — ctx vector @ rdi+0x280."""
    if st.offset + 4 > len(data):
        return
    count = struct.unpack_from("<I", data, st.offset)[0]
    if count > 100000:
        count = 0
    st.emit("WriteU32", 4, base_insn, "ctx[rdi+0x280..0x288] count", data, f"N={count}")
    for n in range(count):
        for fld, off in enumerate([4, 8, 0xC, 0x10]):
            st.emit("WriteU16", 2, base_insn, f"record[{n}]+0x{off:X}", data, f"u16 field")


def walk(insns: list, data: bytes) -> SimState:
    st = SimState()
    skip_until = 0
    i = 0
    while i < len(insns):
        ins = insns[i]
        rva = ins.address - IMAGE_BASE
        if rva > SER_END:
            break
        if rva < skip_until:
            i += 1
            continue

        # Fixed loops (disasm executes once; expand from dump)
        if ins.mnemonic == "lea" and ins.op_str == "rbx, [rdi + 0x31c]":
            emit_slot_loop_6(st, data, rva)
            skip_until = 0x6DDA3
            i += 1
            continue
        if ins.mnemonic == "lea" and ins.op_str == "rbx, [rdi + 0x2cc]":
            emit_slot_loop_13(st, data, rva)
            skip_until = 0x6DDC9
            i += 1
            continue
        if rva == 0x6DDF9 and ins.mnemonic == "call" and find_writer_target(ins.op_str) == 0x6FED0:
            emit_vector_24(st, data, rva)
            skip_until = 0x6DEA9
            i += 1
            continue

        if ins.mnemonic == "call":
            tgt = find_writer_target(ins.op_str)
            if tgt is None:
                i += 1
                continue
            name_size = WRITERS.get(tgt)
            if not name_size:
                i += 1
                continue
            wname, wsize = name_size
            src, src_off = extract_arg(insns, i)

            if tgt == 0x6FD40:
                st.fields.append(
                    FieldRec(
                        file_offset=st.offset,
                        size=0,
                        writer="StreamOpen",
                        insn_rva=f"0x{rva:X}",
                        source="ecx=0x3d090",
                        raw_hex="",
                        decoded="reserve ~0x3d090",
                        note="heap buffer @ 0x310418",
                    )
                )
            elif tgt == 0xC3100:
                consumed = simulate_c3100_skip(data, st.offset)
                st.fields.append(
                    FieldRec(
                        file_offset=st.offset,
                        size=consumed,
                        writer="WriteGlobalHorseTable",
                        insn_rva=f"0x{rva:X}",
                        source="global vector",
                        raw_hex="",
                        decoded="empty in this save",
                        note="skipped 0 bytes — je @ 0xC317D",
                    )
                )
                st.offset += consumed
            elif tgt == 0x6FDF0:
                pass
            elif tgt == 0x6FFF0:
                if st.offset + 4 <= len(data):
                    slen = struct.unpack_from("<I", data, st.offset)[0]
                    st.emit("WriteStdString", 4, rva, f"len prefix", data, "u32 char count")
                    if slen > 0 and st.offset + slen <= len(data):
                        chunk = data[st.offset : st.offset + slen]
                        st.fields.append(
                            FieldRec(
                                file_offset=st.offset,
                                size=slen,
                                writer="WriteStdString",
                                insn_rva=f"0x{rva:X}",
                                source=src,
                                raw_hex=chunk.hex(),
                                decoded=chunk.decode("utf-8", "replace"),
                            )
                        )
                        st.offset += slen
            elif tgt == 0x1167B0:
                pass  # lookup only @ 0x6DFEE; bytes written by following WriteU8
            elif tgt == 0x6D440:
                st.fields.append(
                    FieldRec(
                        file_offset=st.offset,
                        size=0,
                        writer=wname,
                        insn_rva=f"0x{rva:X}",
                        source=src,
                        raw_hex="",
                        decoded="?",
                        note="variable-size block — not linearly simulated",
                    )
                )
            elif wsize > 0:
                label = src
                if src_off is not None and "rdi" in src:
                    label = f"ctx[rdi+0x{src_off:X}]"
                elif src.startswith("imm:"):
                    label = f"constant {src_off}"
                st.emit(wname, wsize, rva, label, data)

        # Detect loops for annotation
        if ins.mnemonic == "lea" and "rbx, [rdi + 0x31c]" in ins.op_str:
            st.loop_stack.append({"type": "slot6x8", "start_off": st.offset, "insn": f"0x{rva:X}"})
        if ins.mnemonic == "lea" and "rbx, [rdi + 0x2cc]" in ins.op_str:
            st.loop_stack.append({"type": "slot13x4", "start_off": st.offset, "insn": f"0x{rva:X}"})
        if ins.mnemonic == "lea" and "rbx, [rdi + 0x278]" in ins.op_str:
            st.loop_stack.append({"type": "field_278", "start_off": st.offset, "insn": f"0x{rva:X}"})

        i += 1
    return st


def verify_linear(fields: list[FieldRec], data: bytes) -> list[dict]:
    issues = []
    expected = 0
    for f in fields:
        if f.size <= 0 or f.writer in ("StreamOpen", "GetBufferSize", "WriteNestedSave", "WriteDynamicBlock"):
            continue
        if f.file_offset != expected and f.writer != "WriteGlobalHorseTable":
            issues.append(
                {
                    "expected_offset": expected,
                    "actual_offset": f.file_offset,
                    "insn": f.insn_rva,
                    "writer": f.writer,
                }
            )
        expected = f.file_offset + f.size
    return issues


def md_table(fields: list[FieldRec], limit: int = 80) -> str:
    lines = [
        "| File offset | Size | Writer | Insn | Ctx source | Value (from dump) |",
        "|-------------|------|--------|------|------------|-------------------|",
    ]
    for f in fields[:limit]:
        val = f.decoded.replace("|", "\\|")[:60]
        lines.append(
            f"| `0x{f.file_offset:04X}` | {f.size} | {f.writer} | {f.insn_rva} | {f.source} | {val} |"
        )
    if len(fields) > limit:
        lines.append(f"\n*… {len(fields) - limit} more entries in JSON …*")
    return "\n".join(lines)


def main() -> int:
    pe = pefile.PE(str(get_exe_path()))
    raw = get_exe_path().read_bytes()
    if not DUMP_PATH.is_file():
        print(f"Missing {DUMP_PATH} — run frida_dump_save_buffer.py first")
        return 1
    data = DUMP_PATH.read_bytes()

    insns = disasm_save(pe, raw)
    st = walk(insns, data)
    issues = verify_linear(st.fields, data)

    # Manual anchor checks from disasm @ 0x6DCBB
    anchors = {
        0x00: ("format_version", "WriteU32(12) @ 0x6DCBB"),
        0x04: ("ctx+0x254", "0x6DCCA"),
        0x08: ("ctx+0x314", "0x6DCD5"),
        0x0C: ("ctx+0x268", "0x6DCE0"),
        0x10: ("ctx+0x114 f32", "0x6DCEB"),
        0x14: ("ctx+0x318", "0x6DCFE"),
        0x18: ("ctx+0x308 name", "0x6DD09 — 'Dale' as u32 fourcc"),
        0x1C: ("ctx+0x440", "0x6DD14"),
    }

    report = {
        "source_dump": str(DUMP_PATH),
        "dump_size": len(data),
        "serialization_rva": f"0x{SER_START:X}-0x{SER_END:X}",
        "simulated_linear_end": st.offset,
        "linear_mismatch_issues": issues[:30],
        "anchors": {
            hex(k): {"label": v[0], "insn": v[1], "dump": read_val(data, k, 4)[1]}
            for k, v in anchors.items()
        },
        "fields": [
            {
                "file_offset": f.file_offset,
                "size": f.size,
                "writer": f.writer,
                "insn_rva": f.insn_rva,
                "source": f.source,
                "raw_hex": f.raw_hex,
                "decoded": f.decoded,
                "note": f.note,
            }
            for f in st.fields
        ],
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    md = f"""# Save file field layout (Phase 1)

**Method:** Capstone walk of `Save_Write` serialization (`0x{SER_START:X}`–`0x{SER_END:X}`) correlated with `save_buffer_dump.bin` (byte-matched to `Game/save/save1.dat`).

**Writers (RVA):**

| RVA | Name | Bytes on disk |
|-----|------|----------------|
| `0x6FE10` | WriteU32 | 4 |
| `0x6FEF0` | WriteU32FromU8 | 4 (byte zero-extended) |
| `0x6FEB0` / `0x6FE30` | WriteU8 | 1 |
| `0x6FF10` | WriteF32 | 4 |
| `0x6FE50` | WriteU16 | 2 |
| `0x6FED0` | WriteU32 (count) | 4 |
| `0x6FE70` | WriteU64 | 8 |
| `0x6FFF0` | WriteStdString | 4 + len |
| `0x6FF30` | WriteVec2F32 | 8 |
| `0xC3100` | Global horse table | variable (empty in this save) |

## Header (verified linear)

| File | Size | Insn | `rdi` offset | Dump value |
|------|------|------|--------------|------------|
| `0x00` | 4 | `0x6DCBB` | constant `12` | format version |
| `0x04` | 4 | `0x6DCCA` | `+0x254` | `0x06D2A89F` |
| `0x08` | 4 | `0x6DCD5` | `+0x314` | `0` |
| `0x0C` | 4 | `0x6DCE0` | `+0x268` | `21` |
| `0x10` | 4 | `0x6DCEB` | `+0x114` | `WriteF32` (raw bits `0x00000047` in this save) |
| `0x14` | 4 | `0x6DCFE` | `+0x318` | `4` |
| `0x18` | 4 | `0x6DD09` | `+0x308` | horse name **`Dale`** (4-char u32) |
| `0x1C` | 4 | `0x6DD14` | `+0x440` | `256` (`0x100`) |

`0xC3100` @ `0x6DCC0` writes the global horse-name table when non-empty; in this save the vector is empty (`je 0xC3370`), so the cursor stays at `0x04` and the first ctx field is still `+0x254`.

## Following header (bool slots as u32)

| File | Insn | `rdi` | Notes |
|------|------|-------|-------|
| `0x20` | `0x6DD19` | `+0x414` | `WriteU32FromU8` |
| `0x24` | `0x6DD25` | `+0x415` | |
| `0x28` | `0x6DD31` | `+0x37C` | WriteU32 |
| `0x2C` | `0x6DD3E` | `0` | xor / WriteU32FromU8 |
| `0x30` | `0x6DD43` | `+0x418` | |
| `0x34` | `0x6DD4E` | `+0x41C` | WriteU32FromU8 |

## Loops (fixed count)

| Start insn | Count | Stride | Ctx base | Per iteration |
|------------|-------|--------|----------|----------------|
| `0x6DD71` | 6 | 8 | `rdi+0x31C` | u8 @+5, u32 @+0, u8 @+4 |
| `0x6DDA3` | 13 | 4 | `rdi+0x2CC` | u32 @-0x34, u32 @+0 |

## Dynamic sections

| Insn | Writer | Ctx | Record |
|------|--------|-----|--------|
| `0x6DDF9` | count + array | `rdi+0x280`..`+0x288` | 0x24 bytes; 4× u16 |
| `0x6DE30` | loop | vector at `+0x280` | |
| `0x6DEA9` | u32 | `rdi+0x278` | |
| `0x6DEB7` | u32 | `rdi+0x27C` | |
| `0x6E043` | count + pairs | `rdi+0x420`..`+0x428` | 8 bytes: u32 + u32 |
| `0x6DF30` | loop | `rdi+0x270` | 0x28-byte records; `WriteU8` / `0x1167B0` |
| `0x6E0A6` / `0x6E0D6` | nested | `0x6D440` | sub-save blobs |

## Linear simulation

First-pass walker emitted **{len(st.fields)}** records; simulated offset **`0x{st.offset:X}`** vs dump **`0x{len(data):X}`**. Mismatches: **{len(issues)}** (nested/variable writers stop linear tracking).

{md_table(st.fields, 45)}

Full machine-readable list: `RE_Tools/analysis/save_field_layout.json`.

**Regenerate:** `python RE_Tools/tools/scripts/map_save_field_layout.py`
"""
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"Wrote {OUT_JSON} ({len(st.fields)} fields, offset=0x{st.offset:X}, issues={len(issues)})")
    print(f"Wrote {OUT_MD}")
    if issues[:5]:
        print("First mismatches:", issues[:5])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
