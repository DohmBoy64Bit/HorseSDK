"""
Frida: log SDL_Event.type at Game_DispatchSdlEvent (RVA 0xC0430).

Usage:
  python RE_Tools/tools/scripts/frida_trace_sdl_events.py
  python RE_Tools/tools/scripts/frida_trace_sdl_events.py --attach --seconds 20
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
from paths import get_game_dir  # noqa: E402

DISPATCH_RVA = 0xC0430
OUT = ROOT / "RE_Tools" / "analysis" / "frida_sdl_events.json"

SDL_NAMES = {
    0x100: "SDL_QUIT",
    0x200: "SDL_APP_TERMINATING",
    0x300: "SDL_KEYDOWN",
    0x301: "SDL_KEYUP",
    0x302: "SDL_TEXTEDITING",
    0x303: "SDL_TEXTINPUT",
    0x400: "SDL_WINDOWEVENT",
    0x401: "SDL_SYSWMEVENT",
    0x600: "SDL_MOUSEMOTION",
    0x800: "SDL_MOUSEBUTTONDOWN",
}

AGENT = r"""
'use strict';
const DISPATCH = %(dispatch)d;
const MAX = %(max_events)d;
let n = 0;

function install() {
    const m = Process.findModuleByName('Horsey.exe');
    if (!m) { send({type:'error', msg:'Horsey.exe not loaded'}); return false; }
    const p = m.base.add(DISPATCH);
    Interceptor.attach(p, {
        onEnter(args) {
            if (n >= MAX) return;
            const ev = args[1];
            if (ev.isNull()) return;
            const t = ev.readU32();
            n++;
            send({type:'event', n:n, sdlType:t, typeHex:'0x'+t.toString(16),
                  ctx: args[0].toString()});
        }
    });
    send({type:'info', msg:'hook Game_DispatchSdlEvent @ rva 0x'+DISPATCH.toString(16)});
    return true;
}
if (!install()) {}
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--attach", action="store_true")
    ap.add_argument("--seconds", type=float, default=15.0)
    ap.add_argument("--max", type=int, default=500)
    ap.add_argument("--spawn", action="store_true", help="spawn Game/Horsey.exe")
    args = ap.parse_args()

    try:
        import frida
    except ImportError:
        print("pip install frida frida-tools", file=sys.stderr)
        return 1

    exe = get_game_dir() / "Horsey.exe"
    if not exe.is_file():
        print(f"Missing {exe}", file=sys.stderr)
        return 1

    script_src = AGENT % {"dispatch": DISPATCH_RVA, "max_events": args.max}
    events: list[dict] = []
    counts: Counter = Counter()

    def on_message(msg, _data):
        if msg["type"] == "send":
            p = msg["payload"]
            if p.get("type") == "event":
                t = p.get("sdlType")
                if isinstance(t, int):
                    counts[t] += 1
                events.append(p)
            elif p.get("type") in ("info", "error"):
                print(p)

    if args.attach:
        session = frida.attach("Horsey.exe")
    else:
        session = frida.spawn([str(exe)], cwd=str(exe.parent))
    script = session.create_script(script_src)
    script.on("message", on_message)
    script.load()
    if not args.attach:
        frida.resume(session.pid)
    time.sleep(args.seconds)
    session.detach()

    summary = {
        "dispatch_rva": hex(DISPATCH_RVA),
        "seconds": args.seconds,
        "total": len(events),
        "counts_by_type": {
            hex(k): {"count": v, "name": SDL_NAMES.get(k)}
            for k, v in counts.most_common()
        },
        "sample": events[:80],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} ({len(events)} events)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
