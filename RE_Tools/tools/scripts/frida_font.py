"""
Frida: log CreateFileW / fopen when path contains .crf, .fnt, n64, or data\\

Usage:
  python RE_Tools/tools/scripts/frida_font.py --seconds 20

Output: RE_Tools/analysis/frida_font.json
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

OUT = ROOT / "RE_Tools" / "analysis" / "frida_font.json"

AGENT = r"""
'use strict';
const needles = ['.crf', '.fnt', 'n64', 'data\\\\', 'data/', 'quip', 'genes.dat'];
const paths = [];

function watchExport(moduleName, exportName, readPath) {
    const addr = Module.findExportByName(moduleName, exportName);
    if (!addr) return false;
    Interceptor.attach(addr, {
        onEnter(args) {
            try {
                const p = readPath(args);
                if (!p) return;
                const low = p.toLowerCase();
                for (let i = 0; i < needles.length; i++) {
                    if (low.indexOf(needles[i].toLowerCase()) >= 0) {
                        const bt = Thread.backtrace(this.context, Backtracer.ACCURATE)
                            .slice(0, 6)
                            .map(a => {
                                const m = Process.findModuleByAddress(a);
                                if (m && m.name.toLowerCase() === 'horsey.exe') {
                                    return '0x' + a.sub(m.base).toString(16).toUpperCase();
                                }
                                return a.toString();
                            });
                        const row = { api: exportName, path: p, backtrace: bt };
                        paths.push(row);
                        send({ type: 'path', row: row });
                        break;
                    }
                }
            } catch (e) {}
        }
    });
    return true;
}

rpc.exports = {
    init: function () {
        let n = 0;
        if (watchExport('kernel32.dll', 'CreateFileW', function (args) {
            return args[0].readUtf16String();
        })) n++;
        if (watchExport('ucrtbase.dll', '_wfopen', function (args) {
            return args[0].readUtf16String();
        })) n++;
        if (watchExport('ucrtbase.dll', 'fopen', function (args) {
            return args[0].readUtf8String();
        })) n++;
        return { hooks: n };
    },
    summary: function () { return paths; }
};
"""


def run(attach: bool, seconds: float) -> dict:
    import frida

    exe = str(get_exe_path())
    if attach:
        session = frida.get_local_device().attach("Horsey.exe")
    else:
        dev = frida.get_local_device()
        pid = dev.spawn([exe], cwd=str(get_game_dir()))
        session = dev.attach(pid)
        dev.resume(pid)
        time.sleep(3)

    events: list[dict] = []
    script = session.create_script(AGENT)

    def on_message(message, _data):
        if message.get("type") == "send":
            events.append(message["payload"])

    script.on("message", on_message)
    script.load()
    info = script.exports_sync.init()
    print(f"File hooks: {info['hooks']} — loading ({seconds}s)")
    time.sleep(seconds)
    summary = script.exports_sync.summary()
    session.detach()
    return {"hooks": info, "events": events, "paths": summary}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--attach", action="store_true")
    ap.add_argument("--seconds", type=float, default=20.0)
    args = ap.parse_args()
    try:
        report = run(args.attach, args.seconds)
    except Exception as exc:
        report = {"error": str(exc)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} ({len(report.get('paths', []))} paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
