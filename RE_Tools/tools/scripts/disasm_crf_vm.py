"""
Capstone: CRF loader cluster @ 0xBF200 and callees (0x6F3C0 file write path).

Outputs:
  RE_Tools/analysis/phase1_crf_vm.json
  RE_Tools/docs/CrfLoaderVm.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "scripts"))

from re_pe_util import disasm_range, load_pe, resolve_call, scan_e8_callers  # noqa: E402

REGIONS = [
    (0xBF200, "FontPath_Cluster_A"),
    (0xBF500, "FontPath_Cluster_B"),
    (0xBF8C0, "FontPath_Cluster_C"),
    (0x6F3C0, "FileWrite_6F3C0"),
    (0x6FD40, "StreamOpen_6FD40"),
]

NAMES = {
    0xBF200: "FontPath_Cluster_A",
    0xBF500: "FontPath_Cluster_B",
    0xBF8C0: "FontPath_Cluster_C",
    0x6F3C0: "FileWrite_6F3C0",
    0x6FD40: "StreamOpen_6FD40",
    0x6FE10: "WriteU32",
    0x88000: "BuildSavePath",
    0x27F70: "PathJoin",
}


def analyze_region(raw, pe, rva: int, label: str) -> dict:
    insns = disasm_range(raw, pe, rva, 0x600)
    calls = [
        {"at": hex(r), "target": resolve_call(o, NAMES)}
        for r, m, o in insns
        if m == "call"
    ]
    return {
        "label": label,
        "rva": hex(rva),
        "insn_count": len(insns),
        "calls": calls[:40],
        "callers": [hex(c) for c in scan_e8_callers(raw, pe, rva)[:15]],
    }


def main() -> int:
    pe, raw = load_pe()
    regions = [analyze_region(raw, pe, rva, label) for rva, label in REGIONS]
    f3c0_callers = scan_e8_callers(raw, pe, 0x6F3C0)

    payload = {
        "hypothesis": "0xBF2xx builds paths to .crf/.fnt; 0x6F3C0 serializes buffer (also save%d.dat)",
        "file_append_6F3C0_callers": [hex(c) for c in f3c0_callers[:25]],
        "regions": regions,
        "opcode_semantics": "RE_Tools/docs/CrfOpcodeSemantics.md",
    }
    out = ROOT / "RE_Tools" / "analysis" / "phase1_crf_vm.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md = [
        "# CRF loader / file-write cluster",
        "",
        "**Capstone** on `Game/Horsey.exe` — complements [CrfOpcodeSemantics.md](CrfOpcodeSemantics.md).",
        "",
        f"**Artifact:** `{out.relative_to(ROOT)}`",
        "",
        "## Regions",
        "",
    ]
    for r in regions:
        md.append(f"### `{r['label']}` @ `{r['rva']}`")
        md.append(f"- Callers: {', '.join(r['callers'][:5]) or 'none'}")
        for c in r["calls"][:8]:
            md.append(f"- `{c['at']}` → `{c['target']}`")
        md.append("")
    md.append("## `0x6F3C0` callers (sample)")
    for c in f3c0_callers[:12]:
        md.append(f"- `{hex(c)}`")
    doc = ROOT / "RE_Tools" / "docs" / "CrfLoaderVm.md"
    doc.write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
