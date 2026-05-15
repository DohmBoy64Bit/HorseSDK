"""
Frida: quit shutdown vs game save (Save_Write @ 0x6DAB0 vs Settings_Save @ 0x71F60).

Spawns Horsey.exe, waits for load, sets g_sdl_quit @ 0x318A50, captures hooks through shutdown.

Usage:
  python RE_Tools/tools/scripts/frida_quit_save_trace.py
  python RE_Tools/tools/scripts/frida_quit_save_trace.py --attach --load-wait 5 --quit-wait 8

Output: RE_Tools/analysis/frida_quit_save_trace.json
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

OUT = ROOT / "RE_Tools" / "analysis" / "frida_quit_save_trace.json"

SAVE_WRITE_RVA = 0x6DAB0
SETTINGS_SAVE_RVA = 0x71F60
SHUTDOWN_PREP_RVA = 0x98680
SHUTDOWN_ENTRY_RVA = 0xBED0C
SETTINGS_SAVE_CALL_RVA = 0xBED11
G_SDL_QUIT_RVA = 0x318A50
FILE_WRITE_RVA = 0x6F3C0

AGENT = r"""
'use strict';
var SAVE_WRITE = __SAVE_WRITE__;
var SETTINGS_SAVE = __SETTINGS_SAVE__;
var SHUTDOWN_PREP = __SHUTDOWN_PREP__;
var SHUTDOWN_ENTRY = __SHUTDOWN_ENTRY__;
var SETTINGS_SAVE_CALL = __SETTINGS_SAVE_CALL__;
var G_SDL_QUIT = __G_SDL_QUIT__;
var FILE_WRITE = __FILE_WRITE__;

var horsey = null;
var log = [];

function modRva(addr) {
    var m = Process.findModuleByAddress(addr);
    if (m && m.name.toLowerCase() === 'horsey.exe')
        return 'Horsey.exe+' + addr.sub(m.base).toString(16).toUpperCase();
    return addr.toString();
}

function bt(ctx, n) {
    return Thread.backtrace(ctx, Backtracer.ACCURATE).slice(0, n).map(modRva);
}

function push(tag, extra) {
    var row = { t: Date.now(), tag: tag };
    if (extra) {
        var k;
        for (k in extra) if (extra.hasOwnProperty(k)) row[k] = extra[k];
    }
    log.push(row);
    send({ type: 'event', row: row });
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

function hook(tag, rva, onEnter) {
    Interceptor.attach(horsey.base.add(rva), {
        onEnter: function (args) {
            var row = { backtrace: bt(this.context, 10) };
            if (onEnter) onEnter.call(this, args, row);
            push(tag, row);
        }
    });
}

function install() {
    horsey = Process.findModuleByName('Horsey.exe');
    if (!horsey) return false;
    push('info', { base: horsey.base.toString() });

    hook('Save_Write', SAVE_WRITE, function (args, row) {
        row.ctx = args[0].toString();
        row.edx = args[1].toInt32();
    });
    hook('Settings_Save', SETTINGS_SAVE, function (args, row) {
        row.rcx = args[0].toString();
    });
    hook('Shutdown_Prep_98680', SHUTDOWN_PREP);
    hook('Shutdown_Entry_BED0C', SHUTDOWN_ENTRY);
    hook('Settings_Save_CallSite_BED11', SETTINGS_SAVE_CALL);

    // Main loop quit test @ 0xBEA66 — observes when g_sdl_quit is consumed
    Interceptor.attach(horsey.base.add(0xBEA66), {
        onEnter: function () {
            var v = horsey.base.add(G_SDL_QUIT).readU8();
            if (v) push('Loop_QuitBranch_BEA66', { g_sdl_quit: v });
        }
    });

    Interceptor.attach(horsey.base.add(FILE_WRITE), {
        onEnter: function (args) {
            var frag = readMsvcString(args[1]);
            if (!frag) return;
            var low = frag.toLowerCase();
            if (low.indexOf('save') < 0 && low.indexOf('settings') < 0) return;
            push('FileWrite_path', {
                frag: frag,
                backtrace: bt(this.context, 8)
            });
        }
    });

    var wf = Module.findExportByName('kernel32.dll', 'WriteFile');
    if (wf) {
        Interceptor.attach(wf, {
            onEnter: function (args) {
                var n = args[2].toInt32();
                if (n < 32 || n > 500000) return;
                var btrace = bt(this.context, 8).join(' ');
                if (btrace.indexOf('6DAB0') < 0 && btrace.indexOf('6F3C0') < 0 &&
                    btrace.indexOf('71F60') < 0) return;
                push('WriteFile', { bytes: n, backtrace: bt(this.context, 8) });
            }
        });
    }

    return true;
}

rpc.exports = {
    forceQuit: function () {
        if (!horsey) return { ok: false };
        var p = horsey.base.add(G_SDL_QUIT);
        p.writeU8(1);
        push('forced_g_sdl_quit', { addr: p.toString() });
        return { ok: true, addr: p.toString() };
    },
    readQuitFlag: function () {
        if (!horsey) return null;
        return horsey.base.add(G_SDL_QUIT).readU8();
    },
    summary: function () { return { log: log }; }
};

if (Process.findModuleByName('Horsey.exe')) {
    install();
} else {
    var t = setInterval(function () {
        if (install()) clearInterval(t);
    }, 50);
}
"""


def build_agent() -> str:
    s = AGENT
    for name, val in [
        ("__SAVE_WRITE__", SAVE_WRITE_RVA),
        ("__SETTINGS_SAVE__", SETTINGS_SAVE_RVA),
        ("__SHUTDOWN_PREP__", SHUTDOWN_PREP_RVA),
        ("__SHUTDOWN_ENTRY__", SHUTDOWN_ENTRY_RVA),
        ("__SETTINGS_SAVE_CALL__", SETTINGS_SAVE_CALL_RVA),
        ("__G_SDL_QUIT__", G_SDL_QUIT_RVA),
        ("__FILE_WRITE__", FILE_WRITE_RVA),
    ]:
        s = s.replace(name, str(val))
    return s


def run(attach: bool, load_wait: float, quit_wait: float) -> dict:
    import frida

    device = frida.get_local_device()
    events: list = []

    def on_message(message, _data):
        if message.get("type") == "send":
            payload = message["payload"]
            events.append(payload)
            if payload.get("type") == "event":
                row = payload.get("row", {})
                print(f"  [{row.get('tag')}]", json.dumps(row)[:200])
        elif message.get("type") == "error":
            print("ERR:", message.get("stack", message))

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
        print(f"Spawned PID {pid}")

    time.sleep(load_wait)
    try:
        q0 = script.exports_sync.read_quit_flag()
        print(f"g_sdl_quit before force: {q0}")
        script.exports_sync.force_quit()
        print("Set g_sdl_quit = 1")
    except Exception as exc:
        print("force_quit failed:", exc)

    time.sleep(quit_wait)
    try:
        summary = script.exports_sync.summary()
    except Exception:
        summary = {"log": events}
    try:
        session.detach()
    except Exception:
        pass

    tags = [e.get("row", {}).get("tag") for e in events if e.get("type") == "event"]
    tag_set = set(tags)
    conclusion = {
        "save_write_on_quit": "Save_Write" in tag_set,
        "settings_save_on_quit": "Settings_Save" in tag_set or "Settings_Save_CallSite_BED11" in tag_set,
        "shutdown_prep": "Shutdown_Prep_98680" in tag_set,
        "shutdown_entry": "Shutdown_Entry_BED0C" in tag_set,
        "file_write_save_path": any(
            e.get("row", {}).get("tag") == "FileWrite_path"
            and "save" in (e.get("row", {}).get("frag") or "").lower()
            for e in events
            if e.get("type") == "event"
        ),
        "file_write_settings": any(
            "settings" in (e.get("row", {}).get("frag") or "").lower()
            for e in events
            if e.get("row", {}).get("tag") == "FileWrite_path"
        ),
    }
    return {
        "pid": pid,
        "load_wait_s": load_wait,
        "quit_wait_s": quit_wait,
        "conclusion": conclusion,
        "tag_counts": {t: tags.count(t) for t in sorted(tag_set)},
        "events": events,
        "summary_log": summary.get("log", []),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--attach", action="store_true")
    ap.add_argument("--load-wait", type=float, default=12.0)
    ap.add_argument("--quit-wait", type=float, default=10.0)
    args = ap.parse_args()
    try:
        report = run(args.attach, args.load_wait, args.quit_wait)
        report["ok"] = True
    except Exception as exc:
        report = {"ok": False, "error": str(exc)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}")
    if report.get("conclusion"):
        print("Conclusion:", json.dumps(report["conclusion"], indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
