"""
Capstone: Game_LoadAssets @ 0x3EE50, GameState_InitMain @ 0x97110 (bootstrap tail).

Outputs:
  RE_Tools/analysis/phase1_bootstrap_tail.json
  RE_Tools/analysis/disasm_Game_LoadAssets.txt
  RE_Tools/analysis/disasm_GameState_InitMain.txt
  RE_Tools/docs/Game_LoadAssets.md
  RE_Tools/docs/GameState_InitMain.md
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_64, Cs
from capstone.x86 import X86_OP_MEM, X86_REG_RIP

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
from paths import get_exe_path  # noqa: E402

IMAGE_BASE = 0x140000000
LOAD_ASSETS = 0x3EE50
INIT_MAIN = 0x97110
BOOTSTRAP = 0x874B0
MAX_SPAN = 0x8000
STRING_LO, STRING_HI = 0x262000, 0x268000

INTERNAL = {
    0x874B0: "Game_BootstrapWorld",
    0x3EE50: "Game_LoadAssets",
    0x97110: "GameState_InitMain",
    0x96D20: "GameState_Ctor",
    0xC1850: "Game_InitCore",
    0xC3C10: "Game_InitRender",
    0xC3A70: "Game_FrameFinalize",
    0x6E2B0: "Save_Load",
    0x6DAB0: "Save_Write",
    0x103B84: "Game_LoadSaveChain",
    0x9828C: "Startup_SaveWrite_Call",
    0x27F70: "PathJoin",
    0xBF2C6: "FontPath_Builder",
    0x6F3C0: "FileWrite_6F3C0",
    0xBE0F0: "GameMain_InitAndLoop",
}


def read_cstring(raw: bytes, pe: pefile.PE, rva: int) -> str | None:
    try:
        off = pe.get_offset_from_rva(rva)
    except Exception:
        return None
    if off is None:
        return None
    chunk = raw[off : off + 128]
    end = chunk.find(b"\x00")
    if end < 0:
        return None
    return chunk[:end].decode("utf-8", errors="replace")


def disasm_fn_fixed(pe: pefile.PE, raw: bytes, start: int) -> list[tuple[int, str, str]]:
    off = pe.get_offset_from_rva(start)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    insns: list[tuple[int, str, str]] = []
    last_ret = start
    for i in md.disasm(raw[off : off + MAX_SPAN], IMAGE_BASE + start):
        rva = i.address - IMAGE_BASE
        insns.append((rva, i.mnemonic, i.op_str))
        if i.mnemonic == "ret":
            last_ret = rva
        if i.mnemonic == "int3" and rva > last_ret + 4 and rva > start + 0x2000:
            break
    return insns


def rip_strings(pe: pefile.PE, raw: bytes, start: int) -> list[dict]:
    off = pe.get_offset_from_rva(start)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    hits = []
    for i in md.disasm(raw[off : off + MAX_SPAN], IMAGE_BASE + start):
        rva = i.address - IMAGE_BASE
        if not i.operands:
            continue
        for op in i.operands:
            if op.type != X86_OP_MEM or op.mem.base != X86_REG_RIP:
                continue
            tgt = rva + i.size + op.mem.disp
            if STRING_LO <= tgt <= STRING_HI:
                s = read_cstring(raw, pe, tgt)
                if s and len(s) >= 2 and s.isprintable():
                    hits.append({"at": hex(rva), "rva": hex(tgt), "text": s})
        if i.mnemonic == "int3" and rva > start + 0x80:
            break
    return hits


def scan_callers(raw: bytes, pe: pefile.PE, target: int) -> list[str]:
    text = next(s for s in pe.sections if s.Name.rstrip(b"\x00") == b".text")
    blob = raw[text.PointerToRawData : text.PointerToRawData + text.SizeOfRawData]
    base = text.VirtualAddress
    hits = []
    for i in range(len(blob) - 5):
        if blob[i] != 0xE8:
            continue
        rel = int.from_bytes(blob[i + 1 : i + 5], "little", signed=True)
        if base + i + 5 + rel == target:
            hits.append(hex(base + i))
    return hits[:40]


def resolve_call(op_str: str, exp: dict[int, str]) -> str:
    m = re.match(r"0x([0-9a-fA-F]+)", op_str.strip())
    if not m:
        return op_str
    va = int(m.group(1), 16)
    rva = va - IMAGE_BASE if va >= IMAGE_BASE else va
    return exp.get(rva) or INTERNAL.get(rva) or hex(rva)


def analyze_one(pe: pefile.PE, raw: bytes, exp: dict, name: str, rva: int) -> dict:
    insns = disasm_fn_fixed(pe, raw, rva)
    end = insns[-1][0] if insns else rva
    calls = [
        {"at": hex(a), "target": resolve_call(o, exp)}
        for a, mn, o in insns
        if mn == "call"
    ]
    jmps = [
        {"at": hex(a), "target": resolve_call(o, exp)}
        for a, mn, o in insns
        if mn in ("jmp", "je", "jne", "ja", "jz", "jnz")
        and o.startswith("0x")
    ]
    return {
        "name": name,
        "rva": hex(rva),
        "end_rva": hex(end),
        "size": end - rva,
        "callers_e8": scan_callers(raw, pe, rva),
        "calls": calls,
        "call_counts": dict(Counter(c["target"] for c in calls).most_common(20)),
        "tail_jmp": [j for j in jmps if "jmp" in j][-3:] if jmps else [],
        "strings": rip_strings(pe, raw, rva)[:60],
    }


def write_disasm(path: Path, title: str, insns: list, exp: dict, strings: list) -> None:
    str_at = {int(h["at"], 16): h["text"] for h in strings}
    lines = [f"# {title}", ""]
    for rva, mn, ops in insns:
        ann = ""
        if rva in str_at:
            ann = f'  ; "{str_at[rva]}"'
        if mn == "call":
            ann = f"  ; -> {resolve_call(ops, exp)}"
        lines.append(f"0x{rva:08X}: {mn:8} {ops}{ann}")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_md(path: Path, info: dict, extra: str) -> None:
    lines = [
        f"# `{info['name']}` @ `{info['rva']}`",
        "",
        f"**Capstone** on `Game/Horsey.exe` · span `{info['rva']}`–`{info['end_rva']}` ({info['size']} B)",
        "",
        extra,
        "",
        "## Callers (E8)",
        "",
    ]
    for c in info["callers_e8"][:15]:
        lines.append(f"- `{c}`")
    lines.extend(["", "## Callees (top)", "", "| Target | Count |", "|--------|-------|"])
    for t, n in list(info["call_counts"].items())[:15]:
        lines.append(f"| `{t}` | {n} |")
    if info["strings"]:
        lines.extend(["", "## Strings (sample)", ""])
        for s in info["strings"][:25]:
            lines.append(f"- `{s['text']}` @ `{s['rva']}`")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    pe = pefile.PE(str(get_exe_path()))
    raw = Path(get_exe_path()).read_bytes()
    exp = {}
    if hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
        for s in pe.DIRECTORY_ENTRY_EXPORT.symbols:
            if s.name:
                exp[s.address] = s.name.decode()

    load = analyze_one(pe, raw, exp, "Game_LoadAssets", LOAD_ASSETS)
    init = analyze_one(pe, raw, exp, "GameState_InitMain", INIT_MAIN)
    boot_calls = analyze_one(pe, raw, exp, "Game_BootstrapWorld", BOOTSTRAP)

    payload = {
        "Game_BootstrapWorld": {
            "rva": hex(BOOTSTRAP),
            "calls": boot_calls["calls"],
            "tail": "jmp 0x97110 @ 0x874FF (Capstone)",
        },
        "Game_LoadAssets": load,
        "GameState_InitMain": init,
    }
    out_json = ROOT / "RE_Tools" / "analysis" / "phase1_bootstrap_tail.json"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    load_ins = disasm_fn_fixed(pe, raw, LOAD_ASSETS)
    init_ins = disasm_fn_fixed(pe, raw, INIT_MAIN)
    write_disasm(
        ROOT / "RE_Tools" / "analysis" / "disasm_Game_LoadAssets.txt",
        "Game_LoadAssets",
        load_ins,
        exp,
        load["strings"],
    )
    write_disasm(
        ROOT / "RE_Tools" / "analysis" / "disasm_GameState_InitMain.txt",
        "GameState_InitMain",
        init_ins,
        exp,
        init["strings"],
    )

    write_md(
        ROOT / "RE_Tools" / "docs" / "Game_LoadAssets.md",
        load,
        "**Role:** load `Game/data/` assets during `Game_BootstrapWorld` @ `0x874B0` (call @ `0x874BE3`).",
    )
    write_md(
        ROOT / "RE_Tools" / "docs" / "GameState_InitMain.md",
        init,
        "**Role:** tail of bootstrap — entered via **`jmp`** from `0x874FF`, not `call`. "
        "Likely loads save / enters playable state (see `Save_Load`, `0x103B84` in callees).",
    )

    # Update Game_BootstrapWorld.md checklist
    gbw = ROOT / "RE_Tools" / "docs" / "Game_BootstrapWorld.md"
    text = gbw.read_text(encoding="utf-8")
    text = text.replace(
        "- [ ] Decompile **`0x97110`** (`GameState_InitMain`) — where bootstrap returns into playable state\n"
        "- [ ] Decompile **`0x3EE50`** (`Game_LoadAssets`) — ties to `Game/data/` loaders\n",
        "- [x] Capstone **`0x97110`** — [GameState_InitMain.md](GameState_InitMain.md)\n"
        "- [x] Capstone **`0x3EE50`** — [Game_LoadAssets.md](Game_LoadAssets.md)\n",
    )
    gbw.write_text(text, encoding="utf-8")

    print(f"Wrote {out_json}")
    print(f"  LoadAssets: {load['size']} B, {len(load['calls'])} calls")
    print(f"  InitMain: {init['size']} B, callers={init['callers_e8']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
