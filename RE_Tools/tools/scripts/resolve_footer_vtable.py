"""
Resolve footer / panel vtable slots +0xB0 (write) and +0xB8 (read).

Static: disasm call sites @ Horsey.exe+0x6E0E9, +0x6E112, +0x6EA08
Runtime (optional): --frida logs resolved targets after game init

Output: RE_Tools/analysis/save_footer_vtable.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_64, Cs

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
from paths import get_exe_path, get_game_dir  # noqa: E402

OUT = ROOT / "RE_Tools" / "analysis" / "save_footer_vtable.json"
IMAGE_BASE = 0x140000000

CALL_SITES = {
    "inventory_panel_write_b0": 0x6E0E9,
    "footer_global_write_b0": 0x6E112,
    "footer_global_read_b8": 0x6EA08,
    "inventory_panel_read_b8": None,  # filled by scan
}


def disasm_head(pe, raw: bytes, rva: int, n: int = 24) -> list[str]:
    off = pe.get_offset_from_rva(rva)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    return [
        f"  {i.address - IMAGE_BASE:06X}: {i.mnemonic:8} {i.op_str}"
        for i in md.disasm(raw[off : off + n * 15], IMAGE_BASE + rva)
    ][:n]


def scan_b8_read_sites(pe, raw: bytes) -> list[int]:
    """Find `call qword ptr [rax + 0xb8]` in .text."""
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    hits: list[int] = []
    for sec in pe.sections:
        if sec.Name.rstrip(b"\x00") != b".text":
            continue
        base = sec.VirtualAddress
        data = raw[sec.PointerToRawData : sec.PointerToRawData + sec.SizeOfRawData]
        for ins in md.disasm(data, IMAGE_BASE + base):
            if ins.mnemonic != "call":
                continue
            if "0xb8" in ins.op_str.lower() and "rax" in ins.op_str:
                hits.append(ins.address - IMAGE_BASE)
    return hits


def frida_resolve(seconds: float) -> dict:
    import frida

    device = frida.get_local_device()
    pid = device.spawn([str(get_exe_path())], cwd=str(get_game_dir()))
    session = device.attach(pid)
    agent = r"""
'use strict';
var sites = {
  footer_write_b0: 0x6E112,
  footer_read_b8: 0x6EA08,
  panel_write_b0: 0x6E0E9
};
var out = {};
var base = Process.findModuleByName('Horsey.exe').base;
function hook(name, rva) {
  Interceptor.attach(base.add(rva), {
    onEnter: function () {
      var vt = this.context.rcx.readPointer();
      var fn = vt.add(0xB0).readPointer();
      out[name] = {
        obj: this.context.rcx.toString(),
        vtable: vt.toString(),
        b0: fn.toString(),
        b0_rva: 'Horsey.exe+' + fn.sub(base).toString(16).toUpperCase()
      };
    }
  });
}
hook('footer_write_b0', sites.footer_write_b0);
Interceptor.attach(base.add(sites.footer_read_b8), {
  onEnter: function () {
    var vt = this.context.rcx.readPointer();
    var fn = vt.add(0xB8).readPointer();
    out.footer_read_b8 = {
      obj: this.context.rcx.toString(),
      vtable: vt.toString(),
      b8: fn.toString(),
      b8_rva: 'Horsey.exe+' + fn.sub(base).toString(16).toUpperCase()
    };
  }
});
rpc.exports.result = function () { return out; };
"""
    script = session.create_script(agent)
    script.load()
    device.resume(pid)
    time.sleep(seconds)
    try:
        res = script.exports_sync.result()
    except Exception:
        res = {}
    try:
        session.detach()
    except Exception:
        pass
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frida", action="store_true", help="Resolve vtable targets at runtime")
    ap.add_argument("--seconds", type=float, default=18.0)
    args = ap.parse_args()

    pe = pefile.PE(str(get_exe_path()))
    raw = get_exe_path().read_bytes()
    b8_sites = scan_b8_read_sites(pe, raw)

    report = {
        "global_footer_ptr_rva": "0x31A660",
        "note": (
            "DAT_14031a660 is heap-allocated; static vtable pointer is not in .rdata. "
            "Use --frida after init or disasm the resolved function at the logged RVA."
        ),
        "call_sites": {
            name: {
                "rva": hex(rva) if rva else None,
                "role": desc,
                "disasm": disasm_head(pe, raw, rva) if rva else None,
            }
            for name, rva, desc in [
                (
                    "inventory_panel_write_b0",
                    0x6E0E9,
                    "After WriteNestedSave on ctx panel @ [rdi+0x438]",
                ),
                (
                    "footer_global_write_b0",
                    0x6E112,
                    "After WriteNestedSave(DAT_14031a660) @ 0x6E103",
                ),
                (
                    "footer_global_read_b8",
                    0x6EA08,
                    "After ReadNestedSave(DAT_14031a660) @ 0x6E9F9",
                ),
            ]
        },
        "all_read_b8_call_sites": [hex(x) for x in b8_sites],
        "write_nested_refs": {"write": "0x6D440", "read": "0x6D5C0"},
        "runtime": None,
    }
    report["b0_handler"] = {
        "rva": "0x1017C0",
        "fn": "FooterExtra_Write",
        "wire": [
            "WriteU32 [obj+0x25C] @ 0x6FE10",
            "WriteU8  [obj+0x261..0x263] @ 0x6FEF0",
        ],
        "disasm": disasm_head(pe, raw, 0x1017C0, 12),
        "verified": "Frida @ 0x6E112 → Horsey.exe+0x1017C0",
    }
    report["b8_handler"] = {
        "rva": "0x101810",
        "fn": "FooterExtra_Read",
        "wire": [
            "ReadU32  [obj+0x25C] @ 0x70320",
            "ReadU8×3 [obj+0x261..0x263] @ 0x70620",
        ],
        "disasm": disasm_head(pe, raw, 0x101810, 12),
        "verified": "Frida @ 0x6EA08 → Horsey.exe+0x101810",
    }
    if args.frida:
        report["runtime"] = frida_resolve(args.seconds)

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} b8_sites={len(b8_sites)} frida={bool(args.frida)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
