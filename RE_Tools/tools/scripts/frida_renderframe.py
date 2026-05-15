"""
Frida: confirm per-frame render path and repomix RenderFrame RVA (0x11E0F0).

Hooks SDL_GL_SwapWindow (export RVA 0x1238D0). Return address after call = real frame loop site.

Usage:
  python RE_Tools/tools/scripts/frida_renderframe.py
  python RE_Tools/tools/scripts/frida_renderframe.py --attach --seconds 20
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
from paths import get_exe_path, get_game_dir  # noqa: E402

REPOMIX_RENDER_FRAME_RVA = 0x11E0F0
MAIN_GAME_FUNC_RVA = 0xBE0F0
SDL_SWAP_EXPORT_RVA = 0x1238D0
STEAM_RUN_CALLBACKS_RVA = 0xBEA7F  # in same loop region (phase1_verify)
MAX_SWAP_HITS = 6

AGENT = r"""
'use strict';

const REPOMIX_RF = %(repomix_rf)d;
const MAIN_GAME = %(main_game)d;
const SDL_SWAP = %(sdl_swap)d;
const STEAM_CB = %(steam_cb)d;
const MAX_SWAP = %(max_swap)d;

let horsey = null;

function horseyRva(addr) {
    if (!horsey || addr.isNull()) return null;
    const o = addr.sub(horsey.base);
    if (o.compare(0) < 0 || o.compare(horsey.size) >= 0) return null;
    return '0x' + o.toString(16).toUpperCase();
}

function modOff(addr) {
    const m = Process.findModuleByAddress(addr);
    if (!m) return addr.toString();
    return m.name + '+0x' + addr.sub(m.base).toString(16).toUpperCase();
}

function bt(context, limit) {
    return Thread.backtrace(context, Backtracer.ACCURATE)
        .slice(0, limit)
        .map(modOff);
}

function hookExport(rva, tag, maxHits, useReturnAddr) {
    const p = horsey.base.add(rva);
    let n = 0;
    Interceptor.attach(p, {
        onEnter(args) {
            n++;
            if (n > maxHits) return;
            const payload = {
                type: 'hit',
                tag: tag,
                n: n,
                hook: '0x' + rva.toString(16)
            };
            if (useReturnAddr) {
                const ret = this.returnAddress;
                payload.returnAddr = modOff(ret);
                payload.returnRva = horseyRva(ret);
                payload.frames = bt(this.context, 10);
            }
            send(payload);
        }
    });
    send({ type: 'info', msg: 'Hook ' + tag + ' @ ' + p });
}

function install() {
    horsey = Process.findModuleByName('Horsey.exe');
    if (!horsey) {
        send({ type: 'error', msg: 'Horsey.exe not loaded' });
        return false;
    }
    send({ type: 'info', msg: 'base=' + horsey.base + ' size=0x' + horsey.size.toString(16) });

    // Repomix "RenderFrame" — expect zero hits in live loop
    hookExport(REPOMIX_RF, 'repomix_11E0F0', 2, true);

    // Real frame path: SDL_GL_SwapWindow return lands after E8 @ 0xBEAF0 -> 0xBEAF5
    hookExport(SDL_SWAP, 'SDL_GL_SwapWindow', MAX_SWAP, true);

    // Once when main game function entered
    hookExport(MAIN_GAME, 'main_game_BE0F0', 1, true);

  // Steam callbacks in loop (optional signal)
    hookExport(STEAM_CB, 'SteamAPI_RunCallbacks', 2, true);

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
    parser = argparse.ArgumentParser()
    parser.add_argument("--attach", action="store_true")
    parser.add_argument("--seconds", type=float, default=15.0)
    args = parser.parse_args()

    import frida

    results: list[dict] = []

    def on_message(message, _data):
        if message["type"] != "send":
            if message["type"] == "error":
                print("FRIDA ERROR:", message.get("stack", message))
            return
        p = message["payload"]
        results.append(p)
        t = p.get("type")
        if t == "hit":
            print(f"\n=== {p['tag']} #{p['n']} ===")
            if "returnAddr" in p:
                print(f"  return -> {p['returnAddr']}  (Horsey RVA {p.get('returnRva')})")
            if p.get("frames"):
                for i, f in enumerate(p["frames"]):
                    print(f"    [{i}] {f}")
        elif t == "info":
            print(f"[info] {p.get('msg')}")

    js = AGENT % {
        "repomix_rf": REPOMIX_RENDER_FRAME_RVA,
        "main_game": MAIN_GAME_FUNC_RVA,
        "sdl_swap": SDL_SWAP_EXPORT_RVA,
        "steam_cb": STEAM_RUN_CALLBACKS_RVA,
        "max_swap": MAX_SWAP_HITS,
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

    out = ROOT / "RE_Tools" / "analysis" / "frida_renderframe.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(str(r) for r in results) + "\n", encoding="utf-8")

    swap = [r for r in results if r.get("tag") == "SDL_GL_SwapWindow"]
    repomix = [r for r in results if r.get("tag") == "repomix_11E0F0"]

    print("\n--- Summary ---")
    if swap:
        print(f"Per-frame swap: caller return RVA = {swap[0].get('returnRva')} (expect 0xBEAF5)")
        if len(swap) > 1:
            print(f"  frame 2 return RVA = {swap[1].get('returnRva')}")
    else:
        print("No SDL_GL_SwapWindow hits.")
    print(f"Repomix 0x11E0F0 hits: {len(repomix)} (expect 0)")
    print(f"Wrote {out}")

    session.detach()
    return 0 if swap else 2


if __name__ == "__main__":
    raise SystemExit(main())
