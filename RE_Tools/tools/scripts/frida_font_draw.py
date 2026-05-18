"""
Frida: hook Font_DrawString @ 0x80D10 — log UTF-8 strings during UI/gameplay.

Hooks:
  Horsey.exe+0x80D32  after `mov r12, [rsp+0xE0]` (text in r12) — all callers
  Horsey.exe+0x3562B  UI cluster (text at caller [rsp+0x30], habit_mono)

Usage:
  python RE_Tools/tools/scripts/frida_font_draw.py --seconds 45
  python RE_Tools/tools/scripts/frida_font_draw.py --attach --seconds 60

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
FONT_DRAW_TEXT_LOADED = 0x80D32  # after r12 = text ptr
UI_DRAW_CALL = 0x3562B
FONT_GLOBALS = {
    "habit_mono": 0x313538,
    "quip": 0x313540,
    "capy_bold": 0x313548,
}

AGENT = r"""
'use strict';
var TEXT_HOOK = __TEXT_HOOK__;
var UI_CALL = __UI_CALL__;
var FONT_GLOBALS = __FONT_GLOBALS__;
var hits = [];
var seen = {};
var maxHits = 400;

function modRva(a) {
  var m = Process.findModuleByAddress(a);
  if (m && m.name.toLowerCase() === 'horsey.exe')
    return 'Horsey.exe+' + a.sub(m.base).toString(16).toUpperCase();
  return a.toString();
}

function fontName(ptr) {
  var base = Process.findModuleByName('Horsey.exe').base;
  for (var k in FONT_GLOBALS) {
    try {
      var g = base.add(FONT_GLOBALS[k]).readPointer();
      if (g.equals(ptr)) return k;
    } catch (e) {}
  }
  return ptr.toString();
}

function readText(ptr) {
  try {
    if (ptr.isNull()) return null;
    return ptr.readUtf8String(96);
  } catch (e) {
    return null;
  }
}

function logDraw(where, font, textPtr, bt) {
  if (hits.length >= maxHits) return;
  var s = readText(textPtr);
  if (!s || s.length < 1) return;
  var key = where + '|' + fontName(font) + '|' + s;
  if (seen[key]) return;
  seen[key] = 1;
  var row = {
    where: where,
    text: s.substring(0, 80),
    font: fontName(font),
    bt: bt
  };
  hits.push(row);
  send({ type: 'draw', row: row });
}

var base = Process.findModuleByName('Horsey.exe').base;

Interceptor.attach(base.add(TEXT_HOOK), {
  onEnter: function () {
    var font = this.context.r14;
    var textPtr = this.context.r12;
    var bt = Thread.backtrace(this.context, Backtracer.ACCURATE).slice(0, 6).map(modRva);
    logDraw('Font_DrawString+0x22', font, textPtr, bt);
  }
});

Interceptor.attach(base.add(UI_CALL), {
  onEnter: function () {
    var font = this.context.rcx;
    var textPtr = this.context.rsp.add(0x30).readPointer();
    var bt = Thread.backtrace(this.context, Backtracer.ACCURATE).slice(0, 6).map(modRva);
    logDraw('UI_0x3562B', font, textPtr, bt);
  }
});

rpc.exports.summary = function () {
  return { hits: hits, unique: Object.keys(seen).length };
};
"""


def main() -> int:
    import frida

    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=45.0)
    ap.add_argument(
        "--attach",
        action="store_true",
        help="Attach to running Horsey.exe instead of spawn",
    )
    args = ap.parse_args()
    events: list = []
    device = frida.get_local_device()

    def on_msg(msg, _):
        if msg.get("type") == "send":
            events.append(msg["payload"])
            p = msg["payload"]
            if p.get("type") == "draw":
                print(p["row"]["where"], repr(p["row"]["text"][:60]), p["row"]["font"])

    script_src = (
        AGENT.replace("__TEXT_HOOK__", str(FONT_DRAW_TEXT_LOADED))
        .replace("__UI_CALL__", str(UI_DRAW_CALL))
        .replace("__FONT_GLOBALS__", json.dumps(FONT_GLOBALS))
    )

    if args.attach:
        procs = [
            p
            for p in device.enumerate_processes()
            if p.name.lower() in ("horsey.exe", "horsey")
        ]
        if not procs:
            print("No Horsey.exe process — start the game or omit --attach")
            return 1
        pid = procs[0].pid
        session = device.attach(pid)
        print(f"Attached pid={pid} — navigate menus/gameplay for {args.seconds}s")
    else:
        pid = device.spawn([str(get_exe_path())], cwd=str(get_game_dir()))
        session = device.attach(pid)
        print(f"Spawned pid={pid} — reach gameplay within {args.seconds}s")

    script = session.create_script(script_src)
    script.on("message", on_msg)
    script.load()
    if not args.attach:
        device.resume(pid)
    time.sleep(args.seconds)
    try:
        summary = script.exports_sync.summary()
    except Exception:
        summary = {"hits": [], "unique": 0}
    try:
        session.detach()
    except Exception:
        pass
    report = {
        "ok": True,
        "attach": args.attach,
        "seconds": args.seconds,
        **summary,
        "events": events,
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} hits={len(summary.get('hits', []))} unique={summary.get('unique', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
