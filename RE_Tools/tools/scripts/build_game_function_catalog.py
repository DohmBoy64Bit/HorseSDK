"""
Build game_function_catalog.json + refresh GameFunctions.h RVAs from verified seeds.

Sources:
  - Curated seeds (GameLoop.md, Save_Write.md, save_read_write_pairs.json)
  - Optional catalog_seed.json overrides

Output:
  RE_Tools/analysis/game_function_catalog.json
  RE_Tools/docs/GameFunctions.h ( #define block regenerated )

Usage:
  python RE_Tools/tools/scripts/build_game_function_catalog.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AN = ROOT / "RE_Tools" / "analysis"
DOC = ROOT / "RE_Tools" / "docs"
OUT_JSON = AN / "game_function_catalog.json"
OUT_H = DOC / "GameFunctions.h"
OUT_H_SDK = ROOT / "SDK" / "include" / "horse" / "game_functions.h"
OUT_TYPES_SDK = ROOT / "SDK" / "include" / "horse" / "game_function_types.h"
OUT_HOOKS_SDK = ROOT / "SDK" / "include" / "horse" / "game_function_hooks.h"
OUT_HOOKS_JSON = AN / "game_function_hooks.json"

REG_ORDER = ("rcx", "rdx", "r8", "r9")
REG_ALIASES = {"ecx": "rcx", "edx": "rdx", "r8d": "r8", "r9d": "r9"}
PAIRS = AN / "save_read_write_pairs.json"
SEED_EXTRA = AN / "catalog_seed.json"
IMAGE_BASE = 0x140000000


def rva_int(s: str) -> int:
    return int(s, 16)


def va_str(rva: str) -> str:
    return hex(IMAGE_BASE + rva_int(rva))


def fn(
    id_: str,
    name: str,
    rva: str,
    category: str,
    summary: str,
    *,
    status: str = "verified",
    pair_read_rva: str | None = None,
    doc: str | None = None,
    decompile: str | None = None,
    callers: list[str] | None = None,
    globals_: list[dict] | None = None,
    struct_offsets: dict[str, str] | None = None,
    parameters: list[dict] | None = None,
    returns: dict | None = None,
    hook: dict | None = None,
    verification: list[str] | None = None,
) -> dict:
    entry = {
        "id": id_,
        "name": name,
        "rva": rva.lower(),
        "va": va_str(rva),
        "category": category,
        "status": status,
        "summary": summary,
        "calling_convention": "microsoft_x64",
        "verification": verification or ["capstone", "frida"],
    }
    if pair_read_rva:
        entry["pair_read_rva"] = pair_read_rva.lower()
    if doc:
        entry["doc"] = doc
    if decompile:
        entry["decompile"] = decompile
    if callers:
        entry["callers"] = [c.lower() for c in callers]
    if globals_:
        entry["globals"] = globals_
    if struct_offsets:
        entry["struct_offsets"] = struct_offsets
    if parameters:
        entry["parameters"] = parameters
    if returns:
        entry["returns"] = returns
    if hook:
        entry["hook"] = hook
    disasm = AN / f"disasm_{name}.txt"
    if disasm.is_file():
        entry["disasm"] = str(disasm.relative_to(ROOT)).replace("\\", "/")
    return entry


# Verified on Game/Horsey.exe — see linked docs
CURATED: list[dict] = [
    fn(
        "game_main_init_and_loop",
        "GameMain_InitAndLoop",
        "0xBE0F0",
        "loop",
        "SDL init, settings, bootstrap, per-frame loop until quit; calls Save_Write on exit",
        doc="RE_Tools/docs/GameLoop.md",
        decompile="RE_Tools/docs/ghidra_exports/GameMain_InitAndLoop.c.txt",
        callers=["0x21EE0D"],
        verification=["capstone", "frida", "ghidra"],
    ),
    fn(
        "game_dispatch_sdl_event",
        "Game_DispatchSdlEvent",
        "0xC0430",
        "loop",
        "SDL event switch; sets quit/focus flags",
        doc="RE_Tools/docs/Game_DispatchSdlEvent.md",
        decompile="RE_Tools/docs/ghidra_exports/Game_DispatchSdlEvent.c.txt",
    ),
    fn(
        "game_update_world",
        "Game_UpdateWorld",
        "0x87510",
        "world",
        "Window coords → normalized; may call Game_WorldSimStep",
        doc="RE_Tools/docs/Game_UpdateWorld.md",
        decompile="RE_Tools/docs/ghidra_exports/Game_UpdateWorld.c.txt",
    ),
    fn(
        "game_world_sim_step",
        "Game_WorldSimStep",
        "0x88510",
        "world",
        "World sim when window size delta non-zero",
        doc="RE_Tools/docs/Game_WorldSimStep.md",
        status="verified",
    ),
    fn(
        "game_bootstrap_world",
        "Game_BootstrapWorld",
        "0x874B0",
        "world",
        "InitCore → InitRender → LoadAssets → GameState ctor",
        doc="RE_Tools/docs/Game_BootstrapWorld.md",
        decompile="RE_Tools/docs/ghidra_exports/Game_BootstrapWorld.c.txt",
    ),
    fn(
        "clamp_int3",
        "ClampInt3",
        "0xC12D0",
        "loop",
        "int clamp(ecx, edx, r8d) — misnamed Game_SimStep in early notes",
        doc="RE_Tools/docs/ClampInt3.md",
        parameters=[
            {"reg": "ecx", "type": "int", "name": "value"},
            {"reg": "edx", "type": "int", "name": "lo"},
            {"reg": "r8", "type": "int", "name": "hi"},
        ],
        returns={"reg": "eax", "type": "int"},
        hook={"safe_pre_call": True, "notes": "Pure clamp; safe to wrap"},
    ),
    fn(
        "save_write",
        "Save_Write",
        "0x6DAB0",
        "save",
        "Serialize game ctx to heap buffer; flush to save%d.dat",
        doc="RE_Tools/docs/Save_Write.md",
        decompile="RE_Tools/docs/ghidra_exports/Save_Write.c.txt",
        callers=["0x98680", "0x10A2C2", "0x10A822"],
        parameters=[{"reg": "rcx", "type": "void *", "name": "ctx"}],
        hook={"safe_pre_call": True, "notes": "Pre-call: log ctx; avoid re-entrancy"},
        verification=["capstone", "frida", "ghidra"],
    ),
    fn(
        "save_load",
        "Save_Load",
        "0x6E2B0",
        "save",
        "Load save file into ctx (mirror of Save_Write)",
        doc="RE_Tools/docs/SaveLoadPath.md",
        pair_read_rva=None,
        parameters=[{"reg": "rcx", "type": "void *", "name": "ctx"}],
        hook={"safe_pre_call": True, "notes": "Pre-call: backup save path"},
        verification=["capstone", "ghidra"],
    ),
    fn(
        "save_load_from_buffer",
        "Save_LoadFromBuffer",
        "0x6E643",
        "save",
        "Deserialize in-memory save blob into ctx",
        doc="RE_Tools/docs/SaveLoadPath.md",
    ),
    fn(
        "write_flush",
        "WriteFlush",
        "0x6FD90",
        "io",
        "Flush serialize heap buffer to file on disk",
        pair_read_rva=None,
    ),
    fn(
        "write_nested_save",
        "WriteNestedSave",
        "0x6D440",
        "nested",
        "Write nested object: name, ptr/merge/b8 header, b8 blob, tail",
        pair_read_rva="0x6D5C0",
        doc="RE_Tools/docs/SaveNestedFormat.md",
    ),
    fn(
        "read_nested_save",
        "ReadNestedSave",
        "0x6D5C0",
        "nested",
        "Read nested object (pair of WriteNestedSave)",
        doc="RE_Tools/docs/SaveNestedFormat.md",
    ),
    fn(
        "write_nested_item",
        "WriteNestedItem",
        "0x6EC40",
        "nested",
        "Write inline nested item when ptr_item_count > 0",
        pair_read_rva="0x6EF80",
    ),
    fn(
        "read_nested_item",
        "ReadNestedItem",
        "0x6EF80",
        "nested",
        "Read inline nested item",
    ),
    fn(
        "pack_genes",
        "PackGenes_6D2A0",
        "0x6D2A0",
        "save",
        "Pack 0x1E0 diploid bytes → 0xF0 wire gene pack",
        doc="RE_Tools/docs/SaveInventoryRecord.h",
    ),
    fn(
        "unpack_genes",
        "UnpackGenes_6D3B0",
        "0x6D3B0",
        "save",
        "Unpack 0xF0 wire → track A/B allele indices",
        doc="RE_Tools/docs/SaveInventoryRecord.h",
    ),
    fn(
        "type1_b8_write",
        "Type1_B8_Write",
        "0x102DC0",
        "nested",
        "vtable+0x48 type-1 component wire (+0xA0..+0xAC)",
        pair_read_rva="0x102E20",
        doc="RE_Tools/docs/SaveSemantics.md",
    ),
    fn(
        "type1_b8_read",
        "Type1_B8_Read",
        "0x102E20",
        "nested",
        "Read type-1 component wire",
    ),
    fn(
        "footer_extra_write",
        "FooterExtra_Write",
        "0x1017C0",
        "save",
        "vtable+0xB0: u32 @ +0x25C + 3×u8 @ +0x261..0x263",
        pair_read_rva="0x101810",
        doc="RE_Tools/docs/SaveFooterFormat.md",
    ),
    fn(
        "footer_extra_read",
        "FooterExtra_Read",
        "0x101810",
        "save",
        "vtable+0xB8 read footer extra bytes",
    ),
    fn(
        "settings_loader",
        "SettingsLoader",
        "0x711B0",
        "settings",
        "Parse settings.xml + horsey.tmx path",
        doc="RE_Tools/docs/SettingsLoader.md",
        decompile="RE_Tools/docs/ghidra_exports/SettingsLoader.c.txt",
        callers=["0xBE562"],
    ),
    fn(
        "settings_save",
        "Settings_Save",
        "0x71F60",
        "settings",
        "Write settings.xml on quit",
        doc="RE_Tools/docs/Settings_Save.md",
    ),
    fn(
        "font_load_or_init",
        "Font_LoadOrInit",
        "0x7F8A0",
        "font",
        "Load .crf font blobs",
        doc="RE_Tools/docs/FontLoad.md",
    ),
    fn(
        "genetics_apply",
        "GeneticsApply",
        "0xAE470",
        "genetics",
        "Apply unpacked gene pack to horse parts (runtime only)",
        doc="RE_Tools/docs/SaveFutureWork.md",
        status="partial",
        callers=["0xADB30"],
    ),
    fn(
        "genetics_apply_gate",
        "GeneticsApplyGate",
        "0xADB30",
        "genetics",
        "Gate: call GeneticsApply when [item+0x234] >= 0",
        status="partial",
    ),
    fn(
        "g_game_state",
        "g_game_state",
        "0x313720",
        "other",
        "Global pointer to main game state (DATA)",
        doc="RE_Tools/docs/g_game_state.md",
        status="verified",
    ),
    fn(
        "gain_money",
        "GainMoney",
        "0x10AB80",
        "economy",
        "void GainMoney(ctx, int amount, char show_ui): [ctx+0x308]+=amount; [ctx+0x30c]=0x3c",
        status="verified",
        decompile="RE_Tools/docs/ghidra_exports/GainMoney.c.txt",
        parameters=[
            {"reg": "rcx", "type": "void *", "name": "ctx"},
            {"reg": "edx", "type": "int", "name": "amount"},
            {"reg": "r8", "type": "char", "name": "show_ui"},
        ],
        struct_offsets={
            "ctx+0x308": "money",
            "ctx+0x30c": "money_ui_timer",
            "ctx+0x310": "last_delta",
        },
        hook={"safe_pre_call": True, "notes": "UI feedback on credit"},
        verification=["capstone", "ghidra"],
    ),
    fn(
        "sim_spawn_disk",
        "SimSpawnDisk",
        "0x33A20",
        "spawn",
        "Large spawn handler; string 'SimSpawnDisk' @ 0x342F0 inside body",
        status="partial",
        decompile="RE_Tools/docs/ghidra_exports/SimSpawnDisk.c.txt",
        verification=["ghidra"],
    ),
    fn(
        "spawn_entity",
        "SpawnEntity",
        "0x30492",
        "spawn",
        "Calls SpawnPlace @ 0x32330 (E8 @ 0x30B52); Frida-verified path",
        status="partial",
        verification=["capstone", "frida"],
    ),
    fn(
        "spawn_place",
        "SpawnPlace",
        "0x32330",
        "spawn",
        "SimSpawnDisk callee; sole E8 target from 0x30B52",
        status="partial",
        verification=["capstone"],
    ),
    fn(
        "grab_horse",
        "GrabHorse",
        "0xD6340",
        "horse",
        "Grab/place horse; GrabHorse string @ 0xD9158 in body (not 0xD71DF)",
        status="partial",
        verification=["capstone", "frida"],
    ),
    fn(
        "drop_horse_fail",
        "DropHorseFail",
        "0xD3C50",
        "horse",
        "Failed horse drop on invalid tile",
        status="partial",
        verification=["string_xref"],
    ),
    fn(
        "spend_money",
        "SpendMoney",
        "0x10AC60",
        "economy",
        "Debit [ctx+0x308]; shop (BuyItem) + race betting",
        status="verified",
        verification=["ghidra", "frida"],
        struct_offsets={
            "ctx+0x308": "money",
            "ctx+0x30c": "money_ui_timer",
            "ctx+0x310": "last_delta",
        },
        parameters=[
            {"reg": "rcx", "type": "void *", "name": "ctx"},
            {"reg": "edx", "type": "int", "name": "cost"},
        ],
        hook={"safe_pre_call": True, "notes": "Shop/race betting debit"},
    ),
    fn(
        "buy_item",
        "BuyItem",
        "0x787D0",
        "shop",
        "Shop buy / dialog dispatch; string 'BuyItem' @ ~0x78B00",
        status="partial",
        decompile="RE_Tools/docs/ghidra_exports/BuyItem.c.txt",
        verification=["ghidra"],
    ),
    fn(
        "race_state_machine",
        "RaceStateMachine",
        "0x8F2B0",
        "race",
        "Race UI FSM; xrefs RaceGo/WonRace/OnYourMark @ 0x90E00-0x92000",
        status="partial",
        decompile="RE_Tools/docs/ghidra_exports/Race_91148.c.txt",
        verification=["ghidra"],
    ),
    fn(
        "sim_message_dispatch",
        "SimMessageDispatch",
        "0x5E0C2",
        "race",
        "Sim tag dispatch hub; SimStartRace string @ 0x5F372; E8 into 0x5F000 region",
        status="partial",
        doc="RE_Tools/docs/SimStartRace.md",
        verification=["capstone", "e8_scan"],
    ),
    fn(
        "sim_rand_mod",
        "SimRandMod",
        "0xC1900",
        "race",
        "PRNG: state @ 0x3128D8; returns edx % ecx; range overload @ 0xC1940",
        status="partial",
        doc="RE_Tools/docs/RaceMechanics.md",
        parameters=[{"reg": "ecx", "type": "int", "name": "modulus"}],
        returns={"reg": "eax", "type": "int"},
        verification=["capstone"],
    ),
    fn(
        "race_advance_sim",
        "RaceAdvanceSim",
        "0x8C9E0",
        "race",
        "Per-frame race sim: 0x70-byte slots @ ctx+0x280, updates horse+0x220 speed",
        status="partial",
        doc="RE_Tools/docs/RaceMechanics.md",
        parameters=[{"reg": "rcx", "type": "void *", "name": "race_ctx"}],
        hook={"safe_pre_call": True, "notes": "Hot path; throttle logging"},
        verification=["capstone", "ghidra"],
    ),
    fn(
        "race_update_horses",
        "RaceUpdateHorses",
        "0x8CC10",
        "race",
        "Called from RaceStateMachine each tick with RaceAdvanceSim",
        status="partial",
        doc="RE_Tools/docs/RaceMechanics.md",
        verification=["ghidra"],
    ),
    fn(
        "race_phase_dispatch",
        "RacePhaseDispatch",
        "0x8A7F0",
        "race",
        "Race phase transitions (OnYourMark / Racing / finish)",
        status="partial",
        doc="RE_Tools/docs/RaceMechanics.md",
        verification=["ghidra"],
    ),
    fn(
        "horse_race_score",
        "HorseRaceScore",
        "0xE2B80",
        "race",
        "void HorseRaceScore(ctx, horse_idx): (rand+nice+record)*years+deco -> [ctx+0x450]; vtable@0x267368[0]",
        status="partial",
        decompile="RE_Tools/docs/ghidra_exports/HorseRaceScore.c.txt",
        doc="RE_Tools/docs/RaceMechanics.md",
        parameters=[
            {"reg": "rcx", "type": "void *", "name": "race_ctx"},
            {"reg": "edx", "type": "int", "name": "horse_index"},
        ],
        verification=["capstone"],
    ),
    fn(
        "race_sim_handler",
        "RaceSimHandler",
        "0x5F020",
        "race",
        "SimStartRace post @ 0x5F365 when [ctx+0xE0]==7; sets [ctx+0x258]=1",
        status="partial",
        decompile="RE_Tools/docs/ghidra_exports/RaceSimHandler.c.txt",
        doc="RE_Tools/docs/RaceMechanics.md",
        verification=["capstone"],
    ),
    fn(
        "race_sim_object_init",
        "RaceSimObject_Init",
        "0x5F900",
        "race",
        "Race sim object ctor (arrays @ +0x278); not the SimStartRace message handler",
        status="partial",
        doc="RE_Tools/docs/RaceMechanics.md",
        verification=["capstone"],
    ),
    fn(
        "sim_post_message",
        "SimPostMessage",
        "0xD6DF0",
        "race",
        "Post sim tag message; strcmp dispatch (Rabbit, Graffe, ...)",
        status="partial",
        doc="RE_Tools/docs/RaceMechanics.md",
        verification=["capstone"],
    ),
    fn(
        "sim_rand_seed",
        "SimRandSeedFromFloat",
        "0xC2080",
        "race",
        "Seed g_prng_state @ 0x2F2700 from float vector",
        status="partial",
        decompile="RE_Tools/docs/ghidra_exports/SimRandSeed.c.txt",
        doc="RE_Tools/docs/RaceMechanics.md",
        verification=["capstone"],
    ),
]


def merge_pairs(catalog: dict[str, dict]) -> None:
    if not PAIRS.is_file():
        return
    data = json.loads(PAIRS.read_text(encoding="utf-8"))
    for p in data.get("pairs", []):
        w = p.get("write_rva")
        r = p.get("read_rva")
        nm = p.get("name", "").replace("/", "_").replace(" ", "_")
        if not w:
            continue
        id_ = re.sub(r"[^a-z0-9_]", "_", nm.lower())
        if id_ in catalog:
            continue
        catalog[id_] = fn(
            id_,
            nm,
            w,
            "io",
            p.get("note") or f"Save stream primitive size={p.get('size')}",
            pair_read_rva=r,
            doc="RE_Tools/analysis/save_read_write_pairs.json",
        )
    for name, spec in data.get("top_level", {}).items():
        rva = spec.get("rva")
        if not rva:
            continue
        id_ = re.sub(r"[^a-z0-9_]", "_", name.lower())
        if id_ in catalog:
            continue
        catalog[id_] = fn(
            id_,
            name,
            rva,
            "save",
            spec.get("role") or spec.get("note") or name,
            doc="RE_Tools/docs/SaveGhidraCrossref.md",
        )


def write_header(functions: list[dict]) -> None:
    lines = [
        "/**",
        " * Horsey.exe — verified RVAs for SDK hooks (auto-generated).",
        " *",
        " * Image base: 0x140000000",
        " * Regenerate: python RE_Tools/tools/scripts/build_game_function_catalog.py",
        " *",
        " * Do not edit by hand.",
        " */",
        "#ifndef HORSE_GAME_FUNCTIONS_H",
        "#define HORSE_GAME_FUNCTIONS_H",
        "",
        "#include <stdint.h>",
        "",
        "#ifdef __cplusplus",
        'extern "C" {',
        "#endif",
        "",
        "#define HORSE_IMAGE_BASE 0x140000000ULL",
        "#define HORSE_RVA_TO_VA(rva) ((void *)(HORSE_IMAGE_BASE + (uint32_t)(rva)))",
        "",
        "static inline void *horse_rva(const void *module_base, uint32_t rva) {",
        "    return (uint8_t *)module_base + rva;",
        "}",
        "",
    ]
    by_cat: dict[str, list] = {}
    for f in functions:
        if f["name"].startswith("g_") and f["category"] == "other":
            by_cat.setdefault("globals", []).append(f)
        else:
            by_cat.setdefault(f["category"], []).append(f)
    order = [
        "loop",
        "economy",
        "spawn",
        "shop",
        "race",
        "horse",
        "breeding",
        "save",
        "io",
        "nested",
        "settings",
        "world",
        "font",
        "genetics",
        "render",
        "other",
        "globals",
    ]
    for cat in order:
        group = by_cat.get(cat)
        if not group:
            continue
        lines.append(f"/* --- {cat} --- */")
        by_name: dict[str, dict] = {}
        for f in group:
            nm = f["name"]
            prev = by_name.get(nm)
            if prev is None or _prefer_catalog_entry(f, prev):
                by_name[nm] = f
        for f in sorted(by_name.values(), key=lambda x: x["name"]):
            rva = rva_int(f["rva"])
            macro = re.sub(r"[^A-Za-z0-9_]", "_", f["name"])
            lines.append(f"#define HORSE_RVA_{macro:<32} 0x{rva:08X}u")
        lines.append("")
    lines.extend(
        [
            "#ifdef __cplusplus",
            "}",
            "#endif",
            "",
            "#endif /* HORSE_GAME_FUNCTIONS_H */",
            "",
        ]
    )
    text = "\n".join(lines)
    OUT_H.write_text(text, encoding="utf-8")
    OUT_H_SDK.parent.mkdir(parents=True, exist_ok=True)
    OUT_H_SDK.write_text(text, encoding="utf-8")


def _norm_reg(reg: str) -> str:
    return REG_ALIASES.get(reg.lower(), reg.lower())


def _param_sort_key(param: dict) -> int:
    try:
        return REG_ORDER.index(_norm_reg(param["reg"]))
    except ValueError:
        return 99


def write_types_header(functions: list[dict]) -> None:
    lines = [
        "/**",
        " * Typed function pointers (microsoft x64) from catalog parameters.",
        " * Regenerate: python RE_Tools/tools/scripts/build_game_function_catalog.py",
        " */",
        "#ifndef HORSE_GAME_FUNCTION_TYPES_H",
        "#define HORSE_GAME_FUNCTION_TYPES_H",
        "",
        '#include "horse/game_functions.h"',
        '#include "horse/module.h"',
        "",
        "#ifdef __cplusplus",
        'extern "C" {',
        "#endif",
        "",
    ]
    for f in sorted(functions, key=lambda x: x["name"]):
        params = f.get("parameters")
        if not params:
            continue
        macro = re.sub(r"[^A-Za-z0-9_]", "_", f["name"])
        sorted_params = sorted(params, key=_param_sort_key)
        arg_list = ", ".join(f"{p['type']} {p['name']}" for p in sorted_params)
        ret = f.get("returns", {}).get("type", "void")
        lines.append(f"typedef {ret} (*HORSE_FN_{macro})({arg_list});")
        lines.append(
            f"#define HORSE_PTR_{macro}(base) "
            f"((HORSE_FN_{macro})horse_module_rva((base), HORSE_RVA_{macro}))"
        )
        lines.append("")
    lines.extend(
        [
            "#ifdef __cplusplus",
            "}",
            "#endif",
            "",
            "#endif /* HORSE_GAME_FUNCTION_TYPES_H */",
            "",
        ]
    )
    OUT_TYPES_SDK.parent.mkdir(parents=True, exist_ok=True)
    OUT_TYPES_SDK.write_text("\n".join(lines), encoding="utf-8")


def write_hooks_artifacts(functions: list[dict]) -> None:
    hooked = [f for f in functions if f.get("hook")]
    hooks_json = {
        "schema": "horse_hook_catalog_v1",
        "image_base": hex(IMAGE_BASE),
        "hooks": [
            {
                "id": f["id"],
                "name": f["name"],
                "rva": f["rva"],
                "safe_pre_call": bool(f["hook"].get("safe_pre_call")),
                "notes": f["hook"].get("notes", ""),
            }
            for f in sorted(hooked, key=lambda x: x["rva"])
        ],
    }
    OUT_HOOKS_JSON.write_text(json.dumps(hooks_json, indent=2), encoding="utf-8")

    lines = [
        "/**",
        " * Hook catalog for mod loader (Phase 4).",
        " * Regenerate: python RE_Tools/tools/scripts/build_game_function_catalog.py",
        " */",
        "#ifndef HORSE_GAME_FUNCTION_HOOKS_H",
        "#define HORSE_GAME_FUNCTION_HOOKS_H",
        "",
        '#include "horse/game_functions.h"',
        "#include <stddef.h>",
        "#include <stdint.h>",
        "",
        "#ifdef __cplusplus",
        'extern "C" {',
        "#endif",
        "",
        "typedef struct HorseHookCatalogEntry {",
        "    const char *id;",
        "    const char *name;",
        "    uint32_t rva;",
        "    uint8_t safe_pre_call;",
        "    const char *notes;",
        "} HorseHookCatalogEntry;",
        "",
        "static const HorseHookCatalogEntry g_horse_hook_catalog[] = {",
    ]
    for f in hooks_json["hooks"]:
        notes = f["notes"].replace("\\", "\\\\").replace('"', '\\"')
        rva = rva_int(f["rva"])
        lines.append(
            f'    {{ "{f["id"]}", "{f["name"]}", 0x{rva:08X}u, '
            f'{1 if f["safe_pre_call"] else 0}, "{notes}" }},'
        )
    lines.extend(
        [
            "};",
            "",
            "#define HORSE_HOOK_CATALOG_COUNT "
            f"(sizeof(g_horse_hook_catalog) / sizeof(g_horse_hook_catalog[0]))",
            "",
            "#ifdef __cplusplus",
            "}",
            "#endif",
            "",
            "#endif /* HORSE_GAME_FUNCTION_HOOKS_H */",
            "",
        ]
    )
    OUT_HOOKS_SDK.parent.mkdir(parents=True, exist_ok=True)
    OUT_HOOKS_SDK.write_text("\n".join(lines), encoding="utf-8")


def _prefer_catalog_entry(a: dict, b: dict) -> bool:
    """True if a should replace b for header / display."""

    def rank(f: dict) -> tuple:
        return (
            0 if f.get("status") == "verified" else 1,
            0 if f.get("decompile") else 1,
            0 if f.get("parameters") else 1,
            -len(f.get("summary", "")),
        )

    return rank(a) < rank(b)


def _catalog_key_for_name(catalog: dict[str, dict], name: str) -> str | None:
    for key, entry in catalog.items():
        if entry.get("name") == name:
            return key
    return None


def merge_gameplay(catalog: dict[str, dict]) -> None:
    gp = AN / "gameplay_functions.json"
    if not gp.is_file():
        return
    data = json.loads(gp.read_text(encoding="utf-8"))
    for f in data.get("functions", []):
        name = f.get("name") or f.get("name_guess")
        if not name or name == "unknown":
            continue
        if _catalog_key_for_name(catalog, name):
            continue
        id_ = re.sub(r"[^a-z0-9_]", "_", name.lower())
        if id_ in catalog:
            continue
        rva = f.get("rva", "0")
        catalog[id_] = fn(
            id_,
            name if not name.endswith("_dispatch") else name.replace("_dispatch", ""),
            rva,
            f.get("category", "gameplay"),
            f.get("summary", ""),
            status=f.get("status", "partial"),
            doc="RE_Tools/docs/GameplayFunctions.md",
            callers=[c.lower() for c in f.get("callers", [])] if f.get("callers") else None,
            struct_offsets=f.get("struct_offsets"),
            verification=f.get("verification", ["string_xref"]),
        )


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--gameplay", action="store_true", help="Merge gameplay_functions.json")
    args = ap.parse_args()

    catalog: dict[str, dict] = {e["id"]: e for e in CURATED}
    if SEED_EXTRA.is_file():
        for e in json.loads(SEED_EXTRA.read_text(encoding="utf-8")).get("functions", []):
            catalog[e["id"]] = e
    merge_pairs(catalog)
    if args.gameplay:
        merge_gameplay(catalog)
    functions = sorted(catalog.values(), key=lambda x: (x["category"], x["rva"]))
    verified = sum(1 for f in functions if f["status"] == "verified")
    report = {
        "image_base": hex(IMAGE_BASE),
        "exe": "Game/Horsey.exe",
        "schema_doc": "RE_Tools/docs/GameFunctionCatalog.md",
        "summary": {
            "total": len(functions),
            "verified_count": verified,
            "partial_count": sum(1 for f in functions if f["status"] == "partial"),
            "stub_count": sum(1 for f in functions if f["status"] == "stub"),
            "by_category": {},
        },
        "functions": functions,
    }
    for f in functions:
        c = f["category"]
        report["summary"]["by_category"][c] = report["summary"]["by_category"].get(c, 0) + 1
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_header(functions)
    write_types_header(functions)
    write_hooks_artifacts(functions)
    print(f"Wrote {OUT_JSON} functions={len(functions)} verified={verified}")
    print(f"Wrote {OUT_H}")
    print(f"Wrote {OUT_H_SDK}")
    print(f"Wrote {OUT_TYPES_SDK}")
    print(f"Wrote {OUT_HOOKS_SDK}")
    print(f"Wrote {OUT_HOOKS_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
