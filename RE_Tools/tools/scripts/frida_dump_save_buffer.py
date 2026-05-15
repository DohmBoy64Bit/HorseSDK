"""
Dump in-memory save serialization buffer when Save_Write @ 0x6DAB0 completes.

The game builds save data into a growable heap buffer (not one WriteFile blob):
  - StreamOpen @ 0x6FD40 (reserve ~0x3d090 bytes)
  - WriteU32/U8/F32 @ 0x6FE10 / 0x6FEF0 / 0x6FF10 → advance @ 0x70C70
  - Globals (RVA, add to Horsey.exe module base):
      0x310408  dword buffer start offset
      0x310410  dword end offset / qword write cursor (same slot; use GetSize)
      0x310418  qword buffer base pointer (after StreamOpen)

Usage:
  python RE_Tools/tools/scripts/frida_dump_save_buffer.py
  python RE_Tools/tools/scripts/frida_dump_save_buffer.py --seconds 45 --max-dumps 3

Output:
  RE_Tools/analysis/save_buffer_dump.bin
  RE_Tools/analysis/save_buffer_dump.json
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
from paths import get_data_dir, get_exe_path, get_game_dir, get_save_dir  # noqa: E402

OUT_BIN = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.bin"
OUT_JSON = ROOT / "RE_Tools" / "analysis" / "save_buffer_dump.json"

SAVE_RVA = 0x6DAB0
GET_SIZE_RVA = 0x6FDF0
STREAM_OPEN_RVA = 0x6FD40
G_START = 0x310408
G_END = 0x310410
G_WRITE_PTR = 0x310410
G_BUF_BASE = 0x310418
G_BUF_END = 0x310420

AGENT = r"""
'use strict';
var SAVE_RVA = __SAVE_RVA__;
var GET_SIZE_RVA = __GET_SIZE_RVA__;
var STREAM_OPEN_RVA = __STREAM_OPEN_RVA__;
var G_START = __G_START__;
var G_END = __G_END__;
var G_WRITE_PTR = __G_WRITE_PTR__;
var G_BUF_BASE = __G_BUF_BASE__;
var G_BUF_END = __G_BUF_END__;
var MAX_DUMPS = __MAX_DUMPS__;

var horsey = null;
var dumps = [];
var inSave = false;
var streamBaseAtOpen = ptr(0);

function modRva(addr) {
    var m = Process.findModuleByAddress(addr);
    if (m && m.name.toLowerCase() === 'horsey.exe')
        return 'Horsey.exe+' + addr.sub(m.base).toString(16).toUpperCase();
    return addr.toString();
}

function backtrace(ctx, n) {
    return Thread.backtrace(ctx, Backtracer.ACCURATE).slice(0, n).map(modRva);
}

function hexBytes(ptr, len) {
    var n = Math.min(len, 256);
    try {
        var arr = new Uint8Array(ptr.readByteArray(n));
        var s = '';
        for (var i = 0; i < arr.length; i++)
            s += ('0' + arr[i].toString(16)).slice(-2);
        return s;
    } catch (e) {
        return '';
    }
}

function tryDump(label) {
    if (dumps.length >= MAX_DUMPS) return;
    var writePtr = horsey.base.add(G_WRITE_PTR).readPointer();
    var bufBase = horsey.base.add(G_BUF_BASE).readPointer();
    var bufEnd = horsey.base.add(G_BUF_END).readPointer();
    var startOff = horsey.base.add(G_START).readU32();
    var endOff = horsey.base.add(G_END).readU32();

    var base = bufBase;
    var size = 0;
    if (!writePtr.isNull() && !bufBase.isNull()) {
        var diff = writePtr.sub(bufBase);
        var n = diff.toInt32();
        if (n > 0 && n < 5000000) size = n;
    }
    if (size === 0 && endOff > startOff && endOff - startOff < 5000000)
        size = endOff - startOff;
    if (base.isNull() && !writePtr.isNull() && size > 0)
        base = writePtr.sub(size);

    if (size <= 0 || size > 5000000 || base.isNull()) {
        send({
            type: 'dump_fail',
            label: label,
            startOff: startOff,
            endOff: endOff,
            writePtr: writePtr.toString(),
            bufBase: bufBase.toString(),
            bufEnd: bufEnd.toString(),
        });
        return;
    }

    var data = base.readByteArray(size);
    var entry = {
        label: label,
        size: size,
        startOff: startOff,
        endOff: endOff,
        base: base.toString(),
        writePtr: writePtr.toString(),
        bufBase: bufBase.toString(),
        header_hex: hexBytes(base, 64),
        backtrace: inSave ? [] : backtrace(this.context, 8),
    };
    dumps.push(entry);
    send({ type: 'dump_ok', entry: entry }, data);
}

function hookSave() {
    Interceptor.attach(horsey.base.add(SAVE_RVA), {
        onEnter: function () {
            inSave = true;
        },
        onLeave: function () {
            tryDump.call(this, 'Save_Write_leave');
            inSave = false;
        }
    });
}

function hookGetSize() {
    Interceptor.attach(horsey.base.add(GET_SIZE_RVA), {
        onLeave: function (ret) {
            if (!inSave) return;
            var bt = backtrace(this.context, 6).join(' ');
            if (bt.indexOf('6DAB0') < 0 && bt.indexOf('6DC') < 0) return;
            send({ type: 'get_size', eax: ret.toInt32() >>> 0 });
        }
    });
}

function hookStreamOpen() {
    Interceptor.attach(horsey.base.add(STREAM_OPEN_RVA), {
        onEnter: function (args) {
            if (!inSave) return;
            try {
                this.reserve = this.context.rcx.toInt32();
            } catch (e) {
                this.reserve = 0;
            }
        },
        onLeave: function () {
            if (!inSave) return;
            streamBaseAtOpen = horsey.base.add(G_BUF_BASE).readPointer();
            send({
                type: 'stream_open',
                reserve: this.reserve,
                bufBase: streamBaseAtOpen.toString(),
            });
        }
    });
}

function install() {
    horsey = Process.findModuleByName('Horsey.exe');
    if (!horsey) return false;
    send({ type: 'info', base: horsey.base.toString() });
    hookSave();
    hookGetSize();
    hookStreamOpen();
    send({ type: 'ready' });
    return true;
}

if (Process.findModuleByName('Horsey.exe')) {
    install();
} else {
    var t = setInterval(function () {
        if (install()) clearInterval(t);
    }, 50);
}

rpc.exports = {
    summary: function () { return { dumps: dumps }; }
};
"""


def build_agent(max_dumps: int) -> str:
    return (
        AGENT.replace("__SAVE_RVA__", str(SAVE_RVA))
        .replace("__GET_SIZE_RVA__", str(GET_SIZE_RVA))
        .replace("__STREAM_OPEN_RVA__", str(STREAM_OPEN_RVA))
        .replace("__G_START__", str(G_START))
        .replace("__G_END__", str(G_END))
        .replace("__G_WRITE_PTR__", str(G_WRITE_PTR))
        .replace("__G_BUF_BASE__", str(G_BUF_BASE))
        .replace("__G_BUF_END__", str(G_BUF_END))
        .replace("__MAX_DUMPS__", str(max_dumps))
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=50.0)
    ap.add_argument("--max-dumps", type=int, default=5)
    ap.add_argument("--attach", action="store_true")
    args = ap.parse_args()

    import frida

    report: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "globals_rva": {
            "G_START": hex(G_START),
            "G_END": hex(G_END),
            "G_WRITE_PTR": hex(G_WRITE_PTR),
            "G_BUF_BASE": hex(G_BUF_BASE),
        },
        "save_rva": hex(SAVE_RVA),
        "on_disk_reference": str(get_save_dir() / "save1.dat"),
        "dumps": [],
        "events": [],
    }
    last_bin: bytes | None = None

    def on_message(message, data):
        if message.get("type") != "send":
            if message.get("type") == "error":
                print("ERR:", message.get("stack", message)[:500])
            return
        payload = message["payload"]
        report["events"].append(
            {k: v for k, v in payload.items() if k != "entry"} if isinstance(payload, dict) else payload
        )
        t = payload.get("type")
        if t == "dump_ok" and data:
            entry = payload["entry"]
            report["dumps"].append(entry)
            nonlocal last_bin
            last_bin = bytes(data)
            print(f"[dump] {entry['label']} size={entry['size']} hdr={entry['header_hex'][:32]}...")
        elif t == "dump_fail":
            print("[dump_fail]", payload)
        elif t in ("info", "ready", "stream_open", "get_size"):
            print(f"[{t}]", json.dumps(payload)[:200])

    device = frida.get_local_device()
    if args.attach:
        session = device.attach("Horsey.exe")
        print(f"Attached — waiting for save dumps ({args.seconds}s)")
    else:
        pid = device.spawn([str(get_exe_path())], cwd=str(get_game_dir()))
        session = device.attach(pid)
        device.resume(pid)
        print(f"Spawned PID {pid} — waiting for startup/auto-save dumps ({args.seconds}s)")

    script = session.create_script(build_agent(args.max_dumps))
    script.on("message", on_message)
    script.load()
    time.sleep(args.seconds)
    try:
        report["summary"] = script.exports_sync.summary()
    except Exception:
        pass
    session.detach()

    if last_bin:
        OUT_BIN.write_bytes(last_bin)
        print(f"Wrote {OUT_BIN} ({len(last_bin)} bytes)")
        on_disk = get_save_dir() / "save1.dat"
        if on_disk.is_file():
            disk = on_disk.read_bytes()
            report["compare_on_disk"] = {
                "disk_size": len(disk),
                "dump_size": len(last_bin),
                "headers_match": disk[:32] == last_bin[:32],
                "disk_header_hex": disk[:64].hex(),
            }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_JSON}")
    return 0 if report["dumps"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
