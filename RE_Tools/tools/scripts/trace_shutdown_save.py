"""
Static trace: Shutdown_Prep @ 0x98680 -> Save_Write @ 0x6DAB0.

BFS over E8 call edges in .text until Save_Write or depth limit.

Output: RE_Tools/analysis/shutdown_save_callchain.json
        RE_Tools/docs/Shutdown_Save_Callchain.md
"""
from __future__ import annotations

import json
import re
import sys
from collections import deque
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_64, Cs

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
from paths import get_exe_path  # noqa: E402

SHUTDOWN_PREP = 0x98680
SAVE_WRITE = 0x6DAB0
SETTINGS_SAVE = 0x71F60
MAX_DEPTH = 8
MAX_FUNCS = 4000

INTERNAL = {
    0x98680: "Shutdown_Prep",
    0x6DAB0: "Save_Write",
    0x71F60: "Settings_Save",
    0x99D70: "Shutdown_Helper_99D70",
    0x99BC0: "Shutdown_Helper_99BC0",
    0x994A0: "Shutdown_Helper_994A0",
    0xBED0C: "Shutdown_Entry",
    0xBED11: "Settings_Save_Call",
}


def build_call_graph(raw: bytes, pe: pefile.PE) -> dict[int, list[int]]:
    """E8 call edges plus near jmp to functions (e.g. jmp Save_Write @ 0x9869A)."""
    text = next(s for s in pe.sections if s.Name.rstrip(b"\x00") == b".text")
    blob = raw[text.PointerToRawData : text.PointerToRawData + text.SizeOfRawData]
    base = text.VirtualAddress
    graph: dict[int, list[int]] = {}
    for i in range(len(blob) - 5):
        if blob[i] != 0xE8:
            continue
        rel = int.from_bytes(blob[i + 1 : i + 5], "little", signed=True)
        src = base + i
        dst = src + 5 + rel
        if 0x1000 <= dst < 0x200000:
            graph.setdefault(src, []).append(dst)

    # Near jmp rel32 (E9) — linear Capstone over .text desyncs; scan opcodes directly.
    for i in range(len(blob) - 5):
        if blob[i] != 0xE9:
            continue
        rel = int.from_bytes(blob[i + 1 : i + 5], "little", signed=True)
        src = base + i
        dst = src + 5 + rel
        if 0x1000 <= dst < 0x200000:
            graph.setdefault(src, []).append(dst)
    return graph


def fn_name(rva: int) -> str:
    return INTERNAL.get(rva, hex(rva))


def find_paths(graph: dict[int, list[int]], start: int, goal: int, max_depth: int) -> list[list[int]]:
    """BFS from any E8 in [start, start+0x800) to goal."""
    origins = sorted(src for src in graph if start <= src < start + 0x800)
    if 0x9869A in graph and 0x9869A not in origins:
        origins.append(0x9869A)
    if not origins:
        origins = [start]
    paths: list[list[int]] = []
    for origin in origins[:20]:
        q: deque[tuple[int, list[int]]] = deque([(origin, [origin])])
        seen = {origin}
        while q:
            node, path = q.popleft()
            if len(path) > max_depth:
                continue
            if node == goal:
                paths.append(path)
                if len(paths) >= 5:
                    break
                continue
            for nxt in graph.get(node, []):
                if nxt in seen:
                    continue
                seen.add(nxt)
                q.append((nxt, path + [nxt]))
    return paths


def callees_in_range(graph: dict[int, list[int]], lo: int, hi: int) -> list[int]:
    out = []
    for src, dsts in graph.items():
        if lo <= src < hi:
            for d in dsts:
                if d not in out:
                    out.append(d)
    return sorted(out)


def main() -> int:
    pe = pefile.PE(str(get_exe_path()))
    raw = Path(get_exe_path()).read_bytes()
    graph = build_call_graph(raw, pe)

    prep_callees = callees_in_range(graph, SHUTDOWN_PREP, SHUTDOWN_PREP + 0x600)
    paths_to_save = find_paths(graph, SHUTDOWN_PREP, SAVE_WRITE, MAX_DEPTH)
    paths_to_settings = find_paths(graph, SHUTDOWN_PREP, SETTINGS_SAVE, MAX_DEPTH)

  # Also search from each direct callee
    extended_paths = list(paths_to_save)
    for c in prep_callees:
        extended_paths.extend(find_paths(graph, c, SAVE_WRITE, MAX_DEPTH))

    # Dedupe path strings
    uniq_paths = []
    seen = set()
    for p in extended_paths:
        key = tuple(p)
        if key in seen:
            continue
        seen.add(key)
        uniq_paths.append([fn_name(x) for x in p])

    payload = {
        "start": fn_name(SHUTDOWN_PREP),
        "goal_save_write": fn_name(SAVE_WRITE),
        "direct_callees_98680": [fn_name(c) for c in prep_callees],
        "paths_to_save_write": uniq_paths[:10],
        "paths_to_settings_save": [[fn_name(x) for x in p] for p in paths_to_settings[:5]],
        "save_write_call_sites_in_prep_region": [
            hex(src)
            for src, dsts in graph.items()
            if SHUTDOWN_PREP <= src < SHUTDOWN_PREP + 0x600 and SAVE_WRITE in dsts
        ],
        "verified_jmp": {
            "at": "0x9869A",
            "target": "Save_Write @ 0x6DAB0",
            "note": "tail jmp — not E8; BFS must include jmp edges",
        },
    }

    out = ROOT / "RE_Tools" / "analysis" / "shutdown_save_callchain.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md = [
        "# Shutdown prep → `Save_Write` (Capstone call graph)",
        "",
        f"**Root:** `Shutdown_Prep` @ **`0x98680`** (called from `GameMain` @ `0xBED0C`)",
        "",
        f"**Artifact:** `{out.relative_to(ROOT)}`",
        "",
        "## Direct callees of `0x98680`",
        "",
    ]
    for c in payload["direct_callees_98680"]:
        md.append(f"- `{c}`")
    md.extend(["", "## Paths to `Save_Write` @ `0x6DAB0`", ""])
    if uniq_paths:
        for i, p in enumerate(uniq_paths[:8], 1):
            md.append(f"{i}. `{'` → `'.join(p)}`")
    else:
        md.append("*No E8 path within depth limit — may use register/indirect call.*")
    if payload["save_write_call_sites_in_prep_region"]:
        md.extend(["", "## Direct E8 in prep region", ""])
        for s in payload["save_write_call_sites_in_prep_region"]:
            md.append(f"- `{s}`")

    doc = ROOT / "RE_Tools" / "docs" / "Shutdown_Save_Callchain.md"
    doc.write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote {out} paths={len(uniq_paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
