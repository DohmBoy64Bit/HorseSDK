"""
Frida: hook GeneticsApply @ 0xAE470 after load — correlate item+0x2B8 pack with genes.xml.

Also hooks ReadNestedItem path @ 0x6EF80 (first inventory slot gene pack sample).

Usage:
  python RE_Tools/tools/scripts/frida_genetics_ae470.py --seconds 25

Output: RE_Tools/analysis/save_genetics_frida.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "scripts"))

from paths import get_data_dir, get_exe_path, get_game_dir  # noqa: E402
from inventory_pack_codec import unpack_6d3b0, GENE_COUNT  # noqa: E402

OUT = ROOT / "RE_Tools" / "analysis" / "save_genetics_frida.json"
AE470 = 0xAE470
ADB30 = 0xADB30
READ_ITEM = 0x6EF80

AGENT = r"""
'use strict';
var AE470 = __AE470__;
var ADB30 = __ADB30__;
var hits = [];
var adb = [];

function modRva(a) {
  var m = Process.findModuleByAddress(a);
  if (m && m.name.toLowerCase() === 'horsey.exe')
    return 'Horsey.exe+' + a.sub(m.base).toString(16).toUpperCase();
  return a.toString();
}

var base = Process.findModuleByName('Horsey.exe').base;

Interceptor.attach(base.add(AE470), {
  onEnter: function (args) {
  },
  onLeave: function (ret) {
    var item = this.context.rcx;
    var row = { type: 'ae470', item: item.toString(), bt: Thread.backtrace(this.context, Backtracer.ACCURATE).slice(0, 6).map(modRva) };
    try {
      var packPtr = item.add(0x2B8);
      row.pack_head_hex = packPtr.readByteArray(16) ? Array.from(new Uint8Array(packPtr.readByteArray(16))).map(function (b) { return ('0' + b.toString(16)).slice(-2); }).join('') : '';
      row.threshold_234 = item.add(0x234).readS32();
    } catch (e) {}
    hits.push(row);
    send({ type: 'hit', row: row });
  }
});

Interceptor.attach(base.add(ADB30), {
  onEnter: function (args) {
    adb.push({ type: 'adb30_enter', item: this.context.rcx.toString() });
  }
});

Interceptor.attach(base.add(READ_ITEM), {
  onLeave: function () {
    if (hits.length > 20) return;
    try {
      var item = this.context.rcx;
      var packed = item.add(0x2B8).readByteArray(0xF0);
      if (!packed) return;
      var arr = Array.from(new Uint8Array(packed));
      var row = { type: 'read_item_pack', item: item.toString(), pack_hex: arr.slice(0, 32).map(function (b) { return ('0' + b.toString(16)).slice(-2); }).join('') };
      hits.push(row);
      send({ type: 'hit', row: row });
    } catch (e) {}
  }
});

rpc.exports.summary = function () { return { hits: hits, adb: adb }; };
"""


def load_gene_names() -> list[str]:
    p = get_data_dir() / "genes.xml"
    if not p.is_file():
        return []
    root = ET.parse(p).getroot()
    return [el.attrib.get("name", f"g{i}") for i, el in enumerate(root.findall("gene"))]


def decode_pack_head(hex32: str) -> dict:
    if not hex32 or len(hex32) < 32:
        return {}
    raw = bytes.fromhex(hex32[: 0xF0 * 2] if len(hex32) >= 0xF0 * 2 else hex32)
    if len(raw) < 0xF0:
        raw = raw + bytes(0xF0 - len(raw))
    u = unpack_6d3b0(raw)
    nz_a = sum(1 for i in range(GENE_COUNT) if u[i] not in (0, 0xFF))
    nz_b = sum(1 for i in range(GENE_COUNT, GENE_COUNT * 2) if u[i] not in (0, 0xFF))
    return {"nonzero_track_a": nz_a, "nonzero_track_b": nz_b, "head_a": list(u[:8]), "head_b": list(u[GENE_COUNT : GENE_COUNT + 8])}


def main() -> int:
    import frida

    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=25.0)
    ap.add_argument(
        "--attach",
        action="store_true",
        help="Attach to running Horsey.exe (load a save in-game first)",
    )
    args = ap.parse_args()
    names = load_gene_names()
    events: list = []

    def on_msg(msg, _):
        if msg.get("type") == "send":
            events.append(msg["payload"])

    device = frida.get_local_device()
    if args.attach:
        procs = [p for p in device.enumerate_processes() if p.name.lower() == "horsey.exe"]
        if not procs:
            print("No running Horsey.exe — start game, load save, re-run with --attach")
            return 1
        pid = procs[0].pid
        session = device.attach(pid)
    else:
        pid = device.spawn([str(get_exe_path())], cwd=str(get_game_dir()))
        session = device.attach(pid)
    script = session.create_script(
        AGENT.replace("__AE470__", str(AE470))
        .replace("__ADB30__", str(ADB30))
    )
    script.on("message", on_msg)
    script.load()
    if not args.attach:
        device.resume(pid)
    print(f"Frida genetics: pid={pid} attach={args.attach} — load save in-game for AE470 hits")
    time.sleep(args.seconds)
    try:
        summary = script.exports_sync.summary()
    except Exception:
        summary = {"hits": [], "adb": []}
    try:
        session.detach()
    except Exception:
        pass

    for h in summary.get("hits", []):
        if h.get("pack_head_hex"):
            h["pack_decode"] = decode_pack_head(h["pack_head_hex"])

    report = {
        "genes_xml": str(get_data_dir() / "genes.xml"),
        "gene_count": len(names),
        "gene_names_sample": names[:8],
        "exe": {
            "AE470": hex(AE470),
            "ADB30": hex(ADB30),
            "ReadNestedItem": hex(READ_ITEM),
            "pack_codec": "inventory_pack_codec.unpack_6d3b0 @ +0x2B8",
        },
        "hits": summary.get("hits", []),
        "adb30_calls": len(summary.get("adb", [])),
        "events": events,
        "note": "AE470 fires when [item+0x234]>=0 after load; use --attach with save loaded in-game.",
        "attach_recommended": True,
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} hits={len(summary.get('hits', []))} adb30={report['adb30_calls']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
