"""
Frida: hook Game_WorldSimStep @ 0x88510 and Game_UpdateWorld @ 0x87510.

Usage:
  python RE_Tools/tools/scripts/frida_world_sim_step.py --seconds 15 --frames 6

Output: RE_Tools/analysis/frida_world_sim_step.json
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

OUT = ROOT / "RE_Tools" / "analysis" / "frida_world_sim_step.json"
SIM_RVA = 0x88510
UPDATE_RVA = 0x87510
SWAP_RVA = 0xBEAF0

AGENT = r"""
'use strict';
var SIM = __SIM__;
var UPDATE = __UPDATE__;
var SWAP = __SWAP__;
var MAX_FRAMES = __MAX_FRAMES__;

var horsey = null;
var frame = 0;
var updateHits = [];
var simHits = [];
var perFrame = [];

function modRva(addr) {
    var m = Process.findModuleByAddress(addr);
    if (m && m.name.toLowerCase() === 'horsey.exe')
        return 'Horsey.exe+' + addr.sub(m.base).toString(16).toUpperCase();
    return addr.toString();
}

function install() {
    horsey = Process.findModuleByName('Horsey.exe');
    if (!horsey) return false;

    Interceptor.attach(horsey.base.add(SWAP), {
        onEnter: function () {
            perFrame.push({
                frame: frame,
                updates: updateHits.length,
                sims: simHits.length
            });
            send({ type: 'frame', frame: frame, row: perFrame[perFrame.length - 1] });
            frame++;
            if (frame >= MAX_FRAMES) send({ type: 'done' });
        }
    });

    Interceptor.attach(horsey.base.add(UPDATE), {
        onEnter: function (args) {
            var row = {
                rcx: args[0].toInt32(),
                backtrace: Thread.backtrace(this.context, Backtracer.ACCURATE)
                    .slice(0, 6).map(modRva)
            };
            updateHits.push(row);
            send({ type: 'update', row: row });
        }
    });

    Interceptor.attach(horsey.base.add(SIM), {
        onEnter: function (args) {
            var row = {
                backtrace: Thread.backtrace(this.context, Backtracer.ACCURATE)
                    .slice(0, 6).map(modRva)
            };
            simHits.push(row);
            send({ type: 'sim', row: row });
        }
    });
    return true;
}

rpc.exports.summary = function () {
    return { updateHits: updateHits, simHits: simHits, perFrame: perFrame };
};

if (Process.findModuleByName('Horsey.exe')) install();
else {
    var t = setInterval(function () { if (install()) clearInterval(t); }, 50);
}
"""


def main() -> int:
    import frida

    ap = argparse.ArgumentParser()
    ap.add_argument("--attach", action="store_true")
    ap.add_argument("--seconds", type=float, default=18.0)
    ap.add_argument("--frames", type=int, default=8)
    args = ap.parse_args()

    agent = (
        AGENT.replace("__SIM__", str(SIM_RVA))
        .replace("__UPDATE__", str(UPDATE_RVA))
        .replace("__SWAP__", str(SWAP_RVA))
        .replace("__MAX_FRAMES__", str(args.frames))
    )
    events = []
    device = frida.get_local_device()

    def on_message(message, _data):
        if message.get("type") == "send":
            events.append(message["payload"])
            p = message["payload"]
            if p.get("type") in ("sim", "update", "frame"):
                print(p.get("type"), json.dumps(p)[:120])

    if args.attach:
        session = device.attach("Horsey.exe")
        pid = None
    else:
        pid = device.spawn([str(get_exe_path())], cwd=str(get_game_dir()))
        session = device.attach(pid)

    script = session.create_script(agent)
    script.on("message", on_message)
    script.load()
    if not args.attach:
        device.resume(pid)
    time.sleep(args.seconds)
    try:
        summary = script.exports_sync.summary()
    except Exception:
        summary = {}
    try:
        session.detach()
    except Exception:
        pass

    report = {
        "ok": True,
        "update_count": len(summary.get("updateHits", [])),
        "sim_count": len(summary.get("simHits", [])),
        "per_frame": summary.get("perFrame", []),
        "events": events,
        "ratio_sim_per_update": (
            len(summary.get("simHits", [])) / max(1, len(summary.get("updateHits", [])))
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} updates={report['update_count']} sim={report['sim_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
