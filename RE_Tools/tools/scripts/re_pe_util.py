"""Shared PE/Capstone helpers for HorseSDK RE scripts."""
from __future__ import annotations

import re
import struct
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_64, Cs
from capstone.x86 import X86_OP_MEM, X86_REG_RIP

IMAGE_BASE = 0x140000000


def load_pe(exe: Path | None = None) -> tuple[pefile.PE, bytes]:
    from paths import get_exe_path  # noqa: WPS433

    path = exe or get_exe_path()
    pe = pefile.PE(str(path))
    raw = Path(path).read_bytes()
    return pe, raw


def text_section(pe: pefile.PE) -> tuple[bytes, int]:
    sec = next(s for s in pe.sections if s.Name.rstrip(b"\x00") == b".text")
    return sec.get_data(), sec.VirtualAddress


def scan_e8_callers(raw: bytes, pe: pefile.PE, target_rva: int) -> list[int]:
    blob, base = text_section(pe)
    hits: list[int] = []
    for i in range(len(blob) - 5):
        if blob[i] != 0xE8:
            continue
        rel = struct.unpack_from("<i", blob, i + 1)[0]
        if base + i + 5 + rel == target_rva:
            hits.append(base + i)
    return hits


def scan_e9_jumps(raw: bytes, pe: pefile.PE, target_rva: int) -> list[int]:
    blob, base = text_section(pe)
    hits: list[int] = []
    for i in range(len(blob) - 5):
        if blob[i] != 0xE9:
            continue
        rel = struct.unpack_from("<i", blob, i + 1)[0]
        if base + i + 5 + rel == target_rva:
            hits.append(base + i)
    return hits


def scan_rip_refs(raw: bytes, pe: pefile.PE, target_rva: int, window: int = 0) -> list[dict]:
    """RIP-relative memory operands pointing at target_rva (+/- window)."""
    blob, base = text_section(pe)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    hits: list[dict] = []
    chunk = 0x10000
    for start in range(0, len(blob), chunk):
        sub = blob[start : start + chunk + 64]
        for i in md.disasm(sub, IMAGE_BASE + base + start):
            rva = i.address - IMAGE_BASE
            if rva < base or rva >= base + len(blob):
                continue
            for op in i.operands or []:
                if op.type != X86_OP_MEM or op.mem.base != X86_REG_RIP:
                    continue
                tgt = rva + i.size + op.mem.disp
                if abs(tgt - target_rva) <= window:
                    hits.append(
                        {
                            "at": hex(rva),
                            "insn": f"{i.mnemonic} {i.op_str}",
                            "target": hex(tgt),
                        }
                    )
    return hits


def disasm_range(raw: bytes, pe: pefile.PE, start: int, max_span: int = 0x4000) -> list[tuple[int, str, str]]:
    off = pe.get_offset_from_rva(start)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    insns: list[tuple[int, str, str]] = []
    last_ret = start
    for i in md.disasm(raw[off : off + max_span], IMAGE_BASE + start):
        rva = i.address - IMAGE_BASE
        insns.append((rva, i.mnemonic, i.op_str))
        if i.mnemonic == "ret":
            last_ret = rva
        if i.mnemonic == "int3" and rva > last_ret + 4 and rva > start + 0x100:
            break
    return insns


def resolve_call(op_str: str, names: dict[int, str]) -> str:
    m = re.match(r"0x([0-9a-fA-F]+)", op_str.strip())
    if not m:
        return op_str
    va = int(m.group(1), 16)
    rva = va - IMAGE_BASE if va >= IMAGE_BASE else va
    return names.get(rva, hex(rva))
