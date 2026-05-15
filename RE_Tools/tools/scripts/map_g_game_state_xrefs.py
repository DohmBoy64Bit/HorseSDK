"""
Map xrefs to g_game_state @ 0x313720 (pointer qword in .data).

Outputs:
  RE_Tools/analysis/phase1_g_game_state.json
  RE_Tools/docs/g_game_state.md
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "scripts"))

from re_pe_util import load_pe, scan_rip_refs  # noqa: E402

G_GAME_STATE = 0x313720
NAMES = {
    0x874F1: "Game_BootstrapWorld_store",
    0xBEAD4: "GameMain_call_UpdateWorld",
    0x6DAB0: "Save_Write",
    0x6E2B0: "Save_Load",
}


def scan_mov_rip_stores(raw: bytes, pe, target: int) -> list[dict]:
    """Pattern-scan 48 89 xx rel32 stores to [rip+disp]==target."""
    from re_pe_util import text_section

    blob, base = text_section(pe)
    hits = []
    for i in range(len(blob) - 7):
        b0, b1, b2 = blob[i], blob[i + 1], blob[i + 2]
        if b0 != 0x48 or b1 != 0x89:
            continue
        if b2 not in (0x05, 0x0D, 0x15, 0x1D, 0x25, 0x2D, 0x35, 0x3D):
            continue
        rel = struct.unpack_from("<i", blob, i + 3)[0]
        src = base + i
        insn_len = 7
        if src + insn_len + rel == target:
            hits.append({"at": hex(src), "pattern": "mov [rip], reg", "opcode": blob[i : i + 7].hex()})
    return hits


def scan_mov_rip_loads(raw: bytes, pe, target: int) -> list[dict]:
    from re_pe_util import text_section

    blob, base = text_section(pe)
    hits = []
    for i in range(len(blob) - 7):
        if blob[i] != 0x48 or blob[i + 1] not in (0x8B, 0x8D):
            continue
        b2 = blob[i + 2]
        if b2 not in (0x05, 0x0D, 0x15, 0x1D, 0x25, 0x2D, 0x35, 0x3D):
            continue
        rel = struct.unpack_from("<i", blob, i + 3)[0]
        src = base + i
        if src + 7 + rel == target:
            hits.append({"at": hex(src), "pattern": "mov/lea reg, [rip]", "opcode": blob[i : i + 7].hex()})
    return hits


def region_label(rva: int) -> str:
    if 0xBE000 <= rva < 0xBF000:
        return "GameMain"
    if 0x87000 <= rva < 0x89000:
        return "Game_Update"
    if 0x6D000 <= rva < 0x6F000:
        return "Save_IO"
    if 0x97000 <= rva < 0x99000:
        return "GameState_Init"
    if 0x87000 <= rva < 0x87600:
        return "Bootstrap"
    return "other"


def main() -> int:
    pe, raw = load_pe()
    stores = scan_mov_rip_stores(raw, pe, G_GAME_STATE)
    loads = scan_mov_rip_loads(raw, pe, G_GAME_STATE)
    rip = scan_rip_refs(raw, pe, G_GAME_STATE, window=8)

    all_sites = sorted(
        {h["at"] for h in stores + loads + rip},
        key=lambda x: int(x, 16),
    )
    by_region: dict[str, list[str]] = {}
    for s in all_sites:
        rva = int(s, 16)
        reg = region_label(rva)
        by_region.setdefault(reg, []).append(s)

    payload = {
        "global": "g_game_state",
        "rva": hex(G_GAME_STATE),
        "va": hex(0x140000000 + G_GAME_STATE),
        "set_by": "Game_BootstrapWorld @ 0x874F1 mov [rip+0x28C228], rbx",
        "stores": stores,
        "loads": loads,
        "rip_refs_near": rip,
        "sites_unique": all_sites,
        "by_region": by_region,
    }
    out = ROOT / "RE_Tools" / "analysis" / "phase1_g_game_state.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md = [
        "# `g_game_state` @ `0x313720`",
        "",
        "**Global:** `qword` pointer to `GameState` object (`operator_new(0x30)` + `GameState_Ctor` @ bootstrap).",
        "",
        f"**Artifact:** `{out.relative_to(ROOT)}`",
        "",
        "## Write (bootstrap)",
        "",
        "- `0x874F1` — `mov [g_game_state], rbx` after `GameState_Ctor`",
        "",
        "## Reads / uses (Capstone RIP scan)",
        "",
        f"**{len(loads)}** `mov/lea reg, [rip→g_game_state]` · **{len(stores)}** stores · **{len(all_sites)}** unique sites",
        "",
    ]
    for reg, sites in sorted(by_region.items()):
        md.append(f"### {reg}")
        for s in sites[:20]:
            md.append(f"- `{s}`")
        if len(sites) > 20:
            md.append(f"- … +{len(sites) - 20} more")
        md.append("")

    doc = ROOT / "RE_Tools" / "docs" / "g_game_state.md"
    doc.write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote {out} sites={len(all_sites)} loads={len(loads)} stores={len(stores)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
