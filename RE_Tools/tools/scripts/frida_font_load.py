"""
Frida: hook real .crf load path — Font_LoadOrInit @ 0x7F8A0, fopen layer @ 0x6FB90.

0x6F3C0 is write/append stream (saves + font path builder), NOT file read.

Usage:
  python RE_Tools/tools/scripts/frida_font_load.py --seconds 20

Output: RE_Tools/analysis/frida_font_load.json
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

OUT = ROOT / "RE_Tools" / "analysis" / "frida_font_load.json"
FONT_LOAD = 0x7F8A0
STREAM_READ = 0x6FB90

AGENT = r"""
'use strict';
var FONT_LOAD = __FONT_LOAD__;
var STREAM_READ = __STREAM_READ__;
var loads = [];
var reads = [];

function readStdString(ptr) {
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

function bt(ctx) {
  return Thread.backtrace(ctx, Backtracer.ACCURATE).slice(0, 10).map(modRva);
}

Interceptor.attach(Process.findModuleByName('Horsey.exe').base.add(FONT_LOAD), {
  onEnter: function (args) {
    var path = readStdString(args[1]);
    var row = {
      path: path,
      r8: args[2].toInt32(),
      ctx: args[0].toString(),
      bt: bt(this.context)
    };
    loads.push(row);
    send({ type: 'font_load', row: row });
  }
});

Interceptor.attach(Process.findModuleByName('Horsey.exe').base.add(STREAM_READ), {
  onEnter: function (args) {
    var path = readStdString(args[1]);
    if (!path) return;
    var low = path.toLowerCase();
    if (low.indexOf('.crf') < 0 && low.indexOf('.fnt') < 0 && low.indexOf('data') < 0)
      return;
    var row = { path: path, bt: bt(this.context) };
    reads.push(row);
    send({ type: 'stream_read', row: row });
  }
});

rpc.exports.summary = function () {
  return { font_loads: loads, stream_reads: reads };
};
"""


def main() -> int:
    import frida

    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=18.0)
    args = ap.parse_args()
    events: list = []
    device = frida.get_local_device()

    def on_msg(msg, _):
        if msg.get("type") == "send":
            events.append(msg["payload"])
            p = msg["payload"]
            if p.get("type") in ("font_load", "stream_read"):
                print(p["row"].get("path", "")[:100])

    pid = device.spawn([str(get_exe_path())], cwd=str(get_game_dir()))
    session = device.attach(pid)
    script = session.create_script(
        AGENT.replace("__FONT_LOAD__", str(FONT_LOAD)).replace(
            "__STREAM_READ__", str(STREAM_READ)
        )
    )
    script.on("message", on_msg)
    script.load()
    device.resume(pid)
    time.sleep(args.seconds)
    try:
        summary = script.exports_sync.summary()
    except Exception:
        summary = {"font_loads": [], "stream_reads": []}
    try:
        session.detach()
    except Exception:
        pass
    report = {"ok": True, **summary, "events": events}
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        f"Wrote {OUT} loads={len(summary.get('font_loads', []))} "
        f"reads={len(summary.get('stream_reads', []))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
