"""
Frida Phase 1: catch startup save load + auto-save via Save_Write and file APIs.

Usage:
  python RE_Tools/tools/scripts/frida_phase1.py --seconds 60

Output: RE_Tools/analysis/frida_phase1.json
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

OUT = ROOT / "RE_Tools" / "analysis" / "frida_phase1.json"

SAVE_RVA = 0x6DAB0
FILE_APPEND_RVA = 0x6F3C0
SAVE_CALLERS = [0x9828C, 0x10A2C2, 0x10A822]

AGENT = r"""
'use strict';
var SAVE_RVA = __SAVE_RVA__;
var FILE_APPEND_RVA = __FILE_APPEND_RVA__;
var SAVE_CALLERS = __SAVE_CALLERS__;

var horsey = null;
var saveHits = [];
var fileAppendHits = [];
var ioPaths = [];
var readFileHits = [];

function modRva(addr) {
    var m = Process.findModuleByAddress(addr);
    if (m && m.name.toLowerCase() === 'horsey.exe')
        return 'Horsey.exe+' + addr.sub(m.base).toString(16).toUpperCase();
    return addr.toString();
}

function backtrace(ctx, n) {
    return Thread.backtrace(ctx, Backtracer.ACCURATE).slice(0, n).map(modRva);
}

function pathInteresting(p) {
    if (!p) return false;
    var low = p.toLowerCase();
    return low.indexOf('.crf') >= 0 || low.indexOf('.fnt') >= 0 ||
        low.indexOf('.dat') >= 0 || low.indexOf('save') >= 0 ||
        low.indexOf('n64') >= 0 || low.indexOf('quip') >= 0 ||
        low.indexOf('data') >= 0 || low.indexOf('settings') >= 0;
}

function readMsvcString(ptr) {
    try {
        if (ptr.isNull()) return null;
        var size = ptr.add(0x10).readU64();
        var cap = ptr.add(0x18).readU64();
        if (cap <= 15) return ptr.readUtf8String(Number(size));
        return ptr.readPointer().readUtf8String(Number(size));
    } catch (e) { return null; }
}

function exportAddr(moduleName, exportName) {
    try {
        return Module.getExportByName(moduleName, exportName);
    } catch (e1) {
        try {
            return Module.findExportByName(moduleName, exportName);
        } catch (e2) {
            return null;
        }
    }
}

function hookSave() {
    Interceptor.attach(horsey.base.add(SAVE_RVA), {
        onEnter: function (args) {
            var hit = {
                ctx: args[0].toString(),
                edx: args[1].toInt32(),
                backtrace: backtrace(this.context, 12),
            };
            saveHits.push(hit);
            send({ type: 'save', hit: hit });
        },
        onLeave: function (ret) {
            if (saveHits.length)
                saveHits[saveHits.length - 1].retval = ret.toInt32();
        }
    });
    var i;
    for (i = 0; i < SAVE_CALLERS.length; i++) {
        (function (rva) {
            Interceptor.attach(horsey.base.add(rva), {
                onEnter: function () {
                    send({ type: 'save_caller', rva: '0x' + rva.toString(16).toUpperCase(),
                        backtrace: backtrace(this.context, 8) });
                }
            });
        })(SAVE_CALLERS[i]);
    }
}

function hookFileAppend() {
    Interceptor.attach(horsey.base.add(FILE_APPEND_RVA), {
        onEnter: function (args) {
            var bt = backtrace(this.context, 6);
            var fromSave = false;
            var j;
            for (j = 0; j < bt.length; j++) {
                if (bt[j].indexOf('6DAB0') >= 0 || bt[j].indexOf('6DB95') >= 0) {
                    fromSave = true;
                    break;
                }
            }
            var frag = readMsvcString(args[1]);
            var hit = { frag: frag, from_save_chain: fromSave, backtrace: bt };
            fileAppendHits.push(hit);
            if (fromSave || pathInteresting(frag))
                send({ type: 'file_append', hit: hit });
        }
    });
}

function hookCreateFileWide() {
    var addr = exportAddr('kernel32.dll', 'CreateFileW');
    if (!addr) return;
    Interceptor.attach(addr, {
        onEnter: function (args) {
            try {
                var p = args[0].readUtf16String();
                if (!pathInteresting(p)) return;
                var row = { api: 'CreateFileW', path: p, backtrace: backtrace(this.context, 10) };
                ioPaths.push(row);
                send({ type: 'io', row: row });
            } catch (e) {}
        }
    });
}

function hookCreateFileA() {
    var addr = exportAddr('kernel32.dll', 'CreateFileA');
    if (!addr) return;
    Interceptor.attach(addr, {
        onEnter: function (args) {
            try {
                var p = args[0].readUtf8String();
                if (!pathInteresting(p)) return;
                var row = { api: 'CreateFileA', path: p, backtrace: backtrace(this.context, 10) };
                ioPaths.push(row);
                send({ type: 'io', row: row });
            } catch (e) {}
        }
    });
}

function hookFopen() {
    var addr = exportAddr('ucrtbase.dll', 'fopen');
    if (!addr) addr = exportAddr('msvcrt.dll', 'fopen');
    if (!addr) return;
    Interceptor.attach(addr, {
        onEnter: function (args) {
            try {
                var p = args[0].readUtf8String();
                if (!pathInteresting(p)) return;
                var row = { api: 'fopen', path: p, backtrace: backtrace(this.context, 10) };
                ioPaths.push(row);
                send({ type: 'io', row: row });
            } catch (e) {}
        }
    });
}

function hookReadFile() {
    var addr = exportAddr('kernel32.dll', 'ReadFile');
    if (!addr) return;
    Interceptor.attach(addr, {
        onEnter: function (args) {
            var n = args[2].toInt32();
            var bt = backtrace(this.context, 8);
            var joined = bt.join(' ');
            if (joined.indexOf('Horsey.exe') < 0) return;
            var row = { api: 'ReadFile', bytes: n, backtrace: bt };
            readFileHits.push(row);
            if (n >= 12 && n <= 500000) {
                try {
                    var bytes = new Uint8Array(args[1].readByteArray(Math.min(n, 32)));
                    var hex = '';
                    var k;
                    for (k = 0; k < bytes.length; k++)
                        hex += ('0' + bytes[k].toString(16)).slice(-2);
                    row.header_hex = hex;
                    if (hex.indexOf('0c000000') === 0)
                        send({ type: 'read_save', row: row });
                } catch (e2) {}
            }
        }
    });
}

function hookWriteFile() {
    var addr = exportAddr('kernel32.dll', 'WriteFile');
    if (!addr) return;
    Interceptor.attach(addr, {
        onEnter: function (args) {
            var n = args[2].toInt32();
            if (n < 64 || n > 500000) return;
            var bt = backtrace(this.context, 8);
            if (bt.join(' ').indexOf('Horsey.exe') < 0) return;
            try {
                var bytes = new Uint8Array(args[1].readByteArray(Math.min(n, 32)));
                var hex = '';
                var k;
                for (k = 0; k < bytes.length; k++)
                    hex += ('0' + bytes[k].toString(16)).slice(-2);
                if (hex.indexOf('0c000000') === 0)
                    send({ type: 'write_save', row: { bytes: n, header_hex: hex, backtrace: bt } });
            } catch (e) {}
        }
    });
}

function install() {
    horsey = Process.findModuleByName('Horsey.exe');
    if (!horsey) return false;
    send({ type: 'info', msg: 'base=' + horsey.base });
    hookSave();
    hookFileAppend();
    hookCreateFileWide();
    hookCreateFileA();
    hookFopen();
    hookReadFile();
    hookWriteFile();
    send({ type: 'ready' });
    return true;
}

if (Process.findModuleByName('Horsey.exe')) {
    install();
} else {
    var timer = setInterval(function () {
        if (install()) clearInterval(timer);
    }, 50);
}

rpc.exports = {
    summary: function () {
        return {
            saveHits: saveHits,
            fileAppendHits: fileAppendHits,
            ioPaths: ioPaths,
            readFileHits: readFileHits,
        };
    }
};
"""


def build_agent() -> str:
    return (
        AGENT.replace("__SAVE_RVA__", str(SAVE_RVA))
        .replace("__FILE_APPEND_RVA__", str(FILE_APPEND_RVA))
        .replace("__SAVE_CALLERS__", json.dumps(SAVE_CALLERS))
    )


def run(attach: bool, seconds: float) -> dict:
    import frida

    device = frida.get_local_device()
    events: list = []
    collected = {
        "saveHits": [],
        "fileAppendHits": [],
        "ioPaths": [],
        "readFileHits": [],
    }

    def on_message(message, _data):
        if message.get("type") == "send":
            payload = message["payload"]
            events.append(payload)
            t = payload.get("type")
            if t == "save":
                collected["saveHits"].append(payload.get("hit"))
            elif t == "file_append":
                collected["fileAppendHits"].append(payload.get("hit"))
            elif t == "io":
                collected["ioPaths"].append(payload.get("row"))
            elif t in ("read_save", "write_save"):
                collected["readFileHits"].append(payload.get("row"))
            print(f"[{t}]", json.dumps(payload)[:260])
        elif message.get("type") == "error":
            print("SCRIPT ERROR:", message.get("stack", message))

    if attach:
        session = device.attach("Horsey.exe")
        pid = None
    else:
        pid = device.spawn([str(get_exe_path())], cwd=str(get_game_dir()))
        session = device.attach(pid)

    script = session.create_script(build_agent())
    script.on("message", on_message)
    script.load()
    if not attach:
        device.resume(pid)
        print(f"Spawned PID {pid}, hooks active…")
    else:
        print("Attached to Horsey.exe")

    time.sleep(seconds)
    try:
        session.detach()
    except Exception:
        pass
    return {"pid": pid, "events": events, **collected}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--attach", action="store_true")
    ap.add_argument("--seconds", type=float, default=60.0)
    args = ap.parse_args()
    try:
        report = run(args.attach, args.seconds)
        report["ok"] = True
    except Exception as exc:
        report = {"ok": False, "error": str(exc)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    print(
        f"  save={len(report.get('saveHits', []))} "
        f"io={len(report.get('ioPaths', []))} "
        f"read={len(report.get('readFileHits', []))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
