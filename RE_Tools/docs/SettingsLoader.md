# `SettingsLoader` @ `0x711B0`

**Ghidra:** `FUN_1400711b0` · **Caller:** `GameMain_InitAndLoop` @ **`0xBE562`**  
**Span:** `0x711B0`–`0x71F22` (`ret` @ `0x71F22`)  
**Raw listing:** [`ghidra_exports/SettingsLoader.c.txt`](ghidra_exports/SettingsLoader.c.txt)

Loads **`settings.xml`** and **`horsey.tmx`** (string cluster @ **`0x262450`** / exe xrefs `0x263850`, `0x263860`), parses XML into globals under **`0x2F14xx`**, then returns.

**Adjacent @ `0x71F60`:** `FUN_140071f60` — **settings/XML write on quit** (`GameMain` @ `0xBED11`). **Not** game save serializer (`Save_Write` is @ **`0x6DAB0`**).

---

## High-level flow

```c
void SettingsLoader(void) {
    // 1) Default globals @ 0x2F14C0..0x2F1584
    g_fullscreen_init = r12b;          // 0x2F14CC
    dword@0x2F14C4 = dword@0x2F14C8 = 100;  // 0x64 default?
    g_vsync_flags = 0x10101;           // 0x2F14E0
    word@0x2F14EA = 0x100;             // g_render_ok baseline

    // 2) PathJoin paths (0x027F70) — game root + filenames
  PathJoin(..., "settings.xml");
  PathJoin(..., "horsey.tmx");

    // 3) Open/read XML buffer (0x0BFB60, 0x025F20, 0x025340)
    if (!open_settings_buffer()) throw;

    // 4) For each XML key: Settings_ParseXmlKey @ 0x072280
    //    Value '1' / '0' (cmp 0x31 / 0x30) -> byte/dword flags

    // 5) Post-parse patches
    if (g_autoload_flag) { ... PathJoin; dword@0x2F1550 = 1000; }
    if (g_autosave_flag) { ... dword@0x2F1550 = -1; }

    if (g_escquits) g_vsync_word = 1;    // 0x2F14E4

    // Clears loop quit during load:
    g_loop_quit = 0;                   // 0x2F14EB @ 0x71DF6

    return;
}
```

---

## `settings.xml` keys (exe string table @ `0x262470`+)

Verified in `Game/Horsey.exe` inside this function’s RIP refs:

| Key | Globals / effect (from Ghidra branches) |
|-----|----------------------------------------|
| `settings.xml` | File path |
| `horsey.tmx` | Map path |
| `fullscreen` | `byte@0x2F14CC` (also `0x30` prefix check @ 0x7158A) |
| `winx`, `winy`, `winw`, `winh` | Window rect → `0x2F14C4` etc. via `0x0257750` |
| `volume`, `sound` | Audio levels |
| `vsync` | `byte@0x2F14E1`, `SDL_GL_SetSwapInterval` path in GameMain |
| `hidpi` | HiDPI flag |
| `savesettings` | `byte@0x2F1558` |
| `escquits` | Escape quits |
| `autosave` / `autoload` | `0x2F1550` timer (-1 or 1000) |
| `ship`, `test`, `map`, `loc`, `labpop`, `money`, `horses`, `inv`, `tut` | Gameplay / UI toggles via `0x072280` |
| **`seed`** | **`g_settings_seed`** @ **`0x2F1587`** — `Settings_ApplyValue` @ **`0x71BCE`** |
| **`log_races`** | Enables race score debug `printf` @ `0xE3021` (see [RaceMechanics.md](RaceMechanics.md)) |

Parser helper: **`Settings_ParseXmlKey` @ `0x72280`** (15× in function).  
String intern/copy: **`FUN_140027e50`**.  
Apply numeric/bool: **`FUN_140025750`**, **`FUN_1400256f0`**.

### Seed and PRNG

| Global | RVA | Role |
|--------|-----|------|
| `g_settings_seed` | `0x2F1587` | Written when XML key `seed` is parsed |
| `g_prng_state` | `0x2F2700` | `SimRandMod` @ `0xC1900` state qword |

Static RIP **read** of `g_settings_seed` not found; PRNG reseed uses `SimRandSeedFromFloat` @ `0xC2080`. Details: [RaceMechanics.md](RaceMechanics.md), [ghidra_exports/SimRandSeed.c.txt](ghidra_exports/SimRandSeed.c.txt).

---

## Globals cluster (`0x2F14C0`–`0x2F14EB`)

| RVA | Ghidra | Role |
|-----|--------|------|
| `0x2F14CC` | `DAT_1402f14cc` | Fullscreen / size-init gate (used in SDL dispatch + loop) |
| `0x2F14C0` | `DAT_1402f14c0` | Settings flag (cleared when `fullscreen` xml = `0`) |
| `0x2F14C4`/`C8` | | Default **100** (`0x64`) before XML |
| `0x2F14D0` | | Cleared xmm block |
| `0x2F14E0` | | `0x10101` — vsync-related |
| `0x2F14E1`–`E5` | | Per-key bytes from XML `'1'`/`'0'` |
| `0x2F14EA` | | **`g_render_ok`** — word `0x100` @ init; cleared @ `0x71DBE` on parse |
| `0x2F14EB` | | **`g_loop_quit`** — **cleared to 0** @ `0x71DF6` after parse |
| `0x2F14EC` | | Byte flag @ `0x71286` |
| `0x2F1550`/`554`/`558` | | Autosave/autoload timing |
| `0x2F1559`–`55B` | | More XML-derived bytes |

---

## Callees (Capstone summary)

| RVA | Suggested name | Count |
|-----|----------------|-------|
| `0x72280` | `Settings_ParseXmlKey` | 15 |
| `0x256F0` | `Xml_NextNode` | 9 |
| `0x25750` | `Settings_ApplyValue` | 9 |
| `0x27E50` | `StdString_FromCStr` | 9 |
| `0x27F70` | `PathJoin` | 6 |
| `0xC12D0` | `Game_SimStep` | 2 (during load) |
| `0xBFB60` | `File_ReadToBuffer` | 1 |

---

## Ghidra renames

| From | To |
|------|-----|
| `FUN_1400711b0` | `SettingsLoader` |
| `FUN_140072280` | `Settings_ParseXmlKey` |
| `FUN_140071f60` | `Save_Write` (separate, @ `0x71F60`) |

---

## Still open

- [ ] Map each `0x072280` call site → exact XML tag name (Ghidra decompiler or xref strings)
- [ ] Confirm `horsey.tmx` load path after XML (may be inside `0x025F20` chain)
- [ ] Decompile `FUN_140025340` / `FUN_140025F20` (XML open)
