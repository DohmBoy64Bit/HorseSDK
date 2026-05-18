#!/usr/bin/env python3
"""
Probe candidate view/camera floats while you pan the farm.

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

G_GAME_STATE = 0x313720
SAVE_CTX_VEC2 = 0x39C

AGENT = r"""
'use strict';
var G_GAME = __G_GAME__;
var samples = [];
var last = 0;

function sample(label, p) {
  if (p.isNull()) return;
  try {
    samples.push({
      label: label,
      ptr: p.toString(),
      f394: p.add(0x394).readFloat(),
      f398: p.add(0x398).readFloat(),
      f39c: p.add(0x39C).readFloat(),
      f3a0: p.add(0x3A0).readFloat()
    });
  } catch (e) {}
}

setInterval(function () {
  var now = Date.now();
  if (now - last < 500) return;
  last = now;
  var base = Process.findModuleByName('Horsey.exe').base;
  var gs = base.add(G_GAME).readPointer();
  sample('g_game_state', gs);
}, 500);

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

    session = device.attach(procs[0].pid)
    script = session.create_script(AGENT.replace("__G_GAME__", str(G_GAME_STATE)))
    script.load()
    print(f"Attached pid={procs[0].pid}. Pan the farm for {args.seconds}s...")
    time.sleep(args.seconds)
    samples = script.exports_sync.dump()
    session.detach()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "g_game_state_rva": hex(G_GAME_STATE),
        "save_ctx_vec2_off": hex(SAVE_CTX_VEC2),
        "sample_count": len(samples),
        "samples": samples[-40:],
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} ({len(samples)} samples)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
