"""
Capstone: Game_WorldSimStep @ 0x88510 and callers.

Outputs:
  RE_Tools/analysis/phase1_world_sim_step.json
  RE_Tools/analysis/disasm_world_sim_step.txt
  RE_Tools/docs/Game_WorldSimStep.md
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_64, Cs

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
from paths import get_exe_path  # noqa: E402

IMAGE_BASE = 0x140000000
SIM_RVA = 0x88510
UPDATE_WORLD_RVA = 0x87510
MAX_SPAN = 0x2500
OUT_JSON = ROOT / "RE_Tools" / "analysis" / "phase1_world_sim_step.json"
OUT_TXT = ROOT / "RE_Tools" / "analysis" / "disasm_world_sim_step.txt"
OUT_MD = ROOT / "RE_Tools" / "docs" / "Game_WorldSimStep.md"

INTERNAL = {
    0x87510: "Game_UpdateWorld",
    0x88510: "Game_WorldSimStep",
    0x03F290: "Game_UpdatePrologue",
    0x251850: "LogHelper_251850",
    0x098040: "Game_AuxUpdate_98040",
    0xC12D0: "Game_SimStep_C12D0",
    0xBFFA0: "Game_PostSwapHook",
    0xBE0F0: "GameMain_InitAndLoop",
    0x3EE50: "Game_LoadAssets",
    0x97110: "GameState_InitMain",
}


def disasm_region(pe: pefile.PE, raw: bytes, start: int, size: int) -> list[tuple[int, str, str]]:
    off = pe.get_offset_from_rva(start)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    out = []
    for i in md.disasm(raw[off : off + size], IMAGE_BASE + start):
        out.append((i.address - IMAGE_BASE, i.mnemonic, i.op_str))
    return out


def find_function_end(insns: list[tuple[int, str, str]], start: int) -> int:
    end = start
    for rva, mn, _ in insns:
        if rva < start:
            continue
        end = rva
        if mn == "int3" and rva > start + 0x30:
            return rva
    return end


def scan_callers(raw: bytes, pe: pefile.PE, target_rva: int) -> list[dict]:
    """Find E8 rel32 calls to target_rva in .text."""
    text = None
    for sec in pe.sections:
        if sec.Name.rstrip(b"\x00") == b".text":
            text = sec
            break
    if not text:
        return []
    base = pe.OPTIONAL_HEADER.ImageBase + text.VirtualAddress
    off = text.PointerToRawData
    size = text.SizeOfRawData
    blob = raw[off : off + size]
    text_rva = text.VirtualAddress
    hits = []
    for i in range(len(blob) - 5):
        if blob[i] != 0xE8:
            continue
        rel = int.from_bytes(blob[i + 1 : i + 5], "little", signed=True)
        call_rva = text_rva + i
        dest = call_rva + 5 + rel
        if dest == target_rva:
            hits.append({"call_site_rva": hex(call_rva), "va": hex(IMAGE_BASE + call_rva)})
    return hits


def resolve_call(op_str: str, exp: dict[int, str]) -> str:
    m = re.match(r"0x([0-9a-fA-F]+)", op_str.strip())
    if not m:
        return op_str
    va = int(m.group(1), 16)
    rva = va - IMAGE_BASE if va >= IMAGE_BASE else va
    return exp.get(rva) or INTERNAL.get(rva) or hex(rva)


def main() -> int:
    pe = pefile.PE(str(get_exe_path()))
    raw = Path(get_exe_path()).read_bytes()
    exp = {}
    if hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
        for s in pe.DIRECTORY_ENTRY_EXPORT.symbols:
            if s.name:
                exp[s.address] = s.name.decode()

    insns = disasm_region(pe, raw, SIM_RVA, MAX_SPAN)
    end = find_function_end(insns, SIM_RVA)
    fn_insns = [(r, m, o) for r, m, o in insns if SIM_RVA <= r <= end]

    calls = []
    for rva, mn, ops in fn_insns:
        if mn == "call":
            calls.append({"at": hex(rva), "target": resolve_call(ops, exp), "raw": ops})

    callers = scan_callers(raw, pe, SIM_RVA)
    uw_insns = disasm_region(pe, raw, UPDATE_WORLD_RVA, 0x400)
    uw_calls = [
        {"at": hex(r), "target": resolve_call(o, exp)}
        for r, mn, o in uw_insns
        if UPDATE_WORLD_RVA <= r < UPDATE_WORLD_RVA + 0x400 and mn == "call"
    ]

    payload = {
        "function": "Game_WorldSimStep",
        "rva": hex(SIM_RVA),
        "end_rva": hex(end),
        "size_bytes": end - SIM_RVA,
        "callers_e8": callers,
        "callees": calls,
        "callee_counts": dict(Counter(c["target"] for c in calls).most_common(25)),
        "Game_UpdateWorld_calls": uw_calls,
        "Game_UpdateWorld_calls_sim": [
            c for c in uw_calls if c["target"] == "Game_WorldSimStep" or c["target"] == hex(SIM_RVA)
        ],
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [f"# Game_WorldSimStep @ 0x{SIM_RVA:X}", ""]
    for rva, mn, ops in fn_insns:
        ann = ""
        if mn == "call":
            ann = f"  ; -> {resolve_call(ops, exp)}"
        lines.append(f"0x{rva:08X}: {mn:8} {ops}{ann}")
    OUT_TXT.write_text("\n".join(lines), encoding="utf-8")

    top = Counter(c["target"] for c in calls).most_common(12)
    md = [
        "# `Game_WorldSimStep` @ `0x88510`",
        "",
        "**Capstone** on `Game/Horsey.exe` · **Primary caller:** `Game_UpdateWorld` @ `0x875FA`",
        "",
        f"**Span:** `0x{SIM_RVA:X}`–`0x{end:X}` ({end - SIM_RVA} bytes)",
        "",
        f"**Artifacts:** `{OUT_JSON.relative_to(ROOT)}`, `{OUT_TXT.relative_to(ROOT)}`",
        "",
        "## Callers (E8 scan)",
        "",
    ]
    for c in callers:
        md.append(f"- `{c['call_site_rva']}`")
    md.extend(["", "## Top callees", "", "| Callee | Count |", "|--------|-------|"])
    for tgt, n in top:
        md.append(f"| `{tgt}` | {n} |")
    md.extend(
        [
            "",
            "## `Game_UpdateWorld` integration",
            "",
            f"Called from `Game_UpdateWorld` when normalized window delta non-zero (`call` @ `0x875FA`).",
            "",
            "See [Game_UpdateWorld.md](Game_UpdateWorld.md). Frida: `frida_world_sim_step.py`.",
            "",
            "## Ghidra rename",
            "",
            "| From | To |",
            "|------|-----|",
            "| `FUN_140088510` | `Game_WorldSimStep` |",
            "",
        ]
    )
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote {OUT_JSON}, span=0x{end - SIM_RVA:X}, callers={len(callers)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
