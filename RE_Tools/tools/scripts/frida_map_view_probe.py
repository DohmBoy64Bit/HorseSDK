#!/usr/bin/env python3
"""
Probe minimap view candidates while you pan the farm.

  python RE_Tools/tools/scripts/frida_map_view_probe.py --attach --seconds 60

Output: RE_Tools/analysis/map_view_probe.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))

from paths import get_exe_path  # noqa: E402

OUT = ROOT / "RE_Tools" / "analysis" / "map_view_probe.json"

G_SAVE_CONTEXT = 0x31A660
OFF_HORSE_OBJ = 0x300
OFF_HORSE_VIEW = 0x28
OFF_CAM_X = 0x394
OFF_CAM_Y = 0x398

AGENT = r"""
'use strict';
var G_SAVE = __G_SAVE__;
var samples = [];
var last = 0;

function rf(p, off) {
  try { return p.add(off).readFloat(); } catch (e) { return null; }
}

function sample() {
  var base = Process.findModuleByName('Horsey.exe').base;
  var slot = base.add(G_SAVE);
  var ctx = ptr(0);
  try { ctx = slot.readPointer(); } catch (e) { return; }
  if (ctx.isNull()) return;
  var horse = ptr(0);
  try { horse = ctx.add(0x300).readPointer(); } catch (e) {}
  var row = {
    t: Date.now(),
    ctx: ctx.toString(),
    cam394: rf(ctx, 0x394),
    cam398: rf(ctx, 0x398),
    horse_ptr: horse.isNull() ? null : horse.toString(),
    horse28_x: horse.isNull() ? null : rf(horse, 0x28),
    horse28_y: horse.isNull() ? null : rf(horse, 0x2c)
  };
  samples.push(row);
}

setInterval(function () {
  var now = Date.now();
  if (now - last < 400) return;
  last = now;
  sample();
}, 400);

rpc.exports.dump = function () { return samples; };
"""


def main() -> int:
    import frida

    ap = argparse.ArgumentParser()
    ap.add_argument("--attach", action="store_true", required=True)
    ap.add_argument("--seconds", type=float, default=60.0)
    args = ap.parse_args()

    exe = get_exe_path()
    if not exe.is_file():
        print(f"Missing {exe}")
        return 1

    device = frida.get_local_device()
    procs = [p for p in device.enumerate_processes() if p.name.lower() == "horsey.exe"]
    if not procs:
        print("Start Horsey.exe with a save loaded, then re-run.")
        return 1

    src = AGENT.replace("__G_SAVE__", str(G_SAVE_CONTEXT))
    session = device.attach(procs[0].pid)
    script = session.create_script(src)
    script.load()
    print(f"Attached pid={procs[0].pid}. Pan the farm for {args.seconds}s...")
    time.sleep(args.seconds)
    samples = script.exports_sync.dump()
    session.detach()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "g_save_context_rva": hex(G_SAVE_CONTEXT),
        "offsets": {
            "horse_obj": hex(OFF_HORSE_OBJ),
            "horse_view": hex(OFF_HORSE_VIEW),
            "camera_x": hex(OFF_CAM_X),
            "camera_y": hex(OFF_CAM_Y),
        },
        "sample_count": len(samples),
        "samples": samples[-60:],
        "note": "Prefer horse_obj+0x28 when it changes with pan; ctx+0x394 is footer camera.",
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} ({len(samples)} samples)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
