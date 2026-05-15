"""
Log Save_Write rcx/edx and caller RVA for load vs save discrimination.

Usage:
  python RE_Tools/tools/scripts/frida_trace_save_mode.py --seconds 60

Output: RE_Tools/analysis/save_mode_trace.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
from paths import get_exe_path, get_game_dir  # noqa: E402

OUT = ROOT / "RE_Tools" / "analysis" / "save_mode_trace.json"
SAVE_RVA = 0x6DAB0
CALLERS = [0x9828C, 0x10A2C2, 0x10A822, 0xBED11]


def build_agent() -> str:
    callers_json = json.dumps(CALLERS)
    return f"""
'use strict';
var hits = [];
var horsey = Process.findModuleByName('Horsey.exe');
function rva(addr) {{
    var m = Process.findModuleByAddress(addr);
    if (m && m.name.toLowerCase() === 'horsey.exe')
        return '0x' + addr.sub(m.base).toString(16).toUpperCase();
    return addr.toString();
}}
function bt(ctx) {{
    return Thread.backtrace(ctx, Backtracer.ACCURATE).slice(0, 14).map(rva);
}}
Interceptor.attach(horsey.base.add({SAVE_RVA}), {{
    onEnter: function(args) {{
        hits.push({{
            rcx: args[0].toString(),
            edx: args[1].toInt32(),
            backtrace: bt(this.context)
        }});
        send({{ type: 'hit', edx: args[1].toInt32(), bt: bt(this.context) }});
    }}
}});
var callers = {callers_json};
callers.forEach(function(rva) {{
    Interceptor.attach(horsey.base.add(rva), {{
        onEnter: function() {{
            send({{ type: 'caller', rva: '0x' + rva.toString(16).toUpperCase() }});
        }}
    }});
}});
send({{ type: 'ready' }});
rpc.exports = {{ hits: function() {{ return hits; }} }};
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=60.0)
    args = ap.parse_args()
    import frida

    report = {"timestamp": datetime.now(timezone.utc).isoformat(), "hits": [], "callers": []}

    def on_message(message, _data):
        if message.get("type") != "send":
            return
        p = message["payload"]
        if p.get("type") == "hit":
            report["hits"].append(p)
        elif p.get("type") == "caller":
            report["callers"].append(p)

    device = frida.get_local_device()
    pid = device.spawn([str(get_exe_path())], cwd=str(get_game_dir()))
    session = device.attach(pid)
    script = session.create_script(build_agent())
    script.on("message", on_message)
    script.load()
    device.resume(pid)
    print(f"Tracing Save_Write mode for {args.seconds}s")
    time.sleep(args.seconds)
    try:
        report["hits_rpc"] = script.exports_sync.hits()
    except Exception:
        pass
    session.detach()
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} hits={len(report['hits'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
