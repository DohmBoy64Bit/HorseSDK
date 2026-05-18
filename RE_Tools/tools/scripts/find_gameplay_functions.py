"""
Find Horsey.exe gameplay functions via string xrefs (race, shop, spawn, money).

Verified: string RVAs from Game/Horsey.exe; code xrefs filtered with Capstone
(LEA/MOV to RIP only — skips embedded string tables).

Output:
  RE_Tools/analysis/gameplay_functions.json
  RE_Tools/docs/GameplayFunctions.md

Usage:
  python RE_Tools/tools/scripts/find_gameplay_functions.py
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_64, Cs

ROOT = Path(__file__).resolve().parents[3]
EXE = ROOT / "Game" / "Horsey.exe"
OUT_JSON = ROOT / "RE_Tools" / "analysis" / "gameplay_functions.json"
OUT_MD = ROOT / "RE_Tools" / "docs" / "GameplayFunctions.md"
IMAGE_BASE = 0x140000000

# name -> {rva, category, role}
GAMEPLAY_STRINGS: dict[str, dict] = {
    "SimStartRace": {"rva": 0x25BB70, "category": "race", "role": "Start simulated race"},
    "SimHorseFinished": {"rva": 0x25BB90, "category": "race", "role": "Sim race horse finished"},
    "OnYourMark": {"rva": 0x263CF0, "category": "race", "role": "Race countdown phase"},
    "RaceGetSet": {"rva": 0x25B250, "category": "race", "role": "Race get-set phase"},
    "RaceGo": {"rva": 0x25B25C, "category": "race", "role": "Race go signal"},
    "CrossFinishLine": {"rva": 0x25B270, "category": "race", "role": "Cross finish line"},
    "WonRace": {"rva": 0x25B280, "category": "race", "role": "Race won"},
    "Racing": {"rva": 0x25B264, "category": "race", "role": "Racing UI state label"},
    "Betting": {"rva": 0x25B230, "category": "race", "role": "Betting UI mode"},
    "BetMore": {"rva": 0x2641C0, "category": "race", "role": "Increase bet"},
    "BetMax": {"rva": 0x2641B8, "category": "race", "role": "Max bet"},
    "SimSpawnDisk": {"rva": 0x25BD78, "category": "spawn", "role": "Spawn entity on world tile"},
    "ProcessHorse": {"rva": 0x265070, "category": "horse", "role": "Process / update horse instance"},
    "GrabHorse": {"rva": 0x266C90, "category": "horse", "role": "Grab / pick up horse"},
    "LerpHorse": {"rva": 0x262830, "category": "horse", "role": "Lerp horse position"},
    "DropHorseFail": {"rva": 0x266A50, "category": "horse", "role": "Drop horse failed"},
    "StatusFoal": {"rva": 0x25D760, "category": "breeding", "role": "Foal status"},
    "Studs": {"rva": 0x267E14, "category": "breeding", "role": "Studding service UI"},
    "BuyItem": {"rva": 0x25DA40, "category": "shop", "role": "Buy item from shop"},
    "GainMoney": {"rva": 0x26BA90, "category": "economy", "role": "Add money to player"},
    "LoseMoney": {"rva": 0x26BAA0, "category": "economy", "role": "Subtract money"},
    "HorseMart": {"rva": 0x262D00, "category": "shop", "role": "Horse mart"},
    "Shopkeep": {"rva": 0x2629A8, "category": "shop", "role": "Shopkeeper"},
}

# Hand-confirmed function entry RVAs (Capstone on Horsey.exe)
PINNED_FUNCTIONS: list[dict] = [
    {
        "name": "GainMoney",
        "rva": "0x10AB80",
        "category": "economy",
        "summary": "void GainMoney(ctx, amount, flag): [ctx+0x308]+=edx; refresh [ctx+0x30c]=0x3c",
        "struct_offsets": {"ctx+0x308": "money", "ctx+0x30c": "money_display_timer", "ctx+0x310": "last_delta"},
        "strings": ["GainMoney"],
        "callers": ["0x2FDAF", "0x3A10A", "0x605F4", "0x60B5D"],
        "status": "verified",
    },
    {
        "name": "SimSpawnDisk",
        "rva": "0x342F0",
        "category": "spawn",
        "summary": "Spawn path: alloc 0x20, copy 'SimSpawnDisk' tag, place via [rbx+0x148]",
        "strings": ["SimSpawnDisk"],
        "status": "partial",
    },
    {
        "name": "ProcessHorse",
        "rva": "0xA23F0",
        "category": "horse",
        "summary": "Horse tick / gene display; switch table refs 'ProcessHorse' @ 0xA24D8",
        "strings": ["ProcessHorse"],
        "status": "partial",
    },
    {
        "name": "BuyItem",
        "rva": "0x78B00",
        "category": "shop",
        "summary": "Shop buy dispatch; refs 'BuyItem' @ 0x78xxx, calls 0x21E450 helper",
        "strings": ["BuyItem"],
        "status": "partial",
    },
]


def text_section(pe, raw: bytes) -> tuple[bytes, int]:
    for sec in pe.sections:
        if sec.Name.startswith(b".text"):
            off = sec.PointerToRawData
            return raw[off : off + sec.SizeOfRawData], sec.VirtualAddress
    raise RuntimeError("no .text")


def code_xrefs(text: bytes, text_rva: int, target_rva: int, raw: bytes, pe) -> list[int]:
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    hits: list[int] = []
    for i in range(len(text) - 7):
        rva_here = text_rva + i
        for insn_len in range(4, 8):
            if i + insn_len > len(text):
                break
            va_next = IMAGE_BASE + rva_here + insn_len
            disp = struct.unpack_from("<i", text, i + insn_len - 4)[0]
            if (va_next + disp) - IMAGE_BASE != target_rva:
                continue
            off = pe.get_offset_from_rva(rva_here)
            insns = list(md.disasm(raw[off : off + 8], IMAGE_BASE + rva_here))
            if not insns:
                break
            m, op = insns[0].mnemonic, insns[0].op_str
            if m in ("lea", "mov", "movsd", "movups", "movdqa") and "rip" in op:
                hits.append(rva_here)
            break
    return hits


def function_start(pe, raw: bytes, xref: int, text_rva: int) -> int:
    off = pe.get_offset_from_rva(xref)
    text_off = pe.get_offset_from_rva(text_rva)
    scan = raw[max(text_off, off - 0x900) : off + 1]
    base_rva = pe.get_rva_from_offset(max(text_off, off - 0x900))
    best = xref
    for j in range(len(scan) - 1, -1, -1):
        rva_j = base_rva + j
        if rva_j >= xref:
            continue
        b = scan[j : j + 3]
        if scan[j] == 0xCC and j + 1 < len(scan) and scan[j + 1] != 0xCC:
            if xref - rva_j < 0xA00:
                return base_rva + j + 1
        if b[:2] in (b"\x40\x53", b"\x48\x89", b"\x55\x48") or b[:3] == b"\x48\x83":
            if xref - rva_j < 0xA00:
                return rva_j
    return best


def find_callers(pe, raw: bytes, fn_rva: int, limit: int = 12) -> list[str]:
    text, text_rva = text_section(pe, raw)
    out: list[str] = []
    for i in range(len(text) - 5):
        if text[i] != 0xE8:
            continue
        rel = struct.unpack_from("<i", text, i + 1)[0]
        dst = text_rva + i + 5 + rel
        if dst == fn_rva:
            out.append(hex(text_rva + i))
            if len(out) >= limit:
                break
    return out


def main() -> int:
    if not EXE.is_file():
        print(f"Missing {EXE}")
        return 1
    pe = pefile.PE(str(EXE))
    raw = EXE.read_bytes()
    text, text_rva = text_section(pe, raw)
    md = Cs(CS_ARCH_X86, CS_MODE_64)

    functions: dict[str, dict] = {}
    for pin in PINNED_FUNCTIONS:
        rva = int(pin["rva"], 16)
        ent = {
            **pin,
            "va": hex(IMAGE_BASE + rva),
            "verification": ["capstone", "string_xref"],
        }
        ent["callers"] = ent.get("callers") or find_callers(pe, raw, rva)
        functions[pin["name"]] = ent

    string_xrefs: list[dict] = []
    for sname, meta in GAMEPLAY_STRINGS.items():
        srva = meta["rva"]
        for xr in code_xrefs(text, text_rva, srva, raw, pe):
            fn_rva = function_start(pe, raw, xr, text_rva)
            off = pe.get_offset_from_rva(xr)
            insn = next(md.disasm(raw[off : off + 12], IMAGE_BASE + xr))
            line = f"{insn.mnemonic} {insn.op_str}"
            string_xrefs.append(
                {
                    "string": sname,
                    "string_rva": hex(srva),
                    "xref_rva": hex(xr),
                    "xref": line,
                    "function_rva": hex(fn_rva),
                }
            )
            key = hex(fn_rva)
            if key not in functions:
                functions[key] = {
                    "rva": key,
                    "va": hex(IMAGE_BASE + fn_rva),
                    "name_guess": sname,
                    "category": meta["category"],
                    "summary": meta["role"],
                    "strings": [sname],
                    "status": "partial",
                    "verification": ["string_xref", "capstone"],
                }
            elif sname not in functions[key]["strings"]:
                functions[key]["strings"].append(sname)
                if len(functions[key]["strings"]) > 1:
                    functions[key]["name_guess"] = functions[key]["strings"][0] + "_dispatch"

    # dedupe: prefer pinned names
    fn_list = []
    seen_rva: set[int] = set()
    for pin in PINNED_FUNCTIONS:
        fn_list.append(functions[pin["name"]])
        seen_rva.add(int(pin["rva"], 16))
    for ent in sorted(
        (v for k, v in functions.items() if not k.startswith("0x") or k not in {p["name"] for p in PINNED_FUNCTIONS}),
        key=lambda x: int(x["rva"], 16),
    ):
        rva = int(ent["rva"], 16)
        if rva in seen_rva:
            continue
        seen_rva.add(rva)
        fn_list.append(ent)

    by_cat: dict[str, int] = {}
    for f in fn_list:
        by_cat[f["category"]] = by_cat.get(f["category"], 0) + 1

    report = {
        "exe": str(EXE),
        "image_base": hex(IMAGE_BASE),
        "method": "Capstone-filtered RIP xrefs + pinned prologue scan",
        "repomix_crossref": "Horsey Game repomix documents same string names (Betting, SimStartRace, BuyItem, …)",
        "summary": {
            "strings_scanned": len(GAMEPLAY_STRINGS),
            "code_xrefs": len(string_xrefs),
            "functions": len(fn_list),
            "pinned_verified": sum(1 for f in fn_list if f.get("status") == "verified"),
            "by_category": by_cat,
        },
        "functions": fn_list,
        "string_xrefs": string_xrefs,
        "sdk_note": "Merge into game_function_catalog.json via build_game_function_catalog.py --gameplay",
    }
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Gameplay functions (race / shop / spawn / economy)",
        "",
        f"**Source:** `Game/Horsey.exe` string xrefs · **{len(fn_list)}** function entries",
        "",
        "Regenerate: `python RE_Tools/tools/scripts/find_gameplay_functions.py`",
        "",
        "## Pinned (hand-verified prologue)",
        "",
        "| RVA | Name | Category | Summary |",
        "|-----|------|----------|---------|",
    ]
    for pin in PINNED_FUNCTIONS:
        lines.append(
            f"| `{pin['rva']}` | **{pin['name']}** | {pin['category']} | {pin['summary'][:80]} |"
        )
    lines.extend(
        [
            "",
            "## By category (auto xref)",
            "",
        ]
    )
    cats: dict[str, list] = {}
    for f in fn_list:
        cats.setdefault(f["category"], []).append(f)
    pinned_names = {p["name"] for p in PINNED_FUNCTIONS}
    for cat in sorted(cats):
        lines.append(f"### {cat}")
        lines.append("")
        lines.append("| RVA | Name | Strings |")
        lines.append("|-----|------|---------|")
        for f in sorted(cats[cat], key=lambda x: int(x["rva"], 16))[:25]:
            nm = f.get("name") or f.get("name_guess", "?")
            if nm in pinned_names:
                continue
            lines.append(
                f"| `{f['rva']}` | `{nm}` | {', '.join(f.get('strings', [])[:3])} |"
            )
        if len(cats[cat]) > 25:
            lines.append(f"| … | +{len(cats[cat]) - 25} more | see `gameplay_functions.json` |")
        lines.append("")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_JSON} functions={len(fn_list)} code_xrefs={len(string_xrefs)}")
    print(f"Wrote {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
