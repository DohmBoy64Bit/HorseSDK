"""
Frida: hook FileWrite @ 0x6F3C0 — log .crf / .fnt path fragments during startup.

Usage:
  python RE_Tools/tools/scripts/frida_font_trace.py --seconds 12

Output: RE_Tools/analysis/frida_font_trace.json
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

OUT = ROOT / "RE_Tools" / "analysis" / "frida_font_trace.json"
FILE_WRITE = 0x6F3C0

AGENT = r"""
'use strict';
var FW = __FW__;
var hits = [];

function readMsvcString(ptr) {
  try {
    if (ptr.isNull()) return null;
    var size = ptr.add(0x10).readU64();
    var cap = ptr.add(0x18).readU64();
    if (cap <= 15) return ptr.readUtf8String(Number(size));
    return ptr.readPointer().readUtf8String(Number(size));
  } catch (e) { return null; }
}

function modRva(a) {
  var m = Process.findModuleByAddress(a);
  if (m && m.name.toLowerCase() === 'horsey.exe')
    return 'Horsey.exe+' + a.sub(m.base).toString(16).toUpperCase();
  return a.toString();
}

Interceptor.attach(Process.findModuleByName('Horsey.exe').base.add(FW), {
  onEnter: function (args) {
    var frag = readMsvcString(args[1]);
    if (!frag) return;
    var low = frag.toLowerCase();
    if (low.indexOf('.crf') < 0 && low.indexOf('.fnt') < 0 && low.indexOf('quip') < 0)
      return;
    var row = { frag: frag, bt: Thread.backtrace(this.context, Backtracer.ACCURATE).slice(0,8).map(modRva) };
    hits.push(row);
    send({ type: 'font_io', row: row });
  }
});

rpc.exports.summary = function () { return { hits: hits }; };
"""


def main() -> int:
    import frida

    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=14.0)
    args = ap.parse_args()
    events = []
    device = frida.get_local_device()

    def on_msg(msg, _):
        if msg.get("type") == "send":
            events.append(msg["payload"])
            if msg["payload"].get("type") == "font_io":
                print(msg["payload"]["row"]["frag"][:80])

    pid = device.spawn([str(get_exe_path())], cwd=str(get_game_dir()))
    session = device.attach(pid)
    script = session.create_script(AGENT.replace("__FW__", str(FILE_WRITE)))
    script.on("message", on_msg)
    script.load()
    device.resume(pid)
    time.sleep(args.seconds)
    try:
        summary = script.exports_sync.summary()
    except Exception:
        summary = {"hits": []}
    try:
        session.detach()
    except Exception:
        pass
    report = {"ok": True, "hits": summary.get("hits", []), "events": events}
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} hits={len(report['hits'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
