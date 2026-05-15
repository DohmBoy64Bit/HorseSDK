"""
Capstone deep analysis for Phase 1 (replaces Ghidra for listed tasks).

Outputs:
  RE_Tools/analysis/phase1_gamemain_loop.json
  RE_Tools/analysis/phase1_save_flow.json
  RE_Tools/analysis/phase1_font_xrefs.json
  RE_Tools/analysis/phase1_crf_loader.json
  RE_Tools/analysis/disasm_phase1_extended.txt
"""
from __future__ import annotations

import json
import struct
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_64, Cs
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
from paths import get_exe_path  # noqa: E402

IMAGE_BASE = 0x140000000
OUT_DIR = ROOT / "RE_Tools" / "analysis"

# --- string targets (RVA from pefile scan May 2026) ---
FONT_STRINGS = {
    "quip.crf": 0x980DE,
    ".crf": 0x980E2,
    "n64.fnt": 0x2658A8,
    "n64_0.png": 0x265A80,
    "genes.dat": 0x266120,
}
DATA_STRING_POOL = (0x262000, 0x268000)  # rdata cluster for path templates


@dataclass
class Insn:
    rva: int
    mnemonic: str
    op_str: str
    size: int


def disasm_region(pe: pefile.PE, raw: bytes, rva: int, size: int) -> list[Insn]:
    off = pe.get_offset_from_rva(rva)
    if off is None:
        return []
    chunk = raw[off : off + size]
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    out: list[Insn] = []
    for i in md.disasm(chunk, IMAGE_BASE + rva):
        out.append(Insn(i.address - IMAGE_BASE, i.mnemonic, i.op_str, i.size))
    return out


def rip_target(insn_rva: int, insn_size: int, disp: int) -> int:
    return insn_rva + insn_size + disp


def find_function_bounds(insns: list[Insn], start_rva: int, max_insns: int = 8000) -> tuple[int, int]:
    """From start_rva until int3 padding or ret with balanced stack (heuristic)."""
    started = False
    end = start_rva
    ret_count = 0
    for ins in insns:
        if ins.rva < start_rva:
            continue
        if not started:
            if ins.rva == start_rva:
                started = True
            else:
                continue
        end = ins.rva + ins.size
        if ins.mnemonic == "ret":
            ret_count += 1
            if ret_count >= 1 and ins.rva > start_rva + 0x80:
                break
        if ins.mnemonic == "int3" and ins.rva > start_rva + 0x40:
            break
        if ins.rva - start_rva > max_insns:
            break
    return start_rva, end


def analyze_gamemain(pe: pefile.PE, raw: bytes) -> dict:
    start = 0xBE0F0
    insns = disasm_region(pe, raw, start, 0x1200)
    bounds = find_function_bounds(insns, start, 10000)

    branches: list[dict] = []
    calls: list[dict] = []
    loop_targets: Counter = defaultdict(int)

    for ins in insns:
        if ins.rva < start or ins.rva > bounds[1]:
            continue
        if ins.mnemonic.startswith("j"):
            # parse target from op_str "0x1400bece7" or "0xbece7"
            parts = ins.op_str.replace("0x", "").split()
            tgt_s = parts[0] if parts else ""
            try:
                tgt = int(tgt_s, 16)
                if tgt > IMAGE_BASE:
                    tgt -= IMAGE_BASE
                loop_targets[tgt] += 1
                branches.append(
                    {
                        "from": hex(ins.rva),
                        "mnemonic": ins.mnemonic,
                        "to": hex(tgt),
                    }
                )
            except ValueError:
                pass
        if ins.mnemonic == "call":
            calls.append({"from": hex(ins.rva), "to": ins.op_str})

    # Frame loop region (Frida-confirmed)
    frame_insns = [i for i in insns if 0xBEA80 <= i.rva <= 0xBED50]
    exit_rets = [hex(i.rva) for i in insns if i.mnemonic == "ret" and start <= i.rva <= 0xBE300]

    return {
        "function_rva": hex(start),
        "disasm_end_rva": hex(bounds[1]),
        "early_exit_rets": [hex(0xBE11A), hex(0xBE148)],
        "all_rets_in_scan": exit_rets,
        "frame_loop_back_edges": [
            {"to": hex(t), "count": c}
            for t, c in sorted(loop_targets.items(), key=lambda x: -x[1])
            if 0xBEA00 <= t <= 0xBEE00
        ],
        "key_branches": [b for b in branches if 0xBEA00 <= int(b["from"], 16) <= 0xBED50][:40],
        "frame_loop_summary": {
            "poll_first": hex(0xBEA8A),
            "poll_drain": hex(0xBEAA5),
            "swap_call": hex(0xBEAF0),
            "loop_jump": hex(0xBECE7),
            "exit_via": "je 0xBECE7 from 0xBEAE7 when quit flag set; early ret @ 0xBE11A (Steam restart), 0xBE148 (SDL init fail)",
        },
        "top_calls_in_frame": [c for c in calls if 0xBEA00 <= int(c["from"], 16) <= 0xBED50][:30],
    }


def analyze_save(pe: pefile.PE, raw: bytes) -> dict:
    start = 0x6DAB0
    insns = disasm_region(pe, raw, start, 0x1800)
    bounds = find_function_bounds(insns, start, 15000)

    callees: list[dict] = []
    rip_strings: list[dict] = []
    for ins in insns:
        if ins.rva < start or ins.rva > bounds[1]:
            continue
        if ins.mnemonic == "call":
            callees.append({"at": hex(ins.rva), "target": ins.op_str})
        if "rip" in ins.op_str and ins.mnemonic in ("lea", "mov", "cmp"):
            # re-parse with capstone for disp
            pass

    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    off = pe.get_offset_from_rva(start)
    chunk = raw[off : off + 0x1800]
    for i in md.disasm(chunk, IMAGE_BASE + start):
        rva = i.address - IMAGE_BASE
        if rva > bounds[1]:
            break
        for op in i.operands:
            if op.type != X86_OP_MEM or op.mem.base != X86_REG_RIP:
                continue
            ref = rip_target(rva, i.size, op.mem.disp)
            if 0x262000 <= ref <= 0x264000 or ref in FONT_STRINGS.values():
                rip_strings.append(
                    {"insn": hex(rva), "mnemonic": i.mnemonic, "string_rva": hex(ref)}
                )

    # Disasm key callees
    callee_rvas = [0x6F3C0, 0x88000, 0x0BEE80, 0x0BFB60]
    callee_snippets: dict[str, list[str]] = {}
    for cr in callee_rvas:
        ci = disasm_region(pe, raw, cr, 0x120)
        callee_snippets[hex(cr)] = [f"{hex(x.rva)}: {x.mnemonic} {x.op_str}" for x in ci[:40]]

    return {
        "function_rva": hex(start),
        "disasm_end_rva": hex(bounds[1]),
        "signature": "Save_Write(void* ctx /*rcx*/, int flags /*edx*/)",
        "callees": callees[:80],
        "rip_refs_in_save": rip_strings[:50],
        "callee_entry_snippets": callee_snippets,
        "write_chain_hypothesis": [
            "0x6DB7E call 0x88000 — build path/std::string",
            "0x6DB86 call 0xBFB60 — helper",
            "0x6DB95 call 0x6F3C0 — serialize/write buffer",
        ],
    }


def scan_string_pool_xrefs(pe: pefile.PE) -> list[dict]:
    """All RIP-relative refs into data string pool + font string RVAs."""
    hits: list[dict] = []
    font_vas = {IMAGE_BASE + r for r in FONT_STRINGS.values()}
    lo, hi = DATA_STRING_POOL

    for section in pe.sections:
        if not section.Name.startswith(b".text"):
            continue
        code = section.get_data()
        base_va = IMAGE_BASE + section.VirtualAddress
        md = Cs(CS_ARCH_X86, CS_MODE_64)
        md.detail = True
        for insn in md.disasm(code, base_va):
            rva = insn.address - IMAGE_BASE
            for op in insn.operands:
                if op.type != X86_OP_MEM or op.mem.base != X86_REG_RIP:
                    continue
                ref_rva = rip_target(rva, insn.size, op.mem.disp)
                ref_va = IMAGE_BASE + ref_rva
                in_font = ref_va in font_vas
                in_pool = lo <= ref_rva <= hi
                in_low = 0x97000 <= ref_rva <= 0x99000  # quip.crf cluster
                if in_font or in_pool or in_low:
                    label = next((k for k, v in FONT_STRINGS.items() if v == ref_rva), None)
                    hits.append(
                        {
                            "insn_rva": hex(rva),
                            "mnemonic": insn.mnemonic,
                            "op_str": insn.op_str,
                            "ref_rva": hex(ref_rva),
                            "string": label,
                        }
                    )
    return hits


def find_callers_of(pe: pefile.PE, target_rva: int) -> list[int]:
    base = pe.OPTIONAL_HEADER.ImageBase
    target_va = base + target_rva
    hits: list[int] = []
    for section in pe.sections:
        if not section.Name.startswith(b".text"):
            continue
        data = section.get_data()
        sec_rva = section.VirtualAddress
        for off in range(len(data) - 5):
            if data[off] != 0xE8:
                continue
            disp = struct.unpack_from("<i", data, off + 1)[0]
            src = base + sec_rva + off
            if src + 5 + disp == target_va:
                hits.append(sec_rva + off)
    return hits


def analyze_font_loaders(pe: pefile.PE, raw: bytes, pool_hits: list[dict]) -> dict:
    font_hits = [h for h in pool_hits if h.get("string")]
    # For each font hit, find containing function (scan back for int3/ret or common prologue)
    loaders: list[dict] = []
    for h in font_hits:
        insn_rva = int(h["insn_rva"], 16)
        callers = find_callers_of(pe, insn_rva)  # who calls this line - rare
        # scan backward for function start (push rbp / sub rsp pattern)
        insns = disasm_region(pe, raw, max(0, insn_rva - 0x200), 0x280)
        func_start = insn_rva
        for ins in reversed(insns):
            if ins.rva >= insn_rva:
                continue
            if ins.mnemonic == "push" and "rbp" in ins.op_str:
                func_start = ins.rva
                break
            if ins.mnemonic == "int3":
                func_start = ins.rva + ins.size
                break
        snippet = disasm_region(pe, raw, func_start, 0x180)
        loaders.append(
            {
                "string": h["string"],
                "ref_rva": h["ref_rva"],
                "use_site": h["insn_rva"],
                "function_start_guess": hex(func_start),
                "callers_to_use_site": [hex(c) for c in callers[:5]],
                "disasm": [f"{hex(s.rva)}: {s.mnemonic} {s.op_str}" for s in snippet[:35]],
            }
        )

    # Also: who calls functions that reference .crf
    crf_users = [l for l in loaders if l["string"] in (".crf", "quip.crf")]
    return {
        "font_string_uses": loaders,
        "crf_loader_candidates": crf_users,
        "note": "function_start_guess = scan back to push rbp / int3",
    }


def analyze_crf_from_loader(loader: dict, pe: pefile.PE, raw: bytes) -> dict:
    """If we found a loader, scan its callees for read loops matching section1."""
    if not loader:
        return {"status": "no_loader_found"}
    start = int(loader["function_start_guess"], 16)
    insns = disasm_region(pe, raw, start, 0x400)
    calls = [i for i in insns if i.mnemonic == "call"]
    return {
        "loader_start": hex(start),
        "calls_in_loader": [{"at": hex(c.rva), "to": c.op_str} for c in calls[:25]],
        "crf_section1_markers": "09 00 f8 / 07 00 f9 — see crf_opcode_trace.json",
        "match_strategy": "Grep loader for fread/ReadFile size=16 header then section1_bytes",
    }


def main() -> int:
    pe = pefile.PE(str(get_exe_path()))
    raw = Path(get_exe_path()).read_bytes()

    gamemain = analyze_gamemain(pe, raw)
    save_flow = analyze_save(pe, raw)
    pool_hits = scan_string_pool_xrefs(pe)
    font = analyze_font_loaders(pe, raw, pool_hits)
    crf_loader = font["crf_loader_candidates"][0] if font["crf_loader_candidates"] else None
    crf = analyze_crf_from_loader(crf_loader, pe, raw)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "phase1_gamemain_loop.json").write_text(json.dumps(gamemain, indent=2), encoding="utf-8")
    (OUT_DIR / "phase1_save_flow.json").write_text(json.dumps(save_flow, indent=2), encoding="utf-8")
    (OUT_DIR / "phase1_font_xrefs.json").write_text(
        json.dumps({"pool_hits_count": len(pool_hits), "font": font, "all_pool_hits_sample": pool_hits[:60]}, indent=2),
        encoding="utf-8",
    )
    (OUT_DIR / "phase1_crf_loader.json").write_text(json.dumps(crf, indent=2), encoding="utf-8")

    # Extended disasm text
    lines = ["# Extended disasm\n"]
    for name, rva, size in [
        ("GameMain", 0xBE0F0, 0x500),
        ("FrameLoop", 0xBEA80, 0x280),
        ("Save_Write", 0x6DAB0, 0x400),
        ("FileWrite_6F3C0", 0x6F3C0, 0x200),
        ("StringFormat_88000", 0x88000, 0x120),
    ]:
        lines.append(f"\n## {name} @ 0x{rva:X}\n")
        for ins in disasm_region(pe, raw, rva, size):
            lines.append(f"0x{ins.rva:08X}: {ins.mnemonic:8} {ins.op_str}")
    (OUT_DIR / "disasm_phase1_extended.txt").write_text("\n".join(lines), encoding="utf-8")

    print("Wrote phase1_* JSON + disasm_phase1_extended.txt")
    print(f"  GameMain loop backs: {gamemain.get('frame_loop_back_edges', [])[:5]}")
    print(f"  Font string uses: {len(font.get('font_string_uses', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
