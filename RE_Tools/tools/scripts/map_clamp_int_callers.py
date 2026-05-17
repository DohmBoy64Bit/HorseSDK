"""
Capstone: document util @ 0xC12D0 (misnamed Game_SimStep).

Signature (first function in cluster):
  int clamp_int(int value /*ecx*/, int lo /*edx*/, int hi /*r8d*/);
  if (ecx < edx) return edx;
  if (ecx > r8d) return r8d;
  return ecx;

Outputs:
  RE_Tools/analysis/clamp_int_callers.json
  RE_Tools/docs/ClampInt3.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "scripts"))

from re_pe_util import disasm_range, load_pe, scan_e8_callers  # noqa: E402

CLAMP_RVA = 0xC12D0
FLOAT_MIN_RVA = 0xC12F0
NAMES = {
    0xC12D0: "ClampInt3",
    0xC12F0: "MinSS",
    0xC1310: "FloatLerpClamp",
    0xBE607: "Loop_ClampW320",
    0xBE620: "Loop_ClampH180",
    0xBEC53: "Loop_ClampPostSwapA",
    0xBEC79: "Loop_ClampPostSwapB",
    0x714A3: "Settings_Clamp200",
    0x714D2: "Settings_Clamp100",
    0x711B0: "SettingsLoader",
}


def decode_site(raw, pe, call_rva: int) -> dict:
    """Disasm ~12 insns before call for ecx/edx/r8 setup."""
    start = max(call_rva - 0x30, 0)
    insns = disasm_range(raw, pe, start, 0x40)
    window = [i for i in insns if call_rva - 0x30 <= i[0] <= call_rva + 2]
    lines = [f"{hex(r)}: {m} {o}" for r, m, o in window[-14:]]
    # Heuristic immediates
    imms = []
    for r, m, o in window:
        if m == "mov" and ", 0x" in o:
            imms.append(o)
    return {
        "call_rva": hex(call_rva),
        "label": NAMES.get(call_rva, ""),
        "disasm_tail": lines,
        "mov_immediates": imms[-4:],
    }


def main() -> int:
    pe, raw = load_pe()
    insns = disasm_range(raw, pe, CLAMP_RVA, 0x80)
    callers = scan_e8_callers(raw, pe, CLAMP_RVA)
    sites = [decode_site(raw, pe, c) for c in sorted(callers)]

    # Known semantics from Capstone @ loop
    known = [
        {
            "site": "0xBE607",
            "ecx": "r10d (computed width)",
            "edx": "0x140 (320)",
            "r8d": "r12d (max width cap)",
            "stores": "dword @ rip+0x232EB8",
        },
        {
            "site": "0xBE620",
            "ecx": "global dword",
            "edx": "0xB4 (180)",
            "r8d": "r15d (max height cap)",
            "stores": "dword @ rip+0x232EA0",
        },
        {
            "site": "0x714A3",
            "ecx": "settings dword",
            "edx": "0",
            "r8d": "0xC8 (200)",
            "context": "SettingsLoader init — caps UI dimension",
        },
        {
            "site": "0x714D2",
            "ecx": "settings dword",
            "edx": "0",
            "r8d": "0x64 (100)",
            "context": "SettingsLoader init",
        },
    ]

    payload = {
        "correction": "0xC12D0 is NOT a sim step; rename to ClampInt3",
        "signature": "int ClampInt3(int val, int lo, int hi)",
        "cluster_rvas": {
            "ClampInt3": "0xC12D0",
            "MinSS": "0xC12F0",
            "FloatLerpClamp": "0xC1310",
        },
        "entry_disasm": [f"{hex(r)}: {m} {o}" for r, m, o in insns[:12]],
        "caller_count": len(callers),
        "known_sites": known,
        "all_sites": sites,
    }
    out = ROOT / "RE_Tools" / "analysis" / "clamp_int_callers.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md = [
        "# `ClampInt3` @ `0xC12D0` (was mislabeled `Game_SimStep`)",
        "",
        "**Verified on `Game/Horsey.exe`** — Capstone `map_clamp_int_callers.py`.",
        "",
        f"**Artifact:** `{out.relative_to(ROOT)}`",
        "",
        "## Signature",
        "",
        "```c",
        "// Horsey.exe+0xC12D0",
        "int ClampInt3(int value /*ecx*/, int lo /*edx*/, int hi /*r8d*/) {",
        "    if (value < lo) return lo;",
        "    if (value > hi) return hi;",
        "    return value;",
        "}",
        "```",
        "",
        "Same RVA region also holds small **SSE helpers** (`MinSS` @ `0xC12F0`, float lerp @ `0xC1310`).",
        "",
        "## Why Frida showed `rcx=0x64` / `0x500`",
        "",
        "Hooks logged **`rcx` only**. At `SettingsLoader` (`0x714A3` / `0x714D2`) the **third** argument is the cap:",
        "",
        "| Call site | `edx` (lo) | `r8d` (hi) | Meaning |",
        "|-----------|------------|------------|---------|",
        "| `0x714A3` | `0` | **`0xC8` (200)** | cap setting to 200 |",
        "| `0x714D2` | `0` | **`0x64` (100)** | cap setting to 100 |",
        "",
        "Frame loop @ `0xBE607` / `0xBE620`:",
        "",
        "| Site | `edx` | `r8d` |",
        "|------|-------|-------|",
        "| `0xBE607` | **`0x140` (320)** | `r12d` |",
        "| `0xBE620` | **`0xB4` (180)** | `r15d` |",
        "",
        "These match half-resolution UI bounds (320×180 vs 960×540 reference).",
        "",
        "## Post-swap loop",
        "",
        "`0xBEC53` / `0xBEC79` clamp scroll/offset globals before `call 0x125E70` (render helper).",
        "",
        "Rename in Ghidra: `FUN_1400c12d0` → **`ClampInt3`**. Do not hook as per-frame sim.",
        "",
    ]
    doc = ROOT / "RE_Tools" / "docs" / "ClampInt3.md"
    doc.write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote {out} callers={len(callers)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
