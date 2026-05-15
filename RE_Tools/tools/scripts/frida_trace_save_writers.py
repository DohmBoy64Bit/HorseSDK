"""
Trace save serialization writers during Save_Write — logs file offset per write.

Hooks stream writers @ 0x6FE10..0x6FFF0 and cursor advance @ 0x70C70.
Only records while inside Save_Write @ 0x6DAB0.

Usage:
  python RE_Tools/tools/scripts/frida_trace_save_writers.py --seconds 50
  python RE_Tools/tools/scripts/frida_trace_save_writers.py --seconds 50 --max-events 8000

Output:
  RE_Tools/analysis/save_writer_trace.json
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

OUT = ROOT / "RE_Tools" / "analysis" / "save_writer_trace.json"

SAVE_RVA = 0x6DAB0
G_BUF_BASE = 0x310418
G_WRITE_PTR = 0x310410

ALL_WRITERS = [
    (0x6FE10, "WriteU32", 4),
    (0x6FE30, "WriteU8", 1),
    (0x6FEF0, "WriteU32FromU8", 4),
    (0x6FF10, "WriteF32", 4),
    (0x6FE50, "WriteU16", 2),
    (0x6FED0, "WriteU32", 4),
    (0x6FE70, "WriteU64", 8),
    (0x6FF30, "WriteVec2F32", 8),
    (0x6FEB0, "WriteU8", 1),
    (0x6FFF0, "WriteStdString", -1),
]
# Skip per-byte WriteU8 so one save fits in event budget (grid uses thousands of U8).
COMPACT_WRITERS = [
    (0x6FE10, "WriteU32", 4),
    (0x6FEF0, "WriteU32FromU8", 4),
    (0x6FF10, "WriteF32", 4),
    (0x6FE50, "WriteU16", 2),
    (0x6FED0, "WriteU32", 4),
    (0x6FE70, "WriteU64", 8),
    (0x6FF30, "WriteVec2F32", 8),
    (0x6FFF0, "WriteStdString", -1),
]

AGENT = r"""
'use strict';
var SAVE_RVA = __SAVE_RVA__;
var G_BUF_BASE = __G_BUF_BASE__;
var G_WRITE_PTR = __G_WRITE_PTR__;
var WRITERS = __WRITERS_JSON__;
var COMPACT = __COMPACT__;
var MAX_EVENTS = __MAX_EVENTS__;

var horsey = null;
var inSave = false;
var events = [];
var saveNum = 0;
var FIRST_SAVE_ONLY = __FIRST_SAVE_ONLY__;

function cursorOffset() {
    try {
        var base = horsey.base.add(G_BUF_BASE).readPointer();
        var cur = horsey.base.add(G_WRITE_PTR).readPointer();
        if (base.isNull() || cur.isNull()) return -1;
        return parseInt(cur.sub(base), 16);
    } catch (e) {
        return -1;
    }
}

function modRva(addr) {
    var m = Process.findModuleByAddress(addr);
    if (m && m.name.toLowerCase() === 'horsey.exe')
        return '0x' + addr.sub(m.base).toString(16).toUpperCase();
    return addr.toString();
}

function readPreview(off, size) {
    try {
        var base = horsey.base.add(G_BUF_BASE).readPointer();
        if (base.isNull() || off < 0) return '';
        var p = base.add(off);
        var n = Math.min(size, 16);
        var arr = new Uint8Array(p.readByteArray(n));
        var s = '';
        for (var i = 0; i < arr.length; i++)
            s += ('0' + arr[i].toString(16)).slice(-2);
        return s;
    } catch (e) { return ''; }
}

function hookWriter(rva, name, size) {
    Interceptor.attach(horsey.base.add(rva), {
        onEnter: function () {
            if (!inSave || events.length >= MAX_EVENTS) return;
            this.off = cursorOffset();
            this.name = name;
            this.size = size;
            this.rva = rva;
            if (rva === 0x6FFF0) {
                try {
                    var p = this.context.rcx;
                    var len = p.add(0x10).readU64();
                    this.strLen = len.toInt32();
                    this.size = 4 + this.strLen;
                } catch (e) {
                    this.strLen = -1;
                }
            } else {
                try {
                    if (rva === 0x6FE10 || rva === 0x6FED0)
                        this.u32 = this.context.ecx.toUInt32();
                    else if (rva === 0x6FEF0)
                        this.u32 = this.context.ecx.toUInt32() & 0xff;
                } catch (e1) {}
            }
        },
        onLeave: function () {
            if (!inSave || this.off === undefined || events.length >= MAX_EVENTS) return;
            var ev = {
                save: saveNum,
                writer: this.name,
                writer_rva: '0x' + this.rva.toString(16).toUpperCase(),
                file_offset: this.off,
                size: this.size,
                after_offset: cursorOffset(),
            };
            if (this.u32 !== undefined) ev.value_u32 = this.u32;
            if (this.strLen !== undefined) ev.str_len = this.strLen;
            ev.hex = readPreview(this.off, this.size > 0 ? this.size : 4);
            events.push(ev);
        }
    });
}

function install() {
    horsey = Process.findModuleByName('Horsey.exe');
    if (!horsey) return false;
    Interceptor.attach(horsey.base.add(SAVE_RVA), {
        onEnter: function () { inSave = true; },
        onLeave: function () {
            inSave = false;
            saveNum++;
            var total = events.length;
            var chunk = 1500;
            var i;
            for (i = 0; i < total; i += chunk) {
                send({ type: 'chunk', save: saveNum, start: i, events: events.slice(i, i + chunk) });
            }
            send({ type: 'save_done', save: saveNum, events: total, final_size: cursorOffset() });
            if (FIRST_SAVE_ONLY && saveNum >= 1) {
                Interceptor.detachAll();
            }
        }
    });
    var i;
    for (i = 0; i < WRITERS.length; i++) {
        hookWriter(WRITERS[i][0], WRITERS[i][1], WRITERS[i][2]);
    }
    send({ type: 'ready', base: horsey.base.toString() });
    return true;
}

if (Process.findModuleByName('Horsey.exe')) install();
else {
    var t = setInterval(function () { if (install()) clearInterval(t); }, 50);
}

rpc.exports = {
    getEvents: function () { return events; },
    getSaves: function () { return saveNum; }
};
"""


def build_agent(max_events: int, first_save_only: bool, compact: bool) -> str:
    writers = COMPACT_WRITERS if compact else ALL_WRITERS
    wjson = json.dumps(writers)
    return (
        AGENT.replace("__SAVE_RVA__", str(SAVE_RVA))
        .replace("__G_BUF_BASE__", str(G_BUF_BASE))
        .replace("__G_WRITE_PTR__", str(G_WRITE_PTR))
        .replace("__WRITERS_JSON__", wjson)
        .replace("__MAX_EVENTS__", str(max_events))
        .replace("__FIRST_SAVE_ONLY__", "true" if first_save_only else "false")
        .replace("__COMPACT__", "true" if compact else "false")
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=50.0)
    ap.add_argument("--max-events", type=int, default=25000)
    ap.add_argument("--all-saves", action="store_true", help="trace every Save_Write, not just first")
    ap.add_argument("--compact", action="store_true", default=True, help="omit WriteU8 hooks (default)")
    ap.add_argument("--full", action="store_true", help="include every WriteU8 (huge trace)")
    args = ap.parse_args()

    import frida

    compact = not args.full
    report: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "compact_mode": compact,
        "events": [],
        "save_completions": [],
    }

    def on_message(message, data):
        if message.get("type") != "send":
            if message.get("type") == "error":
                print("ERR:", str(message.get("stack", message))[:400])
            return
        p = message["payload"]
        t = p.get("type")
        if t == "ready":
            print("[ready]", p.get("base"))
        elif t == "chunk":
            report["events"].extend(p.get("events", []))
        elif t == "save_done":
            report["save_completions"].append(p)
            print(f"[save_done] #{p['save']} events={p['events']} collected={len(report['events'])} size={p['final_size']}")

    device = frida.get_local_device()
    pid = device.spawn([str(get_exe_path())], cwd=str(get_game_dir()))
    session = device.attach(pid)
    script = session.create_script(build_agent(args.max_events, not args.all_saves, compact))
    script.on("message", on_message)
    script.load()
    device.resume(pid)
    print(f"Tracing writers for {args.seconds}s (max {args.max_events} events)")
    time.sleep(args.seconds)
    session.detach()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} ({len(report['events'])} events)")
    return 0 if report["events"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
