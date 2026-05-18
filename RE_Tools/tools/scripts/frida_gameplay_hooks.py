"""
Frida: gameplay hooks for SDK validation.

  - GainMoney @ 0x10AB80 (shop purchase, race payout, …)
  - SimSpawnDisk @ 0x33A20 (placing horses / world spawn FSM entry)
  - RaceStateMachine @ 0x8F2B0 (race UI FSM)
  - RaceGo dispatch site @ 0x91274 (mov [rip+disp] in race cluster — string phase)

Usage:
  python RE_Tools/tools/scripts/frida_gameplay_hooks.py --attach --seconds 120

In-game: buy from shop, place a horse, start and run a race.

Output: RE_Tools/analysis/gameplay_frida.json
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

OUT = ROOT / "RE_Tools" / "analysis" / "gameplay_frida.json"

# Verified / Ghidra (GameFunctions.h)
GAIN_MONEY = 0x10AB80
SIM_SPAWN_DISK = 0x33A20
BUY_ITEM = 0x787D0
RACE_FSM = 0x8F2B0
RACE_GO_SITE = 0x91274
SIM_DISPATCH_LO = 0x33000
SIM_DISPATCH_HI = 0x35000
SIM_MID_LO = 0x5F000
SIM_MID_HI = 0x61000

AGENT = r"""
'use strict';
var GAIN = __GAIN__;
var SPAWN = __SPAWN__;
var BUY = __BUY__;
var RACE = __RACE__;
var RACE_GO = __RACE_GO__;
var SIM_LO = __SIM_LO__;
var SIM_HI = __SIM_HI__;
var MID_LO = __MID_LO__;
var MID_HI = __MID_HI__;

var gain = [];
var spawn = [];
var buy = [];
var race = [];
var racego = [];
var simCalls = [];

function modRva(a) {
  var m = Process.findModuleByAddress(a);
  if (m && m.name.toLowerCase() === 'horsey.exe')
    return '0x' + a.sub(m.base).toString(16);
  return a.toString();
}

function bt(ctx, n) {
  return Thread.backtrace(ctx, Backtracer.ACCURATE).slice(0, n).map(modRva);
}

function readMoney(ctx) {
  try {
    return {
      money: ctx.add(0x308).readS32(),
      timer: ctx.add(0x30c).readS32(),
      delta: ctx.add(0x310).readS32()
    };
  } catch (e) { return {}; }
}

var base = Process.findModuleByName('Horsey.exe').base;

Interceptor.attach(base.add(GAIN), {
  onEnter: function (args) {
    this.ctx = args[0];
    this.amt = args[1].toInt32();
    this.ui = args[2].toInt32() & 0xff;
    this.before = readMoney(this.ctx);
    this.bt = bt(this.context, 8);
  },
  onLeave: function () {
    var row = {
      type: 'gain_money',
      amount: this.amt,
      show_ui: this.ui,
      ctx: this.ctx.toString(),
      before: this.before,
      after: readMoney(this.ctx),
      bt: this.bt,
      from_buy: this.bt.some(function (x) {
        var v = parseInt(x, 16);
        return v >= BUY && v < BUY + 0x4000;
      })
    };
    gain.push(row);
    send({ type: 'gain_money', row: row });
  }
});

Interceptor.attach(base.add(SPAWN), {
  onEnter: function (args) {
    var row = {
      type: 'sim_spawn_disk',
      rcx: args[0].toString(),
      rdx: args[1] ? args[1].toString() : '',
      bt: bt(this.context, 10)
    };
    spawn.push(row);
    send({ type: 'sim_spawn', row: row });
  }
});

Interceptor.attach(base.add(BUY), {
  onEnter: function () {
    var row = { type: 'buy_item', bt: bt(this.context, 6) };
    buy.push(row);
    send({ type: 'buy_item', row: row });
  }
});

var raceLast = 0;
Interceptor.attach(base.add(RACE), {
  onEnter: function (args) {
    var now = Date.now();
    if (now - raceLast < 200) return;
    raceLast = now;
    var row = {
      type: 'race_fsm',
      param_1: args[0].toString(),
      bt: bt(this.context, 6)
    };
    race.push(row);
    if (race.length <= 80) send({ type: 'race_fsm', row: row });
  }
});

Interceptor.attach(base.add(RACE_GO), {
  onEnter: function () {
    var row = {
      type: 'racego_site',
      bt: bt(this.context, 12)
    };
    racego.push(row);
    send({ type: 'racego', row: row });
  }
});

/* Log direct calls into sim dispatch regions (SimStartRace body hunt) */
var hookSim = function (lo, hi, tag) {
  var p = base.add(lo);
  var end = base.add(hi);
  while (p.compare(end) < 0) {
    (function (addr, regionTag) {
      try {
        Interceptor.attach(addr, {
          onEnter: function () {
            if (simCalls.length > 200) return;
            var row = {
              type: 'sim_region',
              region: regionTag,
              target: modRva(addr),
              bt: bt(this.context, 8)
            };
            simCalls.push(row);
            send({ type: 'sim_region', row: row });
          }
        });
      } catch (e) {}
    })(p, tag);
    p = p.add(1);
  }
};
/* Too many 1-byte hooks — instead hook a few hot targets from static scan */
rpc.exports.setSimTargets = function (addrs) {
  addrs.forEach(function (rvaHex) {
    var rva = parseInt(rvaHex, 16);
    try {
      Interceptor.attach(base.add(rva), {
        onEnter: function () {
          if (simCalls.length > 150) return;
          var row = { type: 'sim_target', rva: modRva(this.context.pc), bt: bt(this.context, 8) };
          simCalls.push(row);
          send({ type: 'sim_target', row: row });
        }
      });
    } catch (e) {}
  });
};

rpc.exports.summary = function () {
  return {
    gain_money: gain,
    sim_spawn: spawn,
    buy_item: buy,
    race_fsm: race,
    racego_hits: racego,
    sim_calls: simCalls
  };
};
"""


def load_sim_targets() -> list[str]:
    p = ROOT / "RE_Tools" / "analysis" / "sim_start_race_callees.json"
    if not p.is_file():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    # top 8 targets by caller count
    ranked = sorted(data.get("by_target", {}).items(), key=lambda kv: -len(kv[1]))
    out: list[str] = []
    for tgt, _ in ranked[:8]:
        out.append(tgt.replace("0x", ""))
    return out


def main() -> int:
    import frida

    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=120.0)
    ap.add_argument("--attach", action="store_true", help="Attach to running Horsey.exe (required)")
    ap.add_argument(
        "--full-events",
        action="store_true",
        help="Include raw send() events in JSON (large file)",
    )
    args = ap.parse_args()
    if not args.attach:
        print("Use --attach: start Horsey, load a save, then run this script.")
        return 1
    events: list = []

    def on_msg(msg, _):
        if msg.get("type") == "send":
            events.append(msg["payload"])

    agent = (
        AGENT.replace("__GAIN__", str(GAIN_MONEY))
        .replace("__SPAWN__", str(SIM_SPAWN_DISK))
        .replace("__BUY__", str(BUY_ITEM))
        .replace("__RACE__", str(RACE_FSM))
        .replace("__RACE_GO__", str(RACE_GO_SITE))
        .replace("__SIM_LO__", str(SIM_DISPATCH_LO))
        .replace("__SIM_HI__", str(SIM_DISPATCH_HI))
        .replace("__MID_LO__", str(SIM_MID_LO))
        .replace("__MID_HI__", str(SIM_MID_HI))
    )

    device = frida.get_local_device()
    if args.attach:
        procs = [p for p in device.enumerate_processes() if p.name.lower() == "horsey.exe"]
        if not procs:
            print("No Horsey.exe — start game, load save, re-run with --attach")
            return 1
        pid = procs[0].pid
        session = device.attach(pid)
    else:
        pid = device.spawn([str(get_exe_path())], cwd=str(get_game_dir()))
        session = device.attach(pid)

    script = session.create_script(agent)
    script.on("message", on_msg)
    script.load()

    targets = load_sim_targets()
    if targets:
        try:
            script.exports_sync.set_sim_targets(targets)
            print(f"Hooked {len(targets)} sim dispatch targets from sim_start_race_callees.json")
        except Exception as e:
            print(f"setSimTargets skipped: {e}")

    if not args.attach:
        device.resume(pid)

    print(f"Attached pid={pid} for {args.seconds}s — trigger in-game now:")
    print("  shop buy  |  place horse  |  start/run race")
    print(f"  Output -> {OUT}")
    t0 = time.time()
    while time.time() - t0 < args.seconds:
        time.sleep(5.0)
        n = len([e for e in events if e.get("type")])
        print(f"  … {int(time.time() - t0)}s  events={n}", flush=True)
    try:
        summary = script.exports_sync.summary()
    except Exception:
        summary = {}
    try:
        session.detach()
    except Exception:
        pass

    def rows_of(kind: str) -> list:
        from_rpc = summary.get(kind, [])
        if from_rpc:
            return from_rpc
        return [e["row"] for e in events if e.get("type") == kind and e.get("row")]

    gain_rows = rows_of("gain_money")
    spawn_rows = rows_of("sim_spawn")
    buy_rows = rows_of("buy_item")
    race_rows = rows_of("race_fsm")
    racego_rows = rows_of("racego")
    sim_rows = summary.get("sim_calls", []) or [
        e["row"] for e in events if e.get("type") in ("sim_region", "sim_target") and e.get("row")
    ]

    report = {
        "hooks": {
            "GainMoney": hex(GAIN_MONEY),
            "SimSpawnDisk": hex(SIM_SPAWN_DISK),
            "BuyItem": hex(BUY_ITEM),
            "RaceStateMachine": hex(RACE_FSM),
            "RaceGo_site": hex(RACE_GO_SITE),
        },
        "sim_targets_hooked": targets,
        "summary_counts": {
            "gain_money": len(gain_rows),
            "sim_spawn": len(spawn_rows),
            "buy_item": len(buy_rows),
            "race_fsm": len(race_rows),
            "racego_hits": len(racego_rows),
            "sim_calls": len(sim_rows),
        },
        "gain_money": gain_rows[:50],
        "sim_spawn": spawn_rows[:50],
        "buy_item": buy_rows[:50],
        "race_fsm": race_rows[:40],
        "race_fsm_bt_sample": race_rows[0].get("bt") if race_rows else None,
        "racego_hits": racego_rows[:30],
        "sim_calls": sim_rows[:60],
        "note": "Attach with save loaded; perform shop buy, horse place, race start for hits.",
    }
    if args.full_events:
        report["events"] = events
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} {report['summary_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
