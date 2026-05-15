"""
Scan Horsey.exe for every filename in Game/data/ and Game/save/.

Output: RE_Tools/analysis/data_exe_xrefs.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))

from paths import get_data_dir, get_exe_path, get_save_dir  # noqa: E402

OUT = ROOT / "RE_Tools" / "analysis" / "data_exe_xrefs.json"


def find_all(blob: bytes, needle: bytes) -> list[int]:
    hits: list[int] = []
    start = 0
    while True:
        i = blob.find(needle, start)
        if i < 0:
            break
        hits.append(i)
        start = i + 1
    return hits


def main() -> int:
    exe = get_exe_path()
    blob = exe.read_bytes()
    image_base = 0x140000000  # PE64 default for Horsey.exe (verify in phase1_verify)

    entries: list[dict] = []

    paths: list[Path] = []
    for d in (get_data_dir(), get_save_dir()):
        if d.is_dir():
            paths.extend(sorted(d.iterdir()))

    for path in paths:
        if not path.is_file():
            continue
        name = path.name.encode("ascii", errors="ignore")
        if not name:
            continue
        offsets = find_all(blob, name)
        entries.append(
            {
                "file": path.name,
                "relative_dir": path.parent.name,
                "bytes": path.stat().st_size,
                "exe_file_offset": [hex(o) for o in offsets],
                "exe_rva_guess": [hex(image_base + o) for o in offsets] if offsets else [],
                "referenced_in_exe": bool(offsets),
            }
        )

    # useful suffixes / paths
    extras = [b"data\\", b"data/", b".crf", b".fnt", b"BMF", b"settings.xml", b"horsey.tmx"]
    extra_hits = {s.decode("ascii", errors="replace"): [hex(o) for o in find_all(blob, s)] for s in extras}

    report = {
        "exe": str(exe),
        "image_base_assumption": hex(image_base),
        "verification": "Substring search in Horsey.exe — not full xref graph",
        "files": entries,
        "extra_strings": extra_hits,
        "referenced_count": sum(1 for e in entries if e["referenced_in_exe"]),
        "unreferenced_count": sum(1 for e in entries if not e["referenced_in_exe"]),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"Referenced: {report['referenced_count']} / {len(entries)}")
    unref = [e["file"] for e in entries if not e["referenced_in_exe"]]
    if unref:
        print("Not found in exe strings:", ", ".join(unref[:20]), ("..." if len(unref) > 20 else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
