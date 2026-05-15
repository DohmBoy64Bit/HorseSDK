"""
Frida: hook Game_SimStep @ 0xC12D0 vs Game_UpdateWorld @ 0x87510.

Usage:
  python RE_Tools/tools/scripts/frida_game_sim_step.py --seconds 15

Output: RE_Tools/analysis/frida_game_sim_step.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
from paths import get_exe_path, get_game_dir  # noqa: E402

OUT = ROOT / "RE_Tools" / "analysis" / "frida_game_sim_step.json"
SIM = 0xC12D0
UPDATE = 0x87510
SWAP = 0xBEAF0

AGENT = r"""
'use strict';
var SIM = __SIM__;
var UPDATE = __UPDATE__;
var SWAP = __SWAP__;
var MAX_FRAMES = __MAX_FRAMES__;

var horsey = null;
var simHits = 0, updateHits = 0, frame = 0;

function modRva(a) {
  var m = Process.findModuleByAddress(a);
  if (m && m.name.toLowerCase() === 'horsey.exe')
    return 'Horsey.exe+' + a.sub(m.base).toString(16).toUpperCase();
  return a.toString();
}

function install() {
  horsey = Process.findModuleByName('Horsey.exe');
  if (!horsey) return false;
  Interceptor.attach(horsey.base.add(SWAP), {
    onEnter: function () {
      send({ type: 'frame', frame: frame, sim: simHits, update: updateHits });
      frame++;
      simHits = 0;
      updateHits = 0;
      if (frame >= MAX_FRAMES) send({ type: 'done' });
    }
  });
  Interceptor.attach(horsey.base.add(SIM), {
    onEnter: function (args) {
      simHits++;
      if (simHits <= 3)
        send({ type: 'sim', rcx: args[0].toString(),
          bt: Thread.backtrace(this.context, Backtracer.ACCURATE).slice(0,6).map(modRva) });
    }
  });
  Interceptor.attach(horsey.base.add(UPDATE), {
    onEnter: function (args) {
      updateHits++;
    }
  });
  return true;
}

rpc.exports.summary = function () {
  return { frames: frame };
};

if (Process.findModuleByName('Horsey.exe')) install();
else setInterval(function () { if (install()) clearInterval(this); }, 50);
"""


def main() -> int:
    import frida

    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=18.0)
    ap.add_argument("--frames", type=int, default=12)
    args = ap.parse_args()

    agent = (
        AGENT.replace("__SIM__", str(SIM))
        .replace("__UPDATE__", str(UPDATE))
        .replace("__SWAP__", str(SWAP))
        .replace("__MAX_FRAMES__", str(args.frames))
    )
    events: list = []
    device = frida.get_local_device()

    def on_msg(msg, _):
        if msg.get("type") == "send":
            events.append(msg["payload"])
            p = msg["payload"]
            if p.get("type") in ("sim", "frame", "done"):
                print(p.get("type"), json.dumps(p)[:140])

    pid = device.spawn([str(get_exe_path())], cwd=str(get_game_dir()))
    session = device.attach(pid)
    script = session.create_script(agent)
    script.on("message", on_msg)
    script.load()
    device.resume(pid)
    time.sleep(args.seconds)
    try:
        session.detach()
    except Exception:
        pass

    frames = [e for e in events if e.get("type") == "frame"]
    sim_per = [e.get("sim", 0) for e in frames]
    report = {
        "ok": True,
        "frame_count": len(frames),
        "sim_per_frame_avg": sum(sim_per) / max(1, len(sim_per)),
        "sim_per_frame_max": max(sim_per) if sim_per else 0,
        "update_per_frame_avg": sum(e.get("update", 0) for e in frames) / max(1, len(frames)),
        "events": events,
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} frames={len(frames)} avg_sim={report['sim_per_frame_avg']:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
