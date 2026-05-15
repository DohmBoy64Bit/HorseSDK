"""
Find code RVAs that reference data strings (Capstone RIP-relative operands).

Output: RE_Tools/analysis/phase1_string_xrefs.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_64, Cs
from capstone.x86 import X86_OP_MEM, X86_REG_RIP

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
from paths import get_exe_path  # noqa: E402

OUT = ROOT / "RE_Tools" / "analysis" / "phase1_string_xrefs.json"
IMAGE_BASE = 0x140000000

NEEDLES = [
    b"settings.xml",
    b"horsey.tmx",
    b"genes.dat",
    b"genes.xml",
    b"quip.crf",
    b".crf",
    b"n64.fnt",
    b"n64_0.png",
    b"c64_0.png",
    b"save1.dat",
    b"save",
    b"Save",
    b"data\\",
    b"got cheevo: %s",
]


def string_rvas(pe: pefile.PE, needle: bytes) -> list[int]:
    data = pe.get_memory_mapped_image()
    out: list[int] = []
    start = 0
    while True:
        idx = data.find(needle, start)
        if idx < 0:
            break
        out.append(pe.get_rva_from_offset(idx))
        start = idx + 1
    return out


def build_target_set(pe: pefile.PE, needles: list[bytes]) -> dict[int, str]:
    targets: dict[int, str] = {}
    for needle in needles:
        for rva in string_rvas(pe, needle):
            targets[rva] = needle.decode("ascii", errors="replace")
    return targets


def scan_text_xrefs(pe: pefile.PE, targets: dict[int, str]) -> dict[int, list[int]]:
    """string_rva -> list of instruction RVAs."""
    xrefs: dict[int, list[int]] = {r: [] for r in targets}
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    for section in pe.sections:
        if not section.Name.startswith(b".text"):
            continue
        code = section.get_data()
        base_rva = section.VirtualAddress
        for insn in md.disasm(code, IMAGE_BASE + base_rva):
            insn_rva = insn.address - IMAGE_BASE
            for op in insn.operands:
                if op.type != X86_OP_MEM:
                    continue
                if op.mem.base != X86_REG_RIP:
                    continue
                ref_rva = (insn.address + insn.size + op.mem.disp) - IMAGE_BASE
                if ref_rva in xrefs:
                    xrefs[ref_rva].append(insn_rva)
    return xrefs


def main() -> int:
    pe = pefile.PE(str(get_exe_path()))
    targets = build_target_set(pe, NEEDLES)
    xref_map = scan_text_xrefs(pe, targets)

    by_string: dict[str, dict] = {}
    for rva, label in sorted(targets.items()):
        sites = xref_map.get(rva, [])
        if label not in by_string:
            by_string[label] = {"string_rvas": [], "code_xrefs": []}
        by_string[label]["string_rvas"].append(hex(rva))
        if sites:
            by_string[label]["code_xrefs"].append(
                {"string_rva": hex(rva), "insn_rvas": [hex(s) for s in sites[:30]]}
            )

    entries = [
        {
            "string": k,
            "string_rvas": v["string_rvas"],
            "in_exe": bool(v["string_rvas"]),
            "code_xrefs": v["code_xrefs"],
        }
        for k, v in sorted(by_string.items())
    ]

    report = {
        "image_base": hex(IMAGE_BASE),
        "method": "Capstone RIP-relative memory operands in .text",
        "entries": entries,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    for e in entries:
        if e["code_xrefs"]:
            print(f"  XREF {e['string']!r}: {len(e['code_xrefs'])} hit(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
