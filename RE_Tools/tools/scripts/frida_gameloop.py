"""
Frida Phase 1: map main game loop inside RVA 0xBE0F0 (init + per-frame body).

Hooks SDL exports + in-loop call sites found by static PE scan on Game/Horsey.exe.
Builds a per-frame event timeline (frame = one SDL_GL_SwapWindow).

Usage:
  python RE_Tools/tools/scripts/frida_gameloop.py
  python RE_Tools/tools/scripts/frida_gameloop.py --attach --seconds 12 --frames 5
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

# Static PE scan (Game/Horsey.exe, May 2026)
HOOKS = {
    "main_game_entry": 0xBE0F0,
    "steam_run_callbacks": 0xBEA7F,
    "sdl_poll_call_a": 0xBEA8A,
    "sdl_poll_call_b": 0xBEAA5,
    "sdl_swap_call": 0xBEAF0,
    "loop_internal_call": 0xBEDB4,  # calls 0xBEEA0
    "sdl_swap_alt": 0xC019E,
}
EXPORTS = {
    "SDL_PollEvent": 0x1253B0,
    "SDL_GL_SwapWindow": 0x1238D0,
}

AGENT = r"""
'use strict';

const HOOKS = %(hooks_json)s;
const EXPORTS = %(exports_json)s;
const MAX_FRAMES = %(max_frames)d;
const LOG_EXPORTS = %(log_exports)s;

let horsey = null;
let frame = 0;
let seq = [];
let mainEntered = false;

function rva(addr) {
    if (!horsey || addr.isNull()) return null;
    const o = addr.sub(horsey.base);
    if (o.compare(0) < 0 || o.compare(horsey.size) >= 0) return null;
    return '0x' + o.toString(16).toUpperCase();
}

function logEvent(tag, extra) {
    if (frame >= MAX_FRAMES && tag !== 'main_game_entry') return;
    const e = { frame: frame, tag: tag };
    if (extra) {
        for (const k in extra) e[k] = extra[k];
    }
    seq.push(e);
    if (tag === 'SDL_GL_SwapWindow') {
        send({ type: 'frame_done', frame: frame, events: seq.slice() });
        frame++;
        seq = [];
        if (frame >= MAX_FRAMES) {
            send({ type: 'done', frames: frame });
        }
    }
}

function hookRva(rva, tag, maxHits) {
    const p = horsey.base.add(rva);
    let n = 0;
    Interceptor.attach(p, {
        onEnter() {
            n++;
            if (frame >= MAX_FRAMES && tag !== 'main_game_entry') return;
            if (maxHits > 0 && n > maxHits) return;
            const extra = { n: n, hookRva: '0x' + rva.toString(16) };
            if (tag === 'main_game_entry' && !mainEntered) {
                mainEntered = true;
                extra.returnRva = rva_addr(this.returnAddress);
                extra.frames = backtrace(this.context, 6);
            }
            if (tag === 'SDL_GL_SwapWindow' || tag === 'sdl_swap_call') {
                extra.returnRva = rva_addr(this.returnAddress);
            }
            logEvent(tag, extra);
        }
    });
}

function rva_addr(addr) { return rva(addr); }

function modOff(addr) {
    const m = Process.findModuleByAddress(addr);
    if (!m) return addr.toString();
    return m.name + '+0x' + addr.sub(m.base).toString(16).toUpperCase();
}

function backtrace(ctx, lim) {
    return Thread.backtrace(ctx, Backtracer.ACCURATE).slice(0, lim).map(modOff);
}

function install() {
    horsey = Process.findModuleByName('Horsey.exe');
    if (!horsey) {
        send({ type: 'error', msg: 'Horsey.exe not loaded' });
        return false;
    }
    send({ type: 'info', msg: 'base=' + horsey.base });

    for (const tag in HOOKS) {
        const rva = HOOKS[tag];
        const maxH = (tag === 'main_game_entry') ? 1 : 0;
        hookRva(rva, tag, maxH);
        send({ type: 'info', msg: 'hook ' + tag + ' @ 0x' + rva.toString(16) });
    }
    if (LOG_EXPORTS) {
        for (const tag in EXPORTS) {
            hookRva(EXPORTS[tag], tag, 0);
        }
    }
    send({ type: 'ready' });
    return true;
}

if (Process.findModuleByName('Horsey.exe')) {
    install();
} else {
    const id = setInterval(function () {
        if (Process.findModuleByName('Horsey.exe')) {
            clearInterval(id);
            install();
        }
    }, 30);
}
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--attach", action="store_true")
    ap.add_argument("--seconds", type=float, default=14.0)
    ap.add_argument("--frames", type=int, default=4, help="Stop after N swap frames")
    ap.add_argument("--no-exports", action="store_true", help="Only hook in-loop sites")
    args = ap.parse_args()

    import frida

    frames_out: list[dict] = []
    infos: list[str] = []

    def on_message(message, _data):
        if message["type"] != "send":
            if message["type"] == "error":
                print("ERROR:", message.get("stack", message))
            return
        p = message["payload"]
        t = p.get("type")
        if t == "info":
            infos.append(p.get("msg", ""))
            print("[info]", p.get("msg"))
        elif t == "frame_done":
            frames_out.append(p)
            print(f"\n--- Frame {p['frame']} ---")
            for ev in p["events"]:
                extra = ""
                if "returnRva" in ev:
                    extra = f" ret={ev['returnRva']}"
                print(f"  {ev['tag']}{extra}")
        elif t == "done":
            print(f"\nCaptured {p['frames']} frames.")

    js = AGENT % {
        "hooks_json": json.dumps(HOOKS),
        "exports_json": json.dumps(EXPORTS),
        "max_frames": args.frames,
        "log_exports": "false" if args.no_exports else "true",
    }

    device = frida.get_local_device()
    if args.attach:
        session = device.attach("Horsey.exe")
    else:
        pid = device.spawn([str(get_exe_path())], cwd=str(get_game_dir()))
        session = device.attach(pid)
        device.resume(pid)
        print(f"Spawned PID {pid}")

    script = session.create_script(js)
    script.on("message", on_message)
    script.load()
    time.sleep(args.seconds)

    out = ROOT / "RE_Tools" / "analysis" / "frida_gameloop.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    report = {"infos": infos, "frames": frames_out}
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWrote {out}")

    session.detach()
    return 0 if frames_out else 2


if __name__ == "__main__":
    raise SystemExit(main())
