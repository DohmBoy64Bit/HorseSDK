"""
Capstone + Frida prep: Game_SimStep @ 0xC12D0.

Outputs:
  RE_Tools/analysis/phase1_game_sim_step.json
  RE_Tools/analysis/disasm_game_sim_step.txt
  RE_Tools/docs/Game_SimStep.md
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "scripts"))

from re_pe_util import (  # noqa: E402
    IMAGE_BASE,
    disasm_range,
    load_pe,
    resolve_call,
    scan_e8_callers,
)

SIM_RVA = 0xC12D0
NAMES = {
    0xC12D0: "Game_SimStep",
    0xBE607: "GameMain_SimStep_Call",
    0xBE620: "GameMain_SimStep_Call2",
    0x87510: "Game_UpdateWorld",
    0x711B0: "SettingsLoader",
    0xBE0F0: "GameMain_InitAndLoop",
    0x3F360: "Lock_3F360",
    0x88510: "Game_WorldSimStep",
}

OUT_JSON = ROOT / "RE_Tools" / "analysis" / "phase1_game_sim_step.json"
OUT_TXT = ROOT / "RE_Tools" / "analysis" / "disasm_game_sim_step.txt"
OUT_MD = ROOT / "RE_Tools/docs/Game_SimStep.md"


def main() -> int:
    pe, raw = load_pe()
    insns = disasm_range(raw, pe, SIM_RVA, 0x6000)
    end = insns[-1][0] if insns else SIM_RVA
    calls = [
        {"at": hex(r), "target": resolve_call(o, NAMES)}
        for r, m, o in insns
        if m == "call"
    ]
    callers = scan_e8_callers(raw, pe, SIM_RVA)
    frame_callers = [c for c in callers if 0xBEA00 <= c <= 0xBEE00]
    payload = {
        "function": "Game_SimStep",
        "rva": hex(SIM_RVA),
        "end_rva": hex(end),
        "size": end - SIM_RVA,
        "callers_e8_count": len(callers),
        "callers_frame_loop": [hex(c) for c in frame_callers],
        "callers_all_sample": [hex(c) for c in callers[:30]],
        "callees": calls,
        "callee_counts": dict(Counter(c["target"] for c in calls).most_common(25)),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [f"# Game_SimStep @ 0x{SIM_RVA:X}", ""]
    for r, m, o in insns[:400]:
        ann = f"  ; -> {resolve_call(o, NAMES)}" if m == "call" else ""
        lines.append(f"0x{r:08X}: {m:8} {o}{ann}")
    if len(insns) > 400:
        lines.append(f"... ({len(insns) - 400} more insns)")
    OUT_TXT.write_text("\n".join(lines), encoding="utf-8")

    md = [
        "# `Game_SimStep` @ `0xC12D0`",
        "",
        "**Capstone** on `Game/Horsey.exe` — primary per-frame / UI sim driver.",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| **RVA** | `0x{SIM_RVA:X}` |",
        f"| **Size** | ~`0x{end - SIM_RVA:X}` bytes |",
        f"| **E8 callers** | {len(callers)} (frame loop: {len(frame_callers)}) |",
        "",
        f"**Artifacts:** `{OUT_JSON.relative_to(ROOT)}`, `{OUT_TXT.relative_to(ROOT)}`",
        "",
        "## Frame loop sites (`0xBEA00`–`0xBEE00`)",
        "",
    ]
    for c in frame_callers:
        md.append(f"- `{hex(c)}`")
    md.extend(["", "## Top callees", "", "| Callee | Count |", "|--------|-------|"])
    for t, n in payload["callee_counts"].items():
        md.append(f"| `{t}` | {n} |")
    md.extend(
        [
            "",
            "Contrast: [Game_WorldSimStep.md](Game_WorldSimStep.md) @ `0x88510` is resize-gated (0 Frida hits with stable window).",
            "",
            "Frida: `frida_game_sim_step.py`",
            "",
            "| Ghidra rename |",
            "|---------------|",
            "| `FUN_1400c12d0` → `Game_SimStep` |",
            "",
        ]
    )
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote {OUT_JSON} size=0x{end - SIM_RVA:X} callers={len(callers)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
