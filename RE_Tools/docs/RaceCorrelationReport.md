# Race correlation report (auto-generated)

**Source:** `RE_Tools/analysis/gameplay_frida.json`
**Script:** `analyze_race_correlation.py`
**RE:** [RaceMechanics.md](RaceMechanics.md) — score @ `[race_ctx+0x450]`, not `[horse+0x450]`.

## Summary

- Captured 3 sim tick(s), 12 horse slot reading(s).
- race_ctx+0x450 (race_score_450): min=980 max=980 (single race power dword per RaceMechanics.md @ 0xE2FBD).
- finish_place vs progress (higher progress -> better placement): place=0 avg_progress=1763
- 9 slot reading(s) with finish_place=-1 (still racing).

## finish_place → mean progress

| finish_place | mean progress |
|--------------|---------------|
| 0 | 1763 |

## race_score_450 (ctx)

Values observed: `[980, 980, 980]`

## Status

**Pinned** in [RaceMechanics.md](RaceMechanics.md) (2026-05). Re-run capture only after exe update or if you want a full-finish progress table (optional).

## Re-capture (optional)

```bat
python RE_Tools\tools\scripts\run_frida_race_capture.py --seconds 300
```

