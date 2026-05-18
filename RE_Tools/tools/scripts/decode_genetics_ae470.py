"""
Document genetics apply path after ReadNestedItem (Horsey.exe).

Verified Capstone:
  0x6EF80 ReadNestedItem -> 0x6D3B0 unpack @ +0x2B8
  0x6F100..0x6F118 sparse gene u32 -> +0xCC
  0xADB30 post-read -> 0xAE470 when [item+0x234] >= 0

Output: RE_Tools/analysis/save_genetics_runtime.json
        RE_Tools/analysis/disasm_genetics_ae470.txt
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_64, Cs

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
from paths import get_exe_path  # noqa: E402

IMAGE_BASE = 0x140000000
OUT_JSON = ROOT / "RE_Tools" / "analysis" / "save_genetics_runtime.json"
OUT_TXT = ROOT / "RE_Tools" / "analysis" / "disasm_genetics_ae470.txt"


def disasm_fn(pe, raw: bytes, rva: int, max_bytes: int = 0x400) -> list[str]:
    off = pe.get_offset_from_rva(rva)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    lines = []
    for i in md.disasm(raw[off : off + max_bytes], IMAGE_BASE + rva):
        a = i.address - IMAGE_BASE
        lines.append(f"  {a:06X}: {i.mnemonic:8} {i.op_str}")
        if i.mnemonic == "ret" and a > rva + 0x200:
            break
    return lines


def main() -> int:
    pe = pefile.PE(str(get_exe_path()))
    raw = get_exe_path().read_bytes()
    regions = [
        ("ReadNestedItem_gene_loop", 0x6F0F0, 0x80),
        ("PostRead_ADB30", 0xADB30, 0x100),
        ("GeneticsApply_AE470", 0xAE470, 0x250),
        ("GeneByteHelper_9FC40", 0x9FC40, 0x60),
    ]
    txt_lines = [f"Horsey.exe genetics path — {get_exe_path()}\n"]
    for name, rva, size in regions:
        txt_lines.append(f"=== {name} @ 0x{rva:X} ===")
        txt_lines.extend(disasm_fn(pe, raw, rva, size))
        txt_lines.append("")

    report = {
        "sources": {
            "unpack": "0x6D3B0 fills item+0x2B8 (240 B packed -> 480 B diploid gene indices)",
            "sparse_genes": "0x6EF80 @ 0x6F100: count then (slot_index, value) -> +0xCC..+0x118",
            "post_read": "0xADB30 if [item+0x234]>=0 calls 0xAE470",
        },
        "item_offsets": {
            "+0x2B8": "packed gene blob buffer (see inventory_pack_codec.py)",
            "+0xCC..+0x118": "20× int32 gene slot overrides (-1 = unused)",
            "+0x234": "signed threshold; negative skips AE470 random path",
            "+0x40..+0x48": "vector of horse component objects (stride 0xB8)",
        },
        "ae470_summary": {
            "entry": "0xAE470(rcx=item, rdx=scratch_0x2E0)",
            "gate": "0xADB30 calls AE470 only when [item+0x234] >= 0",
            "uses_table": "rip+0x1B6CEA — maps gene indices to byte offsets in scratch",
            "writes": "byte ptr [table_index + scratch] via 0x9FC40",
            "component_loop": "iterates [item+0x40] vector; requires [entry+8]==3",
            "note": "Scratch filled with RNG @ 0xC1900 in ADB30 path — runtime phenotype glue, not save file bytes",
        },
        "b8_implicit_eof": {
            "read_loop": "0x6D6F5",
            "eof": "ReadU32 @ 0x70540 returns 0",
            "default": "operator_new(0xC8) + ctor @ 0x7AE20 — in-memory slot without wire bytes",
            "manifest": "save_main_nested_b8_manifest.json",
        },
        "save_file_relation": (
            "On-disk gene pack @ inventory +0x51 decodes to g0..g3 indices per genes.xml. "
            "AE470 applies those to live horse parts when loading; not re-serialized into pack."
        ),
    }
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    OUT_TXT.write_text("\n".join(txt_lines), encoding="utf-8")
    print(f"Wrote {OUT_JSON} and {OUT_TXT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
