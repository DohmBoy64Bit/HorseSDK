"""
Deep static analysis: GameMain init_body, Game_DispatchSdlEvent, helpers.

Outputs:
  RE_Tools/analysis/phase1_gamemain_init.json
  RE_Tools/analysis/phase1_sdl_event_dispatch.json
  RE_Tools/analysis/disasm_gamemain_init.txt
  RE_Tools/analysis/disasm_sdl_event_dispatch.txt
  RE_Tools/docs/GameLoop_Static.md  (pseudocode from Capstone — not Ghidra)
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_64, Cs
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
from paths import get_exe_path  # noqa: E402

IMAGE_BASE = 0x140000000
OUT = ROOT / "RE_Tools" / "analysis"
DOCS = ROOT / "RE_Tools" / "docs"

INTERNAL = {
    0x711B0: "SettingsLoader",
    0x87510: "Game_UpdateWorld",
    0xC0430: "Game_DispatchSdlEvent",
    0xBFFA0: "Game_PostSwapHook",
    0xC12D0: "Game_SimStep",
    0xC3A70: "Game_FrameFinalize",
    0xBEEA0: "Loop_Helper_BEEA0",
    0x6DAB0: "Save_Write",
    0x6F3C0: "FileWrite_6F3C0",
    0x88000: "StringFormat_88000",
    0xC0900: "Game_InitSubsystem_C0900",
    0x251CE0: "StdString_Assign",
    0x027F70: "PathJoin_027F70",
}

# SDL2 event type constants (for matching cmp immediates)
SDL_EVENTS = {
    0x100: "SDL_QUIT",
    0x200: "SDL_APP_TERMINATING",
    0x201: "SDL_APP_LOWMEMORY",
    0x202: "SDL_APP_WILLENTERBACKGROUND",
    0x203: "SDL_APP_DIDENTERBACKGROUND",
    0x204: "SDL_APP_WILLENTERFOREGROUND",
    0x205: "SDL_APP_DIDENTERFOREGROUND",
    0x206: "SDL_LOCALECHANGED",
    0x300: "SDL_KEYDOWN",
    0x301: "SDL_KEYUP",
    0x302: "SDL_TEXTEDITING",
    0x303: "SDL_TEXTINPUT",
    0x400: "SDL_WINDOWEVENT",
    0x401: "SDL_SYSWMEVENT",
    0x700: "SDL_MOUSEMOTION",
    0x800: "SDL_MOUSEBUTTONDOWN",
    0x801: "SDL_MOUSEBUTTONUP",
    0x802: "SDL_MOUSEWHEEL",
    0x900: "SDL_JOYAXISMOTION",
    0x1000: "SDL_FINGERDOWN",
    0x1100: "SDL_DROPFILE",
    0x1200: "SDL_AUDIODEVICEADDED",
    0x1500: "SDL_RENDER_TARGETS_RESET",
    0x1600: "SDL_USEREVENT",
}


@dataclass
class Insn:
    rva: int
    mnemonic: str
    op_str: str
    size: int


def disasm(pe: pefile.PE, raw: bytes, rva: int, size: int) -> list[Insn]:
    off = pe.get_offset_from_rva(rva)
    if off is None:
        return []
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    return [
        Insn(i.address - IMAGE_BASE, i.mnemonic, i.op_str, i.size)
        for i in md.disasm(raw[off : off + size], IMAGE_BASE + rva)
    ]


def exports(pe: pefile.PE) -> dict[int, str]:
    m = {}
    if hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
        for s in pe.DIRECTORY_ENTRY_EXPORT.symbols:
            if s.name:
                m[s.address] = s.name.decode()
    return m


def resolve_call(op_str: str, exp: dict[int, str]) -> str:
    m = re.match(r"0x([0-9a-fA-F]+)", op_str.strip())
    if not m:
        if "rip" in op_str:
            return "indirect/import"
        return op_str
    va = int(m.group(1), 16)
    rva = va - IMAGE_BASE if va >= IMAGE_BASE else va
    return exp.get(rva) or INTERNAL.get(rva) or hex(rva)


def find_function_end(insns: list[Insn], start: int, max_span: int = 0x2000) -> int:
    end = start
    for ins in insns:
        if ins.rva < start:
            continue
        if ins.rva - start > max_span:
            break
        end = ins.rva + ins.size
        if ins.mnemonic == "int3" and ins.rva > start + 0x20:
            break
    return end


def analyze_calls(insns: list[Insn], lo: int, hi: int, exp: dict[int, str]) -> list[dict]:
    out = []
    for ins in insns:
        if lo <= ins.rva <= hi and ins.mnemonic == "call":
            out.append({"at": hex(ins.rva), "target": resolve_call(ins.op_str, exp), "raw": ins.op_str})
    return out


def detect_sdl_switch(insns: list[Insn], exp: dict[int, str]) -> list[dict]:
    """Find cmp/test against SDL-ish immediates or [rdx] event.type reads."""
    hits = []
    for ins in insns:
        imm_val = None
        if ins.mnemonic in ("cmp", "test") and "," in ins.op_str:
            parts = [p.strip() for p in ins.op_str.split(",")]
            for p in parts:
                if p.startswith("0x"):
                    try:
                        imm_val = int(p, 16)
                    except ValueError:
                        pass
        # capstone detail for immediate operands
        md = Cs(CS_ARCH_X86, CS_MODE_64)
        md.detail = True
        # event.type often: cmp dword ptr [rdx], 0x400 or mov eax, [rdx]
        event_type_read = "[rdx]" in ins.op_str or "[rdx +" in ins.op_str
        label = SDL_EVENTS.get(imm_val) if imm_val else None
        if label or (event_type_read and ins.mnemonic in ("cmp", "sub", "mov")):
            hits.append(
                {
                    "rva": hex(ins.rva),
                    "insn": f"{ins.mnemonic} {ins.op_str}",
                    "sdl_event": label,
                    "imm": hex(imm_val) if imm_val else None,
                }
            )
    return hits


def branches_to(insns: list[Insn], lo: int, hi: int) -> dict[str, list[str]]:
    jmp = defaultdict(list)
    for ins in insns:
        if not (lo <= ins.rva <= hi) or not ins.mnemonic.startswith("j"):
            continue
        m = re.search(r"0x([0-9a-f]+)", ins.op_str, re.I)
        if m:
            tgt = int(m.group(1), 16)
            if tgt > IMAGE_BASE:
                tgt -= IMAGE_BASE
            jmp[hex(tgt)].append(f"{hex(ins.rva)}:{ins.mnemonic}")
    return dict(jmp)


def write_disasm(path: Path, title: str, insns: list[Insn], labels: dict[int, str] | None = None) -> None:
    labels = labels or {}
    lines = [f"# {title}", f"# Image base {hex(IMAGE_BASE)}\n"]
    for ins in insns:
        tag = labels.get(ins.rva, "")
        suffix = f"  ; {tag}" if tag else ""
        lines.append(f"0x{ins.rva:08X}: {ins.mnemonic:8} {ins.op_str}{suffix}")
    path.write_text("\n".join(lines), encoding="utf-8")


def build_init_pseudocode(calls: list[dict]) -> list[str]:
    lines = [
        "void GameMain_InitBody(void) {  // RVA 0xBE149 .. before frame loop @ 0xBEA7F",
        "  // Steam init, SDL_Init(0x4020), video GL attributes",
        "  // std::string path setup -> SettingsLoader @ 0x711B0 (0xBE562)",
    ]
    seen = set()
    for c in calls:
        t = c["target"]
        if t in seen:
            continue
        seen.add(t)
        if t.startswith("0x"):
            lines.append(f"  call {t};  // @ {c['at']}")
        else:
            lines.append(f"  {t}();  // call @ {c['at']}")
    lines.append("  // fall through to frame_loop @ 0xBEA7F")
    lines.append("}")
    return lines


def build_dispatch_pseudocode(switches: list[dict], calls: list[dict]) -> list[str]:
    lines = [
        "void Game_DispatchSdlEvent(GameContext* ctx, SDL_Event* ev) {  // 0xC0430",
        "  // rcx=ctx, rdx=ev — event.type @ [rdx+0]",
        "  switch (ev->type) {",
    ]
    for s in switches:
        if s.get("sdl_event"):
            lines.append(f"    case {s['imm']}:  // {s['sdl_event']} — cmp @ {s['rva']}")
    lines.append("    default: break;")
    lines.append("  }")
    for c in calls[:15]:
        lines.append(f"  // call {c['target']} @ {c['at']}")
    lines.append("}")
    return lines


def main() -> int:
    pe = pefile.PE(str(get_exe_path()))
    raw = Path(get_exe_path()).read_bytes()
    exp = exports(pe)

    # --- init body ---
    init_start, init_end = 0xBE149, 0xBEA7E
    init_insns = disasm(pe, raw, init_start, init_end - init_start + 0x40)
    init_calls = analyze_calls(init_insns, init_start, init_end, exp)
    init_payload = {
        "region": "GameMain_init_body",
        "rva_range": [hex(init_start), hex(init_end)],
        "call_count": len(init_calls),
        "calls_ordered": init_calls,
        "pseudocode_static": build_init_pseudocode(init_calls),
        "key_sites": {
            "SettingsLoader": "0xBE562 -> SettingsLoader @ 0x711B0",
            "horsey_tmx_string": "0x263850",
            "settings_xml_string": "0x263860",
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "phase1_gamemain_init.json").write_text(json.dumps(init_payload, indent=2), encoding="utf-8")
    write_disasm(OUT / "disasm_gamemain_init.txt", "GameMain init_body", init_insns)

    # --- SDL dispatch ---
    disp_start = 0xC0430
    disp_insns = disasm(pe, raw, disp_start, 0x800)
    disp_end = find_function_end(disp_insns, disp_start, 0x1500)
    disp_insns = [i for i in disp_insns if i.rva <= disp_end]
    disp_calls = analyze_calls(disp_insns, disp_start, disp_end, exp)

    # Enhanced switch detect with capstone immediates
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    off = pe.get_offset_from_rva(disp_start)
    switches = []
    for i in md.disasm(raw[off : off + 0x800], IMAGE_BASE + disp_start):
        rva = i.address - IMAGE_BASE
        if rva > disp_end:
            break
        for op in i.operands:
            if op.type == X86_OP_IMM:
                val = op.imm & 0xFFFFFFFF
                if val in SDL_EVENTS or (0x100 <= val <= 0x1700):
                    switches.append(
                        {
                            "rva": hex(rva),
                            "insn": f"{i.mnemonic} {i.op_str}",
                            "imm": hex(val),
                            "sdl_event": SDL_EVENTS.get(val),
                        }
                    )
        if i.mnemonic == "cmp" and "rdx" in i.op_str:
            switches.append(
                {
                    "rva": hex(rva),
                    "insn": f"{i.mnemonic} {i.op_str}",
                    "note": "likely compares ev->type or ev->window.event",
                }
            )

    # dedupe switches
    seen_s = set()
    uniq_sw = []
    for s in switches:
        k = (s["rva"], s.get("imm"))
        if k in seen_s:
            continue
        seen_s.add(k)
        uniq_sw.append(s)

    disp_payload = {
        "function": "Game_DispatchSdlEvent",
        "function_rva": "0xC0430",
        "span_estimate": [hex(disp_start), hex(disp_end)],
        "sdl_type_matches": [s for s in uniq_sw if s.get("sdl_event")],
        "cmp_on_event_ptr": [s for s in uniq_sw if s.get("note")],
        "all_switch_hints": uniq_sw[:60],
        "calls": disp_calls[:50],
        "pseudocode_static": build_dispatch_pseudocode(
            [s for s in uniq_sw if s.get("sdl_event")], disp_calls
        ),
        "jump_targets": branches_to(disp_insns, disp_start, disp_end),
    }
    (OUT / "phase1_sdl_event_dispatch.json").write_text(json.dumps(disp_payload, indent=2), encoding="utf-8")
    write_disasm(
        OUT / "disasm_sdl_event_dispatch.txt",
        "Game_DispatchSdlEvent",
        disp_insns,
        {disp_start: "Game_DispatchSdlEvent"},
    )

    # --- markdown doc ---
    md_lines = [
        "# Game loop — static pseudocode (Capstone)",
        "",
        "Generated by `analyze_gamemain_functions.py` on `Game/Horsey.exe`.",
        "For Ghidra-quality decompilation, see [Ghidra_User_Tasks.md](Ghidra_User_Tasks.md).",
        "",
        "## Init body (`0xBE149`–`0xBEA7E`)",
        "",
        "```c",
        *init_payload["pseudocode_static"],
        "```",
        "",
        "### Calls (in address order)",
        "",
        "| At | Target |",
        "|----|--------|",
    ]
    for c in init_calls:
        md_lines.append(f"| `{c['at']}` | `{c['target']}` |")
    md_lines.extend(
        [
            "",
            "## `Game_DispatchSdlEvent` @ `0xC0430`",
            "",
            f"Estimated span: `{hex(disp_start)}`–`{hex(disp_end)}`",
            "",
            "### SDL event type comparisons found",
            "",
            "| RVA | Immediate | SDL name |",
            "|-----|-----------|----------|",
        ]
    )
    for s in disp_payload["sdl_type_matches"]:
        md_lines.append(f"| `{s['rva']}` | `{s.get('imm', '')}` | `{s.get('sdl_event', '?')}` |")
    md_lines.extend(["", "```c", *disp_payload["pseudocode_static"], "```"])
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "GameLoop_Static.md").write_text("\n".join(md_lines), encoding="utf-8")

    print("Wrote phase1_gamemain_init.json, phase1_sdl_event_dispatch.json")
    print(f"  Init calls: {len(init_calls)}")
    print(f"  SDL event matches: {len(disp_payload['sdl_type_matches'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
