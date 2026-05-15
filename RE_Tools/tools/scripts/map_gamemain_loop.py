"""
Map GameMain @ 0xBE0F0: regions, SDL exports, frame-loop globals, call graph.

Outputs:
  RE_Tools/analysis/phase1_gamemain_loop_map.json
  RE_Tools/analysis/disasm_gamemain_loop.txt

Verified against Game/Horsey.exe (image base 0x140000000).
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_64, Cs
from capstone.x86 import X86_OP_MEM, X86_REG_RIP

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
from paths import get_exe_path  # noqa: E402

IMAGE_BASE = 0x140000000
OUT_JSON = ROOT / "RE_Tools" / "analysis" / "phase1_gamemain_loop_map.json"
OUT_TXT = ROOT / "RE_Tools" / "analysis" / "disasm_gamemain_loop.txt"

# Frida-confirmed hook sites
HOOK_SITES = {
    "GameMain_InitAndLoop": 0xBE0F0,
    "Loop_SteamRunCallbacks": 0xBEA7F,
    "Loop_PollEvent_First": 0xBEA8A,
    "Loop_PollEvent_Drain": 0xBEAA5,
    "Loop_EventDispatch": 0xBEA9B,
    "Loop_GL_SwapWindow": 0xBEAF0,
    "Loop_FrameTick": 0xBECE7,
    "Loop_QuitCheck": 0xBEAE7,
    "Loop_AutoSaveGate": 0xBEAD9,
    "Loop_QuitSave": 0xBED11,
    "Loop_HelperCall": 0xBEDB4,
    "SettingsLoader_Call": 0xBE562,
}

REGIONS = [
    {"name": "init_prologue", "start": "0xBE0F0", "end": "0xBE149", "role": "Steam restart + SDL_Init early exits"},
    {"name": "init_body", "start": "0xBE149", "end": "0xBEA7F", "role": "Steam/SDL setup, settings @ 0xBE562, world bootstrap"},
    {"name": "frame_loop", "start": "0xBEA7F", "end": "0xBED82", "role": "Blocking per-frame loop until quit (body from 0xBEA85)"},
]

# Known internal callees (RVA) — name when export map misses
INTERNAL_CALLEES = {
    0x0C0430: "Game_DispatchSdlEvent",
    0x087510: "Game_UpdateWorld",
    0x071F60: "Save_Write",
    0x0BFFA0: "Game_PostSwapHook",
    0x0C12D0: "Game_SimStep",
    0x0C3A70: "Game_FrameFinalize",
    0x0BEEA0: "Loop_Helper_BEEA0",
    0x0711B0: "SettingsLoader",
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
    out: list[Insn] = []
    for i in md.disasm(raw[off : off + size], IMAGE_BASE + rva):
        out.append(Insn(i.address - IMAGE_BASE, i.mnemonic, i.op_str, i.size))
    return out


def rip_target(insn_rva: int, insn_size: int, disp: int) -> int:
    return insn_rva + insn_size + disp


def build_export_map(pe: pefile.PE) -> dict[int, str]:
    m: dict[int, str] = {}
    if not hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
        return m
    for sym in pe.DIRECTORY_ENTRY_EXPORT.symbols:
        if sym.name:
            m[sym.address] = sym.name.decode()
    return m


def resolve_call_target(op_str: str, exports: dict[int, str]) -> dict:
    s = op_str.strip()
    if s.startswith("0x"):
        try:
            va = int(s, 16)
            rva = va - IMAGE_BASE if va >= IMAGE_BASE else va
            name = exports.get(rva) or INTERNAL_CALLEES.get(rva)
            return {"rva": hex(rva), "name": name, "raw": op_str}
        except ValueError:
            pass
    if "rip" in s and "0x19c16b" in s:
        return {"rva": None, "name": "SteamAPI_RunCallbacks", "raw": op_str}
    return {"rva": None, "name": None, "raw": op_str}


def read_cstr(pe: pefile.PE, raw: bytes, rva: int) -> str | None:
    off = pe.get_offset_from_rva(rva)
    if off is None:
        return None
    end = raw.find(b"\x00", off)
    if end < 0:
        return None
    return raw[off:end].decode("utf-8", errors="replace")[:120]


def scan_frame_globals(pe: pefile.PE, raw: bytes, insns: list[Insn]) -> list[dict]:
    """RIP-relative globals touched in frame_loop with suggested role."""
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    off = pe.get_offset_from_rva(0xBEA80)
    chunk = raw[off : off + 0x350]
    hits: dict[int, dict] = {}
    for i in md.disasm(chunk, IMAGE_BASE + 0xBEA80):
        rva = i.address - IMAGE_BASE
        for op in i.operands:
            if op.type != X86_OP_MEM or op.mem.base != X86_REG_RIP:
                continue
            ref = rip_target(rva, i.size, op.mem.disp)
            if ref in hits:
                continue
            role = None
            if rva == 0xBEAE1:
                role = "quit_requested (je -> frame tick skips swap path)"
            elif rva in (0xBEABE, 0xBEABC):
                role = "frame flags (pause / mode)"
            hits[ref] = {
                "global_rva": hex(ref),
                "first_use": hex(rva),
                "insn": f"{i.mnemonic} {i.op_str}",
                "role": role,
                "near_string": read_cstr(pe, raw, ref) if 0x260000 <= ref <= 0x270000 else None,
            }
    quit_rva = rip_target(0xBEAE1, 7, 0x232A03)
    hits[quit_rva] = {
        "global_rva": hex(quit_rva),
        "first_use": "0xBEAE1",
        "insn": "cmp byte ptr [rip + 0x232a03], bl",
        "role": "g_quit_requested: je @ 0xBEAE7 -> 0xBECE7 skips SDL_GL_SwapWindow path",
        "near_string": read_cstr(pe, raw, quit_rva) if 0x260000 <= quit_rva <= 0x270000 else None,
    }
    return sorted(hits.values(), key=lambda x: x["first_use"])


def frame_pseudocode(calls: list[dict]) -> list[str]:
    return [
        "while (!g_quit_requested) {",
        "  SteamAPI_RunCallbacks();          // 0xBEA7F",
        "  if (SDL_PollEvent(&ev)) {          // 0xBEA8A",
        "    do { Game_DispatchSdlEvent();   // 0xBEA9B -> 0xC0430",
        "    } while (SDL_PollEvent(&ev));   // 0xBEAA5 drain",
        "  }",
        "  // flag gates @ 0xBEAAE-0xBEADF",
        "  if (!paused) Game_UpdateWorld();  // 0xBEAD4 -> 0x87510",
        "  if (g_quit_requested) break;      // 0xBEAE7 -> 0xBECE7",
        "  SDL_GL_SwapWindow(window);        // 0xBEAF0",
        "  Game_PostSwapHook();              // 0xBEB00 -> 0xBFFA0",
        "  // input / resize / SDL state @ 0xBEB05-0xBEB9E",
        "  // sim + render helpers 0xBEBEE-0xBECC4",
        "  Loop_FrameTick();                 // 0xBECE7 -> SDL_GetTicks delta, maybe SDL_Delay",
        "}",
        "Save_Write(ctx, mode);              // 0xBED11 on quit path",
    ]


def main() -> int:
    pe = pefile.PE(str(get_exe_path()))
    raw = Path(get_exe_path()).read_bytes()
    exports = build_export_map(pe)

    insns = disasm(pe, raw, 0xBE0F0, 0xD00)
    frame_insns = [i for i in insns if 0xBEA80 <= i.rva <= 0xBED82]

    calls: list[dict] = []
    for ins in frame_insns:
        if ins.mnemonic != "call":
            continue
        tgt = resolve_call_target(ins.op_str, exports)
        calls.append({"from": hex(ins.rva), **tgt})

    # Init-phase calls (sample)
    init_calls = []
    for ins in insns:
        if ins.rva >= 0xBEA80:
            break
        if ins.mnemonic != "call":
            continue
        tgt = resolve_call_target(ins.op_str, exports)
        init_calls.append({"from": hex(ins.rva), **tgt})
        if len(init_calls) >= 40:
            break

    globals_frame = scan_frame_globals(pe, raw, frame_insns)

    # Disasm text: init tail + full frame + quit epilogue
    lines = [f"# GameMain disasm — {get_exe_path()}", f"# Image base {hex(IMAGE_BASE)}\n"]
    for title, start, size in [
        ("init_settings_call", 0xBE558, 0x30),
        ("frame_loop", 0xBEA7F, 0x310),
        ("quit_epilogue", 0xBED00, 0x90),
    ]:
        lines.append(f"\n## {title} @ 0x{start:X}\n")
        for ins in disasm(pe, raw, start, size):
            tag = ""
            for name, rva in HOOK_SITES.items():
                if ins.rva == rva:
                    tag = f"  ; {name}"
            lines.append(f"0x{ins.rva:08X}: {ins.mnemonic:8} {ins.op_str}{tag}")

    payload = {
        "function": "GameMain_InitAndLoop",
        "function_rva": "0xBE0F0",
        "span_rva": ["0xBE0F0", "0xBED82"],
        "caller": {"rva": "0x21EE0D", "name": "CRT_main_trampoline"},
        "regions": REGIONS,
        "hook_sites": {k: hex(v) for k, v in HOOK_SITES.items()},
        "frame_loop_pseudocode": frame_pseudocode(calls),
        "frame_calls_resolved": calls,
        "init_calls_sample": init_calls,
        "frame_globals": globals_frame[:25],
        "quit_path": {
            "flag_cmp": "0xBEAE1",
            "skip_render_je": "0xBEAE7 -> 0xBECE7",
            "save_on_quit": "0xBED11 -> Save_Write @ 0x6DAB0",
            "autosave_in_loop": "0xBEAD9 (backtrace from Frida auto-save)",
        },
        "debunked": {
            "RenderFrame_11E0F0": "0 Frida hits; tail thunk only — do not hook",
        },
        "artifacts": {
            "frida": "RE_Tools/analysis/frida_gameloop.json",
            "capstone_summary": "RE_Tools/analysis/phase1_gamemain_loop.json",
        },
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    OUT_TXT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_JSON.name} + {OUT_TXT.name}")
    print(f"  Frame calls: {len(calls)}")
    print(f"  Quit global: {[g for g in globals_frame if g.get('role') and 'quit' in g['role'].lower()][:1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
