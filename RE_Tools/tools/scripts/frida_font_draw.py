"""
Frida: hook Font_DrawString @ 0x80D10 — log glyph indices and width-table bytes.

Usage:
  python RE_Tools/tools/scripts/frida_font_draw.py --seconds 25

Output: RE_Tools/analysis/frida_font_draw.json
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

OUT = ROOT / "RE_Tools" / "analysis" / "frida_font_draw.json"
FONT_DRAW = 0x80D10
UI_DRAW_CALL = 0x3562B  # call Font_DrawString from UI cluster

AGENT = r"""
'use strict';
var FONT_DRAW = __FONT_DRAW__;
var UI_CALL = __UI_CALL__;
var hits = [];
var maxHits = 150;

function modRva(a) {
  var m = Process.findModuleByAddress(a);
  if (m && m.name.toLowerCase() === 'horsey.exe')
    return 'Horsey.exe+' + a.sub(m.base).toString(16).toUpperCase();
  return a.toString();
}

var base = Process.findModuleByName('Horsey.exe').base;

function logDraw(font, textPtr, bt) {
  if (hits.length >= maxHits) return;
  try {
    if (textPtr.isNull()) return;
    var s = textPtr.readUtf8String(48);
    if (!s || s.length < 1) return;
    var row = { text: s.substring(0, 40), font: font.toString(), bt: bt };
    hits.push(row);
    send({ type: 'draw', row: row });
  } catch (e) {}
}

Interceptor.attach(base.add(UI_CALL), {
  onEnter: function (args) {
    var font = this.context.rcx;
    var textPtr = this.context.rsp.add(0x30).readPointer();
    logDraw(font, textPtr, Thread.backtrace(this.context, Backtracer.ACCURATE).slice(0, 5).map(modRva));
  }
});

Interceptor.attach(base.add(FONT_DRAW), {
  onEnter: function (args) {
    var font = args[0];
    var bt = Thread.backtrace(this.context, Backtracer.ACCURATE).slice(0, 5).map(modRva);
    var p30 = this.context.rsp.add(0x30).readPointer();
    logDraw(font, p30, bt);
  }
});

rpc.exports.summary = function () { return { hits: hits }; };
"""


def main() -> int:
    import frida

    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=22.0)
    args = ap.parse_args()
    events: list = []
    device = frida.get_local_device()

    def on_msg(msg, _):
        if msg.get("type") == "send":
            events.append(msg["payload"])
            p = msg["payload"]
            if p.get("type") == "draw":
                print(repr(p["row"]["text"][:40]))

    pid = device.spawn([str(get_exe_path())], cwd=str(get_game_dir()))
    session = device.attach(pid)
    script = session.create_script(
        AGENT.replace("__FONT_DRAW__", str(FONT_DRAW)).replace(
            "__UI_CALL__", str(UI_DRAW_CALL)
        )
    )
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
    report = {"ok": True, **summary, "events": events}
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} hits={len(summary.get('hits', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
