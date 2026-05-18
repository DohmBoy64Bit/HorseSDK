# Race correlation report (auto-generated)

**Source:** `RE_Tools/analysis/gameplay_frida.json`
**Script:** `analyze_race_correlation.py`
**RE:** [RaceMechanics.md](RaceMechanics.md) — score @ `[race_ctx+0x450]`, not `[horse+0x450]`.

## Summary

- Captured 2 sim tick(s), 8 horse slot reading(s).
- snapshot.race_score_450 missing — update frida_gameplay_hooks.py and re-capture.
- Per-horse score_450 in JSON is identical garbage — do NOT read [horse+0x450]; use [race_ctx+0x450] only (see RaceMechanics.md).
- finish_place vs progress (higher progress -> better placement): place=2 avg_progress=2778, place=1 avg_progress=2532, place=0 avg_progress=1696
- OK: highest progress aligns with best (lowest) finish_place index.
- 3 slot reading(s) with finish_place=-1 (still racing).

## finish_place → mean progress

| finish_place | mean progress |
|--------------|---------------|
| 2 | 2778 |
| 1 | 2532 |
| 0 | 1696 |

## race_score_450 (ctx)

Values observed: `[]`

## Re-capture

```bat
python RE_Tools\tools\scripts\run_frida_race_capture.py
```

Play a full race, press Enter when done, then re-run this script.

