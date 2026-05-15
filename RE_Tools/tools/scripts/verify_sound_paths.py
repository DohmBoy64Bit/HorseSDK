"""
Verify every sound.xml f= path exists under Game/.
Output: RE_Tools/analysis/sound_path_verify.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "parsers"))

from paths import get_data_dir, get_game_dir  # noqa: E402
from sound import SoundSet  # noqa: E402

OUT = ROOT / "RE_Tools" / "analysis" / "sound_path_verify.json"


def main() -> int:
    game = get_game_dir()
    ss = SoundSet.load(get_data_dir() / "sound.xml")
    missing: list[dict] = []
    found: list[str] = []

    sound_dir = game / "sound"
    for ev in ss.music_events + ss.sound_events:
        if not ev.file:
            continue
        rel = ev.file.replace("/", "\\")
        candidates = [game / rel, sound_dir / Path(rel).name, sound_dir / rel]
        if any(p.is_file() for p in candidates):
            found.append(rel)
        else:
            missing.append({"name": ev.name, "type": ev.event_type, "path": rel})

    report = {
        "music_count": len(ss.music_events),
        "sound_count": len(ss.sound_events),
        "unique_paths": len(set(found) | {m["path"] for m in missing}),
        "found": len(found),
        "missing": missing,
        "all_found": len(missing) == 0,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} — missing {len(missing)}")
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
