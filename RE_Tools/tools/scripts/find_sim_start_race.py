"""
Find SimStartRace implementation via E8 (call rel32) into sim dispatch regions.

String xrefs @ 0x32FA3 / 0x5F372 only load the tag into xmm — not the race start body.
This script lists callers that jump into:
  - 0x033000 .. 0x035000  (spawn / early sim cluster, contains SimSpawnDisk @ 0x33A20)
  - 0x05F000 .. 0x061000  (mid sim dispatch)

Also resolves function entry for string-xref sites and E8 targets.

Usage:
  python RE_Tools/tools/scripts/find_sim_start_race.py

Output:
  RE_Tools/analysis/sim_start_race_callees.json
  RE_Tools/docs/SimStartRace.md
"""
from __future__ import annotations

import json
import struct
from collections import defaultdict
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_64, Cs

ROOT = Path(__file__).resolve().parents[3]
EXE = ROOT / "Game" / "Horsey.exe"
OUT_JSON = ROOT / "RE_Tools" / "analysis" / "sim_start_race_callees.json"
OUT_MD = ROOT / "RE_Tools" / "docs" / "SimStartRace.md"
IMAGE_BASE = 0x140000000

REGIONS = [
    ("sim_spawn_dispatch", 0x33000, 0x35000),
    ("sim_mid_dispatch", 0x5F000, 0x61000),
]

STRING_XREFS = [
    ("SimStartRace", 0x32FA3),
    ("SimStartRace", 0x5F372),
    ("SimSpawnDisk", 0x342F0),
]

PINNED_ENTRIES = {
    "GainMoney": 0x10AB80,
    "SimSpawnDisk": 0x33A20,
    "RaceStateMachine": 0x8F2B0,
}


def text_blob(pe, raw: bytes) -> tuple[bytes, int]:
    for sec in pe.sections:
        if sec.Name.startswith(b".text"):
            off = sec.PointerToRawData
            return raw[off : off + sec.SizeOfRawData], sec.VirtualAddress
    raise RuntimeError("no .text")


def in_region(rva: int) -> str | None:
    for name, lo, hi in REGIONS:
        if lo <= rva < hi:
            return name
    return None


def find_function_entry(text: bytes, text_rva: int, site_rva: int, max_back: int = 0x2000) -> int | None:
    """Walk backward for common x64 prologue (push rbp / sub rsp)."""
    off = site_rva - text_rva
    if off < 0 or off >= len(text):
        return None
    start = max(0, off - max_back)
    chunk = text[start:off]
    # prefer: 40 55 (push rbp) or 48 89 5c 24 / 48 83 ec
    candidates: list[int] = []
    for i in range(len(chunk) - 3, -1, -1):
        b0, b1 = chunk[i], chunk[i + 1] if i + 1 < len(chunk) else 0
        if b0 == 0x40 and b1 == 0x55:
            candidates.append(text_rva + start + i)
        elif b0 == 0x48 and b1 == 0x89 and i + 3 < len(chunk) and chunk[i + 2] == 0x5C:
            candidates.append(text_rva + start + i)
        elif b0 == 0x48 and b1 == 0x83 and i + 2 < len(chunk) and chunk[i + 2] == 0xEC:
            candidates.append(text_rva + start + i)
    return candidates[-1] if candidates else None


def scan_e8_calls(text: bytes, text_rva: int) -> list[dict]:
    hits: list[dict] = []
    i = 0
    while i + 5 <= len(text):
        if text[i] == 0xE8:
            rel = struct.unpack_from("<i", text, i + 1)[0]
            call_rva = text_rva + i
            tgt = call_rva + 5 + rel
            reg = in_region(tgt)
            if reg:
                hits.append(
                    {
                        "call_rva": hex(call_rva),
                        "target_rva": hex(tgt),
                        "region": reg,
                        "caller_entry_guess": hex(find_function_entry(text, text_rva, call_rva) or 0),
                    }
                )
        i += 1
    return hits


def scan_capstone_calls(text: bytes, text_rva: int) -> list[dict]:
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    hits: list[dict] = []
    for ins in md.disasm(text, IMAGE_BASE + text_rva):
        if ins.mnemonic != "call":
            continue
        tgt: int | None = None
        if ins.bytes and ins.bytes[0] == 0xE8 and len(ins.bytes) >= 5:
            rel = struct.unpack_from("<i", ins.bytes, 1)[0]
            tgt = ins.address - IMAGE_BASE + 5 + rel
        elif ins.op_str.startswith("0x"):
            try:
                tgt = int(ins.op_str.split()[0], 16) - IMAGE_BASE
            except ValueError:
                tgt = None
        if tgt is None:
            continue
        reg = in_region(tgt)
        if reg:
            hits.append(
                {
                    "call_rva": hex(ins.address - IMAGE_BASE),
                    "target_rva": hex(tgt),
                    "region": reg,
                    "disasm": f"{ins.mnemonic} {ins.op_str}",
                    "caller_entry_guess": hex(
                        find_function_entry(text, text_rva, ins.address - IMAGE_BASE) or 0
                    ),
                }
            )
    return hits


def group_by_target(hits: list[dict]) -> dict[str, list[dict]]:
    g: dict[str, list[dict]] = defaultdict(list)
    for h in hits:
        g[h["target_rva"]].append(h)
    return dict(sorted(g.items(), key=lambda kv: int(kv[0], 16)))


def group_by_caller(hits: list[dict]) -> dict[str, int]:
    c: dict[str, int] = defaultdict(int)
    for h in hits:
        c[h["caller_entry_guess"]] += 1
    return dict(sorted(c.items(), key=lambda kv: -kv[1]))


def write_md(data: dict) -> None:
    lines = [
        "# SimStartRace — caller scan",
        "",
        "## Why string xrefs mislead",
        "",
        "`SimStartRace` @ `.rdata` `0x25BB70` is referenced by **movups** inside dispatch stubs",
        "(`0x32FA3`, `0x5F372`) — those sites copy the tag into a message object, they are **not**",
        "the function entry that starts a race. Ghidra `RaceCluster` export was empty for the same",
        "reason: **no function starts** in `0x90E00`–`0x92000`; race UI lives in `RaceStateMachine` @ `0x8F2B0`.",
        "",
        "## E8 callers into dispatch regions",
        "",
        "| Region | RVA range | Role |",
        "|--------|-----------|------|",
        "| `sim_spawn_dispatch` | `0x33000`–`0x35000` | Spawn / early sim (incl. `SimSpawnDisk` @ `0x33A20`) |",
        "| `sim_mid_dispatch` | `0x5F000`–`0x61000` | Mid sim handlers |",
        "",
        f"Total E8 hits (byte scan): **{data['summary']['e8_hits']}**",
        "",
        "### Top call targets",
        "",
    ]
    for tgt, callers in list(data["by_target"].items())[:15]:
        lines.append(f"- **{tgt}** — {len(callers)} caller(s)")
        for c in callers[:3]:
            lines.append(f"  - from `{c['call_rva']}` (fn `{c['caller_entry_guess']}`)")
    lines.extend(
        [
            "",
            "### Top caller functions (by E8 count)",
            "",
        ]
    )
    for ent, n in list(data["top_callers"].items())[:12]:
        lines.append(f"- `{ent}` — {n} call(s) into regions")
    lines.extend(
        [
            "",
            "## String xref sites (tag load only)",
            "",
        ]
    )
    for row in data["string_xrefs"]:
        lines.append(
            f"- **{row['name']}** @ `{row['site_rva']}` → entry guess `{row['entry_guess']}`"
        )
    lines.extend(
        [
            "",
            "## Frida",
            "",
            "```bat",
            "python RE_Tools/tools/scripts/frida_gameplay_hooks.py --attach --seconds 120",
            "```",
            "",
            "Start a race in-game; check `racego_hits` and `sim_start_region_calls` in",
            "`RE_Tools/analysis/gameplay_frida.json`.",
            "",
        ]
    )
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    if not EXE.is_file():
        print(f"Missing {EXE}")
        return 1
    raw = EXE.read_bytes()
    pe = pefile.PE(str(EXE))
    text, text_rva = text_blob(pe, raw)

    e8_hits = scan_e8_calls(text, text_rva)

    xref_rows = []
    for name, site in STRING_XREFS:
        xref_rows.append(
            {
                "name": name,
                "site_rva": hex(site),
                "entry_guess": hex(find_function_entry(text, text_rva, site) or 0),
            }
        )

    by_target = group_by_target(e8_hits)
    top_callers = group_by_caller(e8_hits)

    data = {
        "exe": str(EXE),
        "image_base": hex(IMAGE_BASE),
        "regions": [{"name": n, "lo": hex(lo), "hi": hex(hi)} for n, lo, hi in REGIONS],
        "pinned_entries": {k: hex(v) for k, v in PINNED_ENTRIES.items()},
        "string_xrefs": xref_rows,
        "summary": {
            "e8_hits": len(e8_hits),
            "unique_targets": len(by_target),
            "unique_callers": len(top_callers),
        },
        "by_target": {k: v[:20] for k, v in by_target.items()},
        "top_callers": dict(list(top_callers.items())[:40]),
        "note": "Prefer E8 targets with many callers or callers from Game_WorldSimStep / race FSM for SimStartRace body.",
    }
    OUT_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")
    write_md(data)
    print(f"Wrote {OUT_JSON} e8_hits={len(e8_hits)} targets={len(by_target)}")
    print(f"Wrote {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
