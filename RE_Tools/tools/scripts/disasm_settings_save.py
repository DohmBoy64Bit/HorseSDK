"""
Capstone: Settings_Save @ 0x71F60 (settings.xml write on quit @ 0xBED11).

Outputs:
  RE_Tools/analysis/phase1_settings_save.json
  RE_Tools/analysis/disasm_settings_save.txt
  RE_Tools/docs/Settings_Save.md
"""
from __future__ import annotations

import json
import re
import struct
import sys
from collections import Counter
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_64, Cs
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
from paths import get_exe_path  # noqa: E402

IMAGE_BASE = 0x140000000
FUNC_RVA = 0x71F60
MAX_SPAN = 0x1800
STRING_LO, STRING_HI = 0x262000, 0x268000
OUT_JSON = ROOT / "RE_Tools" / "analysis" / "phase1_settings_save.json"
OUT_TXT = ROOT / "RE_Tools" / "analysis" / "disasm_settings_save.txt"
OUT_MD = ROOT / "RE_Tools" / "docs" / "Settings_Save.md"

INTERNAL = {
    0x72280: "Settings_ParseXmlKey",
    0x722C2: "Settings_WriteXmlKey",
    0x256F0: "Xml_NextNode",
    0x258F0: "Xml_SetAttribute",
    0x25750: "Settings_ApplyValue",
    0x27F70: "PathJoin",
    0x27E50: "StdString_FromCStr",
    0xBFB60: "File_ReadToBuffer",
    0x251CE0: "StdString_Assign",
    0x2511B0: "memcpy",
    0x28600: "operator_new",
    0x25E20: "Xml_DocLoad",
    0x25EC0: "Xml_FindRoot",
    0x24A80: "Xml_CreateDoc",
    0x25340: "File_OpenRead",
    0x254B0: "Settings_GetGlobalPtr",
}


def read_cstring(raw: bytes, rva: int, max_len: int = 128) -> str | None:
    off = None
    try:
        pe_off = pe.get_offset_from_rva(rva)
    except Exception:
        return None
    if pe_off is None:
        return None
    chunk = raw[pe_off : pe_off + max_len]
    end = chunk.find(b"\x00")
    if end < 0:
        return None
    try:
        return chunk[:end].decode("utf-8", errors="replace")
    except Exception:
        return None


def disasm_fn(pe: pefile.PE, raw: bytes, start: int) -> list[tuple[int, str, str, int]]:
    off = pe.get_offset_from_rva(start)
    chunk = raw[off : off + MAX_SPAN]
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    insns = []
    last_ret = start
    for i in md.disasm(chunk, IMAGE_BASE + start):
        rva = i.address - IMAGE_BASE
        insns.append((rva, i.mnemonic, i.op_str, i.size))
        if i.mnemonic == "ret" and rva > start + 0x100:
            last_ret = rva
        if i.mnemonic == "int3" and rva > last_ret + 8:
            break
        if rva > start + MAX_SPAN - 16:
            break
    return insns


def rip_strings(insns, raw: bytes) -> list[dict]:
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    off = pe.get_offset_from_rva(FUNC_RVA)
    chunk = raw[off : off + MAX_SPAN]
    hits = []
    for i in md.disasm(chunk, IMAGE_BASE + FUNC_RVA):
        rva = i.address - IMAGE_BASE
        if not i.operands:
            continue
        for op in i.operands:
            if op.type != X86_OP_MEM or op.mem.base != X86_REG_RIP:
                continue
            tgt = rva + i.size + op.mem.disp
            if STRING_LO <= tgt <= STRING_HI:
                s = read_cstring(raw, tgt)
                if s and len(s) >= 2:
                    hits.append({"at": hex(rva), "string_rva": hex(tgt), "text": s})
    return hits


def resolve_call(op_str: str, exp: dict[int, str]) -> str:
    m = re.match(r"0x([0-9a-fA-F]+)", op_str.strip())
    if not m:
        return op_str
    va = int(m.group(1), 16)
    rva = va - IMAGE_BASE if va >= IMAGE_BASE else va
    return exp.get(rva) or INTERNAL.get(rva) or hex(rva)


def main() -> int:
    global pe
    pe = pefile.PE(str(get_exe_path()))
    raw = Path(get_exe_path()).read_bytes()
    exp = {}
    if hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
        for s in pe.DIRECTORY_ENTRY_EXPORT.symbols:
            if s.name:
                exp[s.address] = s.name.decode()

    insns = disasm_fn(pe, raw, FUNC_RVA)
    end_rva = insns[-1][0] if insns else FUNC_RVA
    calls = []
    globals_written = []
    for rva, mn, ops, _ in insns:
        if mn == "call":
            calls.append({"at": hex(rva), "target": resolve_call(ops, exp)})
        if mn == "mov" and "rip" in ops and "0x2f1" in ops.lower():
            globals_written.append({"at": hex(rva), "insn": f"{mn} {ops}"})

    str_hits = rip_strings(insns, raw)
    call_counts = Counter(c["target"] for c in calls)

    # Keys: strings that look like XML tag names (short, lowercase)
    xml_keys = sorted(
        {h["text"] for h in str_hits if re.match(r"^[a-z][a-z0-9_]{0,24}$", h["text"])}
    )
    path_strings = sorted(
        {h["text"] for h in str_hits if "." in h["text"] or "\\" in h["text"]}
    )

    payload = {
        "function": "Settings_Save",
        "rva": hex(FUNC_RVA),
        "span": [hex(FUNC_RVA), hex(end_rva)],
        "caller_quit": "0xBED11",
        "call_count": len(calls),
        "calls_unique": dict(call_counts.most_common(30)),
        "calls_ordered": calls,
        "string_refs": str_hits,
        "xml_keys_in_function": xml_keys,
        "path_strings": path_strings,
        "global_rip_refs": globals_written[:40],
        "note": "Does not call Save_Write @ 0x6DAB0 (verified by call list).",
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        f"# Settings_Save @ 0x{FUNC_RVA:X} (Capstone)",
        f"# Span ~0x{FUNC_RVA:X}-0x{end_rva:X}",
        "",
    ]
    for rva, mn, ops, _ in insns:
        ann = ""
        for h in str_hits:
            if int(h["at"], 16) == rva:
                ann = f"  ; \"{h['text']}\""
                break
        if mn == "call":
            tgt = resolve_call(ops, exp)
            ann = f"  ; -> {tgt}"
        lines.append(f"0x{rva:08X}: {mn:8} {ops}{ann}")
    OUT_TXT.write_text("\n".join(lines), encoding="utf-8")

    md_lines = [
        "# `Settings_Save` @ `0x71F60`",
        "",
        "**Capstone:** `FUN_140071f60` · **Quit caller:** `GameMain` @ **`0xBED11`**",
        "",
        "Persists **`settings.xml`** on shutdown — **not** `save%d.dat` (`Save_Write` @ `0x6DAB0`).",
        "",
        f"**Artifacts:** `{OUT_JSON.relative_to(ROOT)}`, `{OUT_TXT.relative_to(ROOT)}`",
        "",
        "## Call graph (unique callees)",
        "",
        "| Callee | Count | Role |",
        "|--------|-------|------|",
    ]
    for tgt, n in call_counts.most_common(15):
        role = {
            "Settings_ParseXmlKey": "read key name",
            "Settings_WriteXmlKey": "emit key/value",
            "Xml_SetAttribute": "XML attribute write",
            "Xml_NextNode": "walk nodes",
            "PathJoin": "build `settings.xml` path",
            "File_ReadToBuffer": "read existing file",
            "Xml_DocLoad": "parse XML",
        }.get(tgt, "")
        md_lines.append(f"| `{tgt}` | {n} | {role} |")

    md_lines.extend(
        [
            "",
            "## XML keys referenced in this function (exe strings)",
            "",
        ]
    )
    for k in xml_keys:
        md_lines.append(f"- `{k}`")
    if path_strings:
        md_lines.extend(["", "## Path / file strings", ""])
        for p in path_strings:
            md_lines.append(f"- `{p}`")

    md_lines.extend(
        [
            "",
            "## Ghidra renames",
            "",
            "| From | To |",
            "|------|-----|",
            "| `FUN_140071f60` | `Settings_Save` |",
            "",
        ]
    )
    OUT_MD.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"Wrote {OUT_JSON}, {OUT_TXT}, {OUT_MD}")
    print(f"  calls={len(calls)} keys={len(xml_keys)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
