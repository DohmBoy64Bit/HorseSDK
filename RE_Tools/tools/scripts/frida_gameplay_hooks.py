"""
Frida: gameplay hooks for SDK validation.

  - GainMoney @ 0x10AB80 (credits — race prize, etc.)
  - SpendMoney @ 0x10AC60 (debits — shop purchases; BuyItem.c.txt calls this)
  - SpawnEntity @ 0x30492 (calls SpawnPlace @ 0x32330 from 0x30B52)
  - SpawnPlace @ 0x32330 (SimSpawnDisk spawn callee)
  - GrabHorse @ 0xD6340 (GrabHorse string @ 0xD9158; not 0xD71DF)
  - DropHorseFail @ 0xD3C50 (failed tile drop)
  - BuyItem @ 0x787D0 (shop UI tick)
  - RaceStateMachine @ 0x8F2B0 (optional, --no-race to skip menu noise)
  - RaceAdvanceSim @ 0x8C9E0 (race sim tick — ctx race score @ +0x450 vs finish slots)

Usage:
  python RE_Tools/tools/scripts/frida_gameplay_hooks.py --attach
  python RE_Tools/tools/scripts/frida_gameplay_hooks.py --attach --seconds 120

Attach, play in-game, press Enter when done (or use --seconds for a timer).

Output: RE_Tools/analysis/gameplay_frida.json
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))

from paths import get_exe_path, get_game_dir  # noqa: E402

OUT = ROOT / "RE_Tools" / "analysis" / "gameplay_frida.json"

# Verified Ghidra + Capstone E8 scan (Horsey.exe)
GAIN_MONEY = 0x10AB80
SPEND_MONEY = 0x10AC60  # subtract [ctx+0x308]; BuyItem + race betting
SPAWN_ENTITY = 0x30492  # mov rcx,rdi; call 0x32330 @ 0x30B52
SPAWN_PLACE = 0x32330
GRAB_HORSE = 0xD6340  # 12 E8 callers; GrabHorse tag @ 0xD9158 inside body
DROP_HORSE_FAIL = 0xD3C50
BUY_ITEM = 0x787D0
RACE_FSM = 0x8F2B0
RACE_ADVANCE_SIM = 0x8C9E0
G_SETTINGS_SEED = 0x2F1587
G_PRNG_STATE = 0x2F2700
# NEVER hook 0x91274 (mid-instruction) or 0xD71DF (wrong entry).

AGENT = r"""
'use strict';
var GAIN = __GAIN__;
var SPEND = __SPEND__;
var SPAWN_ENT = __SPAWN_ENT__;
var SPAWN = __SPAWN__;
var GRAB = __GRAB__;
var DROP_FAIL = __DROP_FAIL__;
var BUY = __BUY__;
var RACE = __RACE__;
var RACE_SIM = __RACE_SIM__;
var HOOK_RACE = __HOOK_RACE__;
var HOOK_RACE_SIM = __HOOK_RACE_SIM__;
var G_SEED = __G_SEED__;
var G_PRNG = __G_PRNG__;

var gain = [];
var spend = [];
var spawnEnt = [];
var spawn = [];
var grab = [];
var dropFail = [];
var buy = [];
var race = [];
var raceSim = [];
var buyThrottle = 0;
var raceSimThrottle = 0;
var raceSimTicks = 0;

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

Interceptor.attach(base.add(SPEND), {
  onEnter: function (args) {
    this.ctx = args[0];
    this.cost = args[1].toInt32();
    this.before = readMoney(this.ctx);
    this.bt = Thread.backtrace(this.context, Backtracer.FUZZY).slice(0, 8).map(modRva);
  },
  onLeave: function () {
    var row = {
      type: 'spend_money',
      cost: this.cost,
      ctx: this.ctx.toString(),
      before: this.before,
      after: readMoney(this.ctx),
      bt: this.bt,
      from_buy: this.bt.some(function (x) {
        var v = parseInt(x, 16);
        return v >= BUY && v < BUY + 0x5000;
      })
    };
    spend.push(row);
    send({ type: 'spend_money', row: row });
  }
});

Interceptor.attach(base.add(SPAWN_ENT), {
  onEnter: function (args) {
    var row = {
      type: 'spawn_entity',
      rcx: args[0].toString(),
      bt: Thread.backtrace(this.context, Backtracer.FUZZY).slice(0, 8).map(modRva)
    };
    spawnEnt.push(row);
    send({ type: 'spawn_entity', row: row });
  }
});

Interceptor.attach(base.add(SPAWN), {
  onEnter: function (args) {
    var row = {
      type: 'spawn_place',
      rcx: args[0].toString(),
      bt: Thread.backtrace(this.context, Backtracer.FUZZY).slice(0, 8).map(modRva)
    };
    spawn.push(row);
    send({ type: 'spawn_place', row: row });
  }
});

Interceptor.attach(base.add(GRAB), {
  onEnter: function (args) {
    var row = {
      type: 'grab_horse',
      rcx: args[0].toString(),
      rdx: args[1] ? args[1].toInt32() : 0,
      bt: Thread.backtrace(this.context, Backtracer.FUZZY).slice(0, 8).map(modRva)
    };
    grab.push(row);
    send({ type: 'grab_horse', row: row });
  }
});

Interceptor.attach(base.add(DROP_FAIL), {
  onEnter: function (args) {
    var row = {
      type: 'drop_horse_fail',
      rcx: args[0].toString(),
      bt: Thread.backtrace(this.context, Backtracer.FUZZY).slice(0, 8).map(modRva)
    };
    dropFail.push(row);
    send({ type: 'drop_horse_fail', row: row });
  }
});

Interceptor.attach(base.add(BUY), {
  onEnter: function () {
    var now = Date.now();
    if (now - buyThrottle < 250) return;
    buyThrottle = now;
    if (buy.length > 200) return;
    var row = { type: 'buy_item', bt: Thread.backtrace(this.context, Backtracer.FUZZY).slice(0, 6).map(modRva) };
    buy.push(row);
    if (buy.length <= 30) send({ type: 'buy_item', row: row });
  }
});

if (HOOK_RACE) {
  var raceLast = 0;
  Interceptor.attach(base.add(RACE), {
    onEnter: function (args) {
      var now = Date.now();
      if (now - raceLast < 500) return;
      raceLast = now;
      var row = { type: 'race_fsm', param_1: args[0].toString() };
      if (race.length < 30) {
        row.bt = Thread.backtrace(this.context, Backtracer.FUZZY).slice(0, 6).map(modRva);
      }
      race.push(row);
      if (race.length <= 60) send({ type: 'race_fsm', row: row });
    }
  });
}

function readRaceSnapshot(ctx) {
  var out = { horses: [], n_horses: 0 };
  try {
    out.race_score_450 = ctx.add(0x450).readS32();
    out.n_horses = ctx.add(0x298).readS32();
    var slots = ctx.add(0x280).readPointer();
    var list = ctx.add(0x130).readPointer();
    if (slots.isNull() || list.isNull()) return out;
    var n = out.n_horses;
    if (n < 0) n = 0;
    if (n > 16) n = 16;
    for (var i = 0; i < n; i++) {
      var slot = slots.add(i * 0x70);
      var horsePtr = list.add(i * 8).readPointer();
      var h = {
        i: i,
        finish_place: slot.add(0x0c).readS32(),
        progress: slot.add(0x10).readS32(),
        timer: slot.add(0x14).readS32(),
        speed_f: slot.add(0x24).readFloat()
      };
      if (!horsePtr.isNull()) {
        h.speed_220 = horsePtr.add(0x220).readS32();
      }
      out.horses.push(h);
    }
  } catch (e) {
    out.error = e.toString();
  }
  return out;
}

if (HOOK_RACE_SIM) {
  Interceptor.attach(base.add(RACE_SIM), {
    onEnter: function (args) {
      raceSimTicks++;
      var now = Date.now();
      if (now - raceSimThrottle < 250) return;
      raceSimThrottle = now;
      if (raceSim.length > 120) return;
      var ctx = args[0];
      var row = {
        type: 'race_advance_sim',
        tick: raceSimTicks,
        ctx: ctx.toString(),
        state_e0: ctx.add(0xe0).readS32(),
        frame_254: ctx.add(0x254).readS32(),
        race_flag_258: ctx.add(0x258).readU8(),
        g_settings_seed: base.add(G_SEED).readU32(),
        g_prng_state: base.add(G_PRNG).readU64().toString(),
        snapshot: readRaceSnapshot(ctx)
      };
      raceSim.push(row);
      if (raceSim.length <= 40) send({ type: 'race_advance_sim', row: row });
    }
  });
}

rpc.exports.summary = function () {
  return {
    gain_money: gain,
    spend_money: spend,
    spawn_place: spawn,
    grab_horse: grab,
    buy_item: buy,
    race_fsm: race,
    race_advance_sim: raceSim,
    race_advance_sim_ticks: raceSimTicks
  };
};
"""


def main() -> int:
    import frida

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--seconds",
        type=float,
        default=None,
        help="Auto-stop after N seconds (default: wait until you press Enter)",
    )
    ap.add_argument("--attach", action="store_true", help="Attach to running Horsey.exe (required)")
    ap.add_argument(
        "--full-events",
        action="store_true",
        help="Include raw send() events in JSON (large file)",
    )
    ap.add_argument(
        "--no-race",
        action="store_true",
        help="Skip RaceStateMachine hook (menu ticks constantly)",
    )
    ap.add_argument(
        "--no-race-sim",
        action="store_true",
        help="Skip RaceAdvanceSim hook (verbose during active race)",
    )
    args = ap.parse_args()
    if not args.attach:
        print("Use --attach: start Horsey, load a save, then run this script.")
        return 1
    events: list = []

    def on_msg(msg, _):
        if msg.get("type") == "send":
            events.append(msg["payload"])

    hook_race = not args.no_race
    hook_race_sim = not args.no_race_sim
    agent = (
        AGENT.replace("__GAIN__", str(GAIN_MONEY))
        .replace("__SPEND__", str(SPEND_MONEY))
        .replace("__SPAWN_ENT__", str(SPAWN_ENTITY))
        .replace("__SPAWN__", str(SPAWN_PLACE))
        .replace("__GRAB__", str(GRAB_HORSE))
        .replace("__DROP_FAIL__", str(DROP_HORSE_FAIL))
        .replace("__BUY__", str(BUY_ITEM))
        .replace("__RACE__", str(RACE_FSM))
        .replace("__RACE_SIM__", str(RACE_ADVANCE_SIM))
        .replace("__HOOK_RACE__", "true" if hook_race else "false")
        .replace("__HOOK_RACE_SIM__", "true" if hook_race_sim else "false")
        .replace("__G_SEED__", str(G_SETTINGS_SEED))
        .replace("__G_PRNG__", str(G_PRNG_STATE))
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

    hooked = ["GainMoney", "SpendMoney", "SpawnPlace", "GrabHorse", "BuyItem"]
    if hook_race:
        hooked.append("RaceStateMachine")
    if hook_race_sim:
        hooked.append("RaceAdvanceSim")
    print("Hooks:", ", ".join(hooked))
    print("Note: GrabHorse entry is 0xD6340 (not 0xD71DF). SimStartRace body is RaceSimHandler@0x5F020.")

    if not args.attach:
        device.resume(pid)

    print(f"Attached pid={pid} — trigger in-game now:")
    print("  shop buy  |  place horse  |  start/run race")
    print(f"  Output -> {OUT}")

    stop_ticker = threading.Event()

    def event_ticker() -> None:
        t0 = time.time()
        while not stop_ticker.wait(5.0):
            n = len(events)
            print(f"  … {int(time.time() - t0)}s  events={n}", flush=True)

    ticker = threading.Thread(target=event_ticker, daemon=True)
    ticker.start()

    if args.seconds is not None:
        print(f"  Auto-stop in {args.seconds}s (or Ctrl+C)")
        time.sleep(args.seconds)
    else:
        print("  Press Enter when finished…")
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            print()
    stop_ticker.set()
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
    spend_rows = rows_of("spend_money")
    spawn_ent_rows = rows_of("spawn_entity")
    spawn_rows = rows_of("spawn_place") or rows_of("sim_spawn")
    grab_rows = rows_of("grab_horse")
    drop_rows = rows_of("drop_horse_fail")
    buy_rows = rows_of("buy_item")
    race_rows = rows_of("race_fsm")
    race_sim_rows = rows_of("race_advance_sim")

    report = {
        "hooks": {
            "GainMoney": hex(GAIN_MONEY),
            "SpendMoney": hex(SPEND_MONEY),
            "SpawnEntity": hex(SPAWN_ENTITY),
            "SpawnPlace": hex(SPAWN_PLACE),
            "GrabHorse": hex(GRAB_HORSE),
            "DropHorseFail": hex(DROP_HORSE_FAIL),
            "BuyItem": hex(BUY_ITEM),
            "RaceStateMachine": hex(RACE_FSM) if hook_race else None,
            "RaceAdvanceSim": hex(RACE_ADVANCE_SIM) if hook_race_sim else None,
            "g_settings_seed": hex(G_SETTINGS_SEED),
            "g_prng_state": hex(G_PRNG_STATE),
        },
        "why_old_log_missed": {
            "sim_spawn_0": "0x33A20 has no E8 callers; use 0x32330 + GrabHorse@0xD71DF",
            "gain_on_buy": "shops debit via SpendMoney@0x10AC60 not GainMoney",
            "sim_dispatch_0": "SimStartRace is tag data, not SimMessageDispatch entry",
            "buy_1475": "BuyItem ticks every frame while shop UI open",
            "race_76": "RaceStateMachine did fire — race was captured",
        },
        "summary_counts": {
            "gain_money": len(gain_rows),
            "spend_money": len(spend_rows),
            "spawn_entity": len(spawn_ent_rows),
            "spawn_place": len(spawn_rows),
            "grab_horse": len(grab_rows),
            "drop_horse_fail": len(drop_rows),
            "buy_item": len(buy_rows),
            "race_fsm": len(race_rows),
            "race_advance_sim": len(race_sim_rows),
        },
        "gain_money": gain_rows[:50],
        "spend_money": spend_rows[:50],
        "spawn_entity": spawn_ent_rows[:50],
        "spawn_place": spawn_rows[:50],
        "grab_horse": grab_rows[:50],
        "drop_horse_fail": drop_rows[:30],
        "buy_item": buy_rows[:50],
        "race_fsm": race_rows[:40],
        "race_fsm_bt_sample": race_rows[0].get("bt") if race_rows else None,
        "race_advance_sim": race_sim_rows[:80],
        "race_advance_sim_sample": race_sim_rows[-1] if race_sim_rows else None,
        "note": "race_advance_sim: snapshot.race_score_450 = [race_ctx+0x450] (HorseRaceScore @ 0xE2FBD); finish_place @ slot+0x0C.",
    }
    if args.full_events:
        report["events"] = events
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} {report['summary_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
