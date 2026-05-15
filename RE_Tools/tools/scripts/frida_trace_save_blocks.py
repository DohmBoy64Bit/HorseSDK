"""
Trace save sub-block boundaries (grid end, pairs, nested) during Save_Write.

Hooks (Horsey.exe RVAs):
  0x6DF18  — log grid cell count (width*height) + cursor
  0x6E043  — pair-vector count write
  0x6D440  — WriteNestedSave enter/leave (byte delta)
  0x6EC40  — nested inventory element enter/leave

Usage:
  python RE_Tools/tools/scripts/frida_trace_save_blocks.py --seconds 45

Output:
  RE_Tools/analysis/save_block_trace.json
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

OUT = ROOT / "RE_Tools" / "analysis" / "save_block_trace.json"

SAVE_RVA = 0x6DAB0
AUTO_SAVE_CALLER = 0x10A822  # periodic save — same Save_Write path
G_BUF_BASE = 0x310418
G_WRITE_PTR = 0x310410

AGENT = r"""
'use strict';
var SAVE_RVA = __SAVE_RVA__;
var G_BUF_BASE = __G_BUF_BASE__;
var G_WRITE_PTR = __G_WRITE_PTR__;
var MAX_EVENTS = __MAX_EVENTS__;

var horsey = null;
var inSave = false;
var events = [];
var saveNum = 0;
var depth = 0;

function cursorOffset() {
    try {
        var base = horsey.base.add(G_BUF_BASE).readPointer();
        var cur = horsey.base.add(G_WRITE_PTR).readPointer();
        if (base.isNull() || cur.isNull()) return -1;
        return parseInt(cur.sub(base), 16);
    } catch (e) { return -1; }
}

function push(ev) {
    if (events.length >= MAX_EVENTS) return;
    ev.save = saveNum;
    ev.depth = depth;
    events.push(ev);
}

function hookEnterLeave(rva, name, readCtx) {
    Interceptor.attach(horsey.base.add(rva), {
        onEnter: function (args) {
            if (!inSave) return;
            this.name = name;
            this.off0 = cursorOffset();
            this.extra = {};
            if (readCtx) {
                try { readCtx(this, this.context); } catch (e1) {}
            }
        },
        onLeave: function (ret) {
            if (!inSave || this.off0 === undefined) return;
            var off1 = cursorOffset();
            push({
                kind: 'block',
                block: this.name,
                rva: '0x' + rva.toString(16).toUpperCase(),
                file_offset: this.off0,
                after_offset: off1,
                bytes: off1 >= 0 && this.off0 >= 0 ? (off1 - this.off0) : -1,
                extra: this.extra
            });
        }
    });
}

function install() {
    horsey = Process.findModuleByName('Horsey.exe');
    if (!horsey) return false;

    Interceptor.attach(horsey.base.add(SAVE_RVA), {
        onEnter: function () { inSave = true; depth = 0; },
        onLeave: function () {
            inSave = false;
            saveNum++;
            var total = events.length;
            var chunk = 800;
            var i;
            for (i = 0; i < total; i += chunk) {
                send({ type: 'chunk', save: saveNum, start: i, events: events.slice(i, i + chunk) });
            }
            send({ type: 'save_done', save: saveNum, events: total, final_size: cursorOffset() });
        }
    });

    function hookNestedCall(rva, label) {
        Interceptor.attach(horsey.base.add(rva), {
            onEnter: function () {
                if (!inSave) return;
                push({
                    kind: 'nested_call',
                    rva: '0x' + rva.toString(16).toUpperCase(),
                    label: label,
                    file_offset: cursorOffset(),
                    obj: this.context.rcx.toString()
                });
            }
        });
    }
    hookNestedCall(0x6E0A6, 'Save_Write_main_nested');
    hookNestedCall(0x6E0D6, 'Save_Write_inventory_nested');
    hookNestedCall(0x6E103, 'Save_Write_global_nested');

    // imul eax,[rbx] @ 0x6DF18 — eax = height*width after insn
    Interceptor.attach(horsey.base.add(0x6DF18), {
        onLeave: function () {
            if (!inSave) return;
            var cells = 0;
            try { cells = this.context.rax.toUInt32(); } catch (e0) {}
            push({
                kind: 'grid_dims',
                rva: '0x6DF18',
                file_offset: cursorOffset(),
                cell_count: cells,
                note: 'eax = [0x27C]*[0x278] before grid loop'
            });
        }
    });

    // WriteU32 count for pair vector @ 0x6E043
    Interceptor.attach(horsey.base.add(0x6E043), {
        onEnter: function () {
            if (!inSave) return;
            var n = 0;
            try { n = this.context.rcx.toUInt32(); } catch (e1) {}
            push({
                kind: 'pair_count',
                rva: '0x6E043',
                file_offset: cursorOffset(),
                pair_count: n
            });
        }
    });

    hookEnterLeave(0x6D440, 'WriteNestedSave', function (st, ctx) {
        st.extra.obj = ctx.rcx.toString();
    });

    Interceptor.attach(horsey.base.add(0x6EC40), {
        onEnter: function (args) {
            if (!inSave) return;
            this.name = 'WriteNestedItem';
            this.off0 = cursorOffset();
            this.obj = args[0].toString();
            depth++;
        },
        onLeave: function () {
            if (!inSave || this.off0 === undefined) return;
            if (depth > 0) depth--;
            var off1 = cursorOffset();
            push({
                kind: 'block',
                block: this.name,
                rva: '0x6EC40',
                file_offset: this.off0,
                after_offset: off1,
                bytes: off1 >= 0 && this.off0 >= 0 ? (off1 - this.off0) : -1,
                extra: { obj: this.obj }
            });
        }
    });

    Interceptor.attach(horsey.base.add(__AUTO_SAVE__), {
        onEnter: function () {
            push({ kind: 'autosave_hit', rva: '0x10A822' });
        }
    });

    send({ type: 'ready', base: horsey.base.toString() });
    return true;
}

if (Process.findModuleByName('Horsey.exe')) install();
else {
    var t = setInterval(function () { if (install()) clearInterval(t); }, 50);
}

rpc.exports = {
    getEvents: function () { return events; }
};
"""


def build_agent(max_events: int) -> str:
    return (
        AGENT.replace("__SAVE_RVA__", str(SAVE_RVA))
        .replace("__G_BUF_BASE__", str(G_BUF_BASE))
        .replace("__G_WRITE_PTR__", str(G_WRITE_PTR))
        .replace("__MAX_EVENTS__", str(max_events))
        .replace("__AUTO_SAVE__", str(AUTO_SAVE_CALLER))
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=45.0)
    ap.add_argument("--max-events", type=int, default=5000)
    args = ap.parse_args()

    import frida

    report: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "events": [],
        "save_completions": [],
    }

    def on_message(message, _data):
        if message.get("type") != "send":
            if message.get("type") == "error":
                print("ERR:", str(message.get("stack", message))[:400])
            return
        p = message["payload"]
        if p.get("type") == "ready":
            print("[ready]", p.get("base"))
        elif p.get("type") == "chunk":
            report["events"].extend(p.get("events", []))
        elif p.get("type") == "save_done":
            report["save_completions"].append(p)
            print(f"[save_done] events={p['events']} final_size={p['final_size']}")

    device = frida.get_local_device()
    pid = device.spawn([str(get_exe_path())], cwd=str(get_game_dir()))
    session = device.attach(pid)
    script = session.create_script(build_agent(args.max_events))
    script.on("message", on_message)
    script.load()
    device.resume(pid)
    print(f"Tracing save blocks for {args.seconds}s — trigger a save in-game")
    time.sleep(args.seconds)
    if not report["events"]:
        try:
            report["events"] = script.exports_sync.get_events()
        except Exception:
            pass
    session.detach()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} ({len(report['events'])} events)")
    return 0 if report["events"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
