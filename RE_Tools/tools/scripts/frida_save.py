"""
Frida: hook Save_Write @ 0x6DAB0 and log return addresses + first args.

Usage:
  python RE_Tools/tools/scripts/frida_save.py --seconds 30
  python RE_Tools/tools/scripts/frida_save.py --attach --seconds 60

Output: RE_Tools/analysis/frida_save.json
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

OUT = ROOT / "RE_Tools" / "analysis" / "frida_save.json"
SAVE_RVA = 0x6DAB0
CALLERS = [0x9828C, 0x10A2C2, 0x10A822]

AGENT = r"""
'use strict';
const SAVE_RVA = %(save_rva)d;
const CALLERS = %(callers)s;
let horsey = null;
const hits = [];

function rva(addr) {
    if (!horsey || addr.isNull()) return null;
    const o = addr.sub(horsey.base);
    return '0x' + o.toString(16).toUpperCase();
}

function hookSave() {
    const p = horsey.base.add(SAVE_RVA);
    Interceptor.attach(p, {
        onEnter(args) {
            const bt = Thread.backtrace(this.context, Backtracer.ACCURATE)
                .slice(0, 8)
                .map(rva);
            hits.push({
                when: 'enter',
                rcx: args[0].toString(),
                rdx: args[1].toString(),
                r8: args[2].toString(),
                backtrace_rva: bt,
            });
            send({ type: 'save_hit', hit: hits[hits.length - 1] });
        },
        onLeave(ret) {
            hits[hits.length - 1].retval = ret.toString();
        }
    });
}

function hookCallers() {
    CALLERS.forEach(function (rva) {
        Interceptor.attach(horsey.base.add(rva), {
            onEnter() {
                send({ type: 'caller', rva: '0x' + rva.toString(16).toUpperCase() });
            }
        });
    });
}

rpc.exports = {
    init: function () {
        horsey = Process.enumerateModules().find(m => m.name.toLowerCase() === 'horsey.exe');
        if (!horsey) throw new Error('Horsey.exe not loaded');
        hookSave();
        hookCallers();
        return { base: horsey.base.toString() };
    },
    summary: function () { return hits; }
};
"""


def run(attach: bool, seconds: float) -> dict:
    import frida

    exe = str(get_exe_path())
    hooks = {"save_rva": SAVE_RVA, "callers": CALLERS}
    script_src = AGENT % hooks

    if attach:
        device = frida.get_local_device()
        session = device.attach("Horsey.exe")
    else:
        device = frida.get_local_device()
        pid = device.spawn([exe], cwd=str(get_game_dir()))
        session = device.attach(pid)
        device.resume(pid)
        time.sleep(2)

    script = session.create_script(script_src)
    events: list[dict] = []

    def on_message(message, _data):
        if message.get("type") == "send":
            events.append(message["payload"])

    script.on("message", on_message)
    script.load()
    info = script.exports_sync.init()
    print(f"Attached base {info['base']} — trigger a save in-game ({seconds}s)")
    time.sleep(seconds)
    summary = script.exports_sync.summary()
    session.detach()
    return {"base": info["base"], "events": events, "hits": summary}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--attach", action="store_true")
    ap.add_argument("--seconds", type=float, default=25.0)
    args = ap.parse_args()
    try:
        report = run(args.attach, args.seconds)
    except Exception as exc:
        report = {"error": str(exc), "hint": "Launch game first or run without --attach"}
    report["save_rva"] = hex(SAVE_RVA)
    report["callers"] = [hex(c) for c in CALLERS]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} ({len(report.get('hits', []))} save hits)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
