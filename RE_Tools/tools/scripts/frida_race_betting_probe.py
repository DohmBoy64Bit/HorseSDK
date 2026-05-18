#!/usr/bin/env python3
"""
Probe race betting UI fields while on bet / pick screen.

  python RE_Tools/tools/scripts/frida_race_betting_probe.py --attach --seconds 45

Output: RE_Tools/analysis/race_betting_probe.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))

from paths import get_exe_path  # noqa: E402

OUT = ROOT / "RE_Tools" / "analysis" / "race_betting_probe.json"

AGENT = r"""
'use strict';
var RACE_FSM = 0x8F2B0;
var G_PRNG = 0x2F2700;
var samples = [];
var lastMs = 0;

function readRaceCtx(ctx) {
  var o = { ctx: ctx.toString() };
  try {
    o.e0 = ctx.add(0xe0).readS32();
    o.phase = ctx.add(0x3d4).readS32();
    o.bet = ctx.add(0x2c0).readS32();
    o.bet_cap = ctx.add(0x2c4).readS32();
    o.bet_cap2 = ctx.add(0x2c8).readS32();
    o.race_active = ctx.add(0x258).readS32();
    o.score450 = ctx.add(0x450).readS32();
    o.n_horses = ctx.add(0x298).readS32();
    o.g_prng = ptr(G_PRNG_BASE).readU64().toString();
    var list = ctx.add(0x130).readPointer();
  var n = o.n_horses;
  if (n < 0) n = 0;
  if (n > 12) n = 12;
  o.horses = [];
  if (!list.isNull()) {
    for (var i = 0; i < n; i++) {
      var hp = list.add(i * 8).readPointer();
      var h = { i: i, ptr: hp.toString() };
      if (!hp.isNull()) {
        h.f284 = hp.add(0x284).readS32();
        h.f220 = hp.add(0x220).readS32();
      }
      o.horses.push(h);
    }
  }
  } catch (e) {
    o.error = e.toString();
  }
  return o;
}

Interceptor.attach(base.add(RACE_FSM), {
  onEnter: function (args) {
    var now = Date.now();
    if (now - lastMs < 400) return;
    lastMs = now;
    var row = readRaceCtx(args[0]);
    row.t = now;
    if (samples.length < 200) samples.push(row);
  }
});

recv('dump', function () {
  send({ type: 'done', samples: samples });
});
"""

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--attach", action="store_true")
    ap.add_argument("--seconds", type=int, default=45)
    args = ap.parse_args()

    try:
        import frida
    except ImportError:
        print("pip install frida", file=sys.stderr)
        return 1

    exe = get_exe_path()
    if not exe.is_file():
        print(f"Missing {exe}", file=sys.stderr)
        return 1

    if args.attach:
        device = frida.get_local_device()
        session = device.attach("Horsey.exe")
    else:
        print("Use --attach with Horsey running on betting screen", file=sys.stderr)
        return 1

    base = 0x140000000
    script_src = (
        AGENT.replace("var RACE_FSM = 0x8F2B0;", f"var base = ptr('0x{base:x}');\nvar RACE_FSM = 0x{RACE_FSM:x};")
        .replace("0x8F2B0", hex(0x8F2B0))
    )
    script_src = script_src.replace("G_PRNG_BASE", hex(base + 0x2F2700))

    # fix template - build properly
    script_src = f"""
'use strict';
var base = ptr('0x{base:x}');
var RACE_FSM = 0x8F2B0;
var G_PRNG = ptr('0x{base + 0x2F2700:x}');
var samples = [];
var lastMs = 0;

function readRaceCtx(ctx) {{
  var o = {{ ctx: ctx.toString() }};
  try {{
    o.e0 = ctx.add(0xe0).readS32();
    o.phase = ctx.add(0x3d4).readS32();
    o.bet = ctx.add(0x2c0).readS32();
    o.bet_cap = ctx.add(0x2c4).readS32();
    o.bet_cap2 = ctx.add(0x2c8).readS32();
    o.race_active = ctx.add(0x258).readS32();
    o.score450 = ctx.add(0x450).readS32();
    o.n_horses = ctx.add(0x298).readS32();
    o.g_prng = G_PRNG.readU64().toString();
    var list = ctx.add(0x130).readPointer();
    var n = o.n_horses;
    if (n < 0) n = 0;
    if (n > 12) n = 12;
    o.horses = [];
    if (!list.isNull()) {{
      for (var i = 0; i < n; i++) {{
        var hp = list.add(i * 8).readPointer();
        var h = {{ i: i, ptr: hp.toString() }};
        if (!hp.isNull()) {{
          h.f284 = hp.add(0x284).readS32();
          h.f220 = hp.add(0x220).readS32();
        }}
        o.horses.push(h);
      }}
    }}
  }} catch (e) {{
    o.error = e.toString();
  }}
  return o;
}}

Interceptor.attach(base.add(RACE_FSM), {{
  onEnter: function (args) {{
    var now = Date.now();
    if (now - lastMs < 400) return;
    lastMs = now;
    var row = readRaceCtx(args[0]);
    row.t = now;
    if (samples.length < 200) samples.push(row);
  }}
}});

recv('dump', function () {{
  send({{ type: 'done', samples: samples }});
}});
"""

    done = []

    def on_message(message, _data):
        if message.get("type") == "send" and message.get("payload", {}).get("type") == "done":
            done.append(message["payload"])

    script = session.create_script(script_src)
    script.on("message", on_message)
    script.load()
    print(f"Attached. On betting screen for {args.seconds}s...")
    time.sleep(args.seconds)
    script.post({"type": "dump"})
    time.sleep(1)
    session.detach()

    payload = done[0] if done else {"samples": []}
    payload["note"] = "RaceStateMachine samples; see RE_Tools/docs/RaceBettingOdds.md"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} ({len(payload.get('samples', []))} samples)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
