# How we built the Horsey Steam API stub (for AI / maintainers)

**Scope:** HorseSDK `steam_bypass/` only — minimal replacement `steam_api64.dll` for **Horsey Game** (`Horsey.exe`) so local modding / RE works **without the Steam client**.

**Not in scope:** Generic Steam cracking, `steamclient64.dll` emulation, depot unlock, or instructions for other titles.

**Legal:** Use only with a legitimate copy of Horsey Game. This repo does not ship `Horsey.exe`, the Steamworks SDK, or Valve binaries.

**Quick reference:** [README.md](README.md) · implementation [`src/steam_api64.cpp`](src/steam_api64.cpp) · build [`build.bat`](build.bat) · exports [`exports.def`](exports.def)

---

## What we built (one sentence)

A **10-export** x64 DLL that satisfies `Horsey.exe`’s import table and returns **fake COM vtables** for three Steam interface version strings the game requests at runtime.

---

## Prerequisites (repo layout)

```
HorseSDK/
  Game/Horsey.exe          # gitignored; you provide
  Game/data/ Game/save/
  steam_bypass/            # this project
  RE_Tools/tools/scripts/phase1_verify.py
```

Offline play requires `Game/steam_api64.dll` (stub) + `Game/steam_appid.txt` next to `Horsey.exe`.

---

## Phase 1 — Discover what the game actually imports

**Goal:** Export list must match the PE import table **exactly** (names + calling convention). Extra exports are fine; **missing** exports = load failure.

### 1.1 List `steam_api64.dll` imports

Tool: `pefile` (used in `RE_Tools/tools/scripts/phase1_verify.py`).

**Horsey result (verified May 2026):** exactly **10** symbols:

| Import |
|--------|
| `SteamAPI_Shutdown` |
| `SteamAPI_RegisterCallback` |
| `SteamAPI_ManualDispatch_Init` |
| `SteamInternal_SteamAPI_Init` |
| `SteamInternal_ContextInit` |
| `SteamAPI_RunCallbacks` |
| `SteamInternal_FindOrCreateUserInterface` |
| `SteamAPI_UnregisterCallback` |
| `SteamAPI_GetHSteamUser` |
| `SteamAPI_RestartAppIfNecessary` |

Recorded in: `RE_Tools/analysis/phase1_verify.txt` (section `Steam imports`).

```bat
python RE_Tools\tools\scripts\phase1_verify.py
```

### 1.2 Find interface version strings

Search `.rdata` / repomix / Ghidra for strings passed to `SteamInternal_FindOrCreateUserInterface`.

**Horsey strings:**

| Interface version | Call site RVA (in `Horsey.exe`) |
|-------------------|----------------------------------|
| `STEAMUSERSTATS_INTERFACE_VERSION013` | `0x379D8` |
| `STEAMAPPS_INTERFACE_VERSION008` | `0xC09B8` |
| `SteamUtils010` | `0xC09E2` |

### 1.3 Map init / shutdown flow in the exe

Documented in [RE_Tools/docs/GameMain_InitAndLoop.md](../RE_Tools/docs/GameMain_InitAndLoop.md).

| RVA | API / behavior |
|-----|----------------|
| `0xBE0F0` | Main game init entry |
| `0xBE106` | `SteamAPI_RestartAppIfNecessary` — immediate `appId = 0x36F88B` (3602571) |
| `0xBE74A` | `SteamInternal_SteamAPI_Init` — `RCX` → `"SteamUtils010"` |
| `0xBE762`+ | `SteamInternal_ContextInit` + indirect vtable calls on utils |
| `0xBEA7F` | `SteamAPI_RunCallbacks` (main loop) |
| `0xBED1F` | `SteamAPI_Shutdown` |

**Stub implication:**

- `SteamAPI_RestartAppIfNecessary` → return **`false`** (game must not exit to relaunch Steam).
- `SteamInternal_SteamAPI_Init` → return **`true`** (game must not take “init failed” path).

### 1.4 Note app ID sources

| Source | Value |
|--------|--------|
| `steam_bypass/steam_appid.txt` | `3602570` |
| `SteamAPI_RestartAppIfNecessary` immediate @ `0xBE106` | `3602571` |
| Prior RE / `ColdClientLoader.ini` in repomix | `3602570` |

Ship `steam_appid.txt` with **3602570**. The restart stub ignores the argument anyway.

### 1.5 Optional: achievement / stats usage

Strings in binary (repomix / x64dbg dump):

- `"Cheevo %s not found!"` @ RVA `0x25D910`
- `"got cheevo: %s"` @ RVA `0x25D928`

→ Implement **UserStats** vtable slots for request/set/get/store, not just “return true” on init.

---

## Phase 2 — Choose stub strategy

| Approach | Horsey choice |
|----------|----------------|
| **A. Minimal `steam_api64.dll` stub** (this repo) | **Yes** — 10 exports, fake vtables |
| **B. Official `steam_api64.dll` + Cold Client + `steamclient64.dll`** | Documented as alternative in [README.md](README.md); heavier, not default for SDK work |

Rule: **only implement what imports + call sites require.** Do not clone full Steamworks.

---

## Phase 3 — Implement `steam_api64.dll`

### 3.1 File roles

| File | Role |
|------|------|
| [`src/steam_api64.cpp`](src/steam_api64.cpp) | All export implementations + vtables |
| [`exports.def`](exports.def) | Linker export names (must match import table) |
| [`build.bat`](build.bat) | `g++ -shared` → `build/steam_api64.dll` → copy to `../Game/` |
| [`steam_appid.txt`](steam_appid.txt) | `3602570` |

### 3.2 Flat exports (non-vtable)

Implement in `extern "C"` with `__declspec(dllexport)`:

```cpp
SteamAPI_RestartAppIfNecessary(uint32_t)  → false
SteamInternal_SteamAPI_Init(const char*) → true; initVtables()
SteamAPI_GetHSteamUser()                → 1
SteamAPI_RegisterCallback / Unregister  → no-op, return 1
SteamAPI_RunCallbacks / Shutdown / ManualDispatch_Init → no-op
```

### 3.3 Interface objects (`SteamInternal_FindOrCreateUserInterface`)

Horsey passes a **version string**; return a pointer to a small struct whose **first member is `void** vtable`** (COM layout).

```cpp
struct SteamIface { void** vtable; };
```

Match strings **exactly** (see Phase 1.2). Unknown string → `nullptr`.

### 3.4 Vtable calling convention (x64 Windows)

Steam interface methods use **`__fastcall`**: `this` in `RCX`, then user args.

Pattern in stub:

1. Allocate `VTable<N>` — array of function pointers.
2. `fillFalse()` — every slot → `StubFalse` (safe default).
3. `set(index, &StubX)` — patch only indices proved by disasm or SDK headers.

**Horsey patches:**

**ISteamUserStats v013** (`g_userStatsVt`, 48 slots):

| Index | Method (Steamworks layout) | Stub |
|-------|----------------------------|------|
| 0 | `RequestCurrentStats` | always `true` |
| 7 | `SetAchievement` | always `true` |
| 8 | `GetAchievement` | `true`, `*achieved = false` |
| 11 | `StoreStats` | always `true` |

**ISteamApps v008** (`g_appsVt`, 32 slots):

| Index | Method | Stub |
|-------|--------|------|
| 0 | `BIsSubscribed` | `true` |
| 5 | `BIsSubscribedApp` | `true` |

**ISteamUtils v010** (`g_utilsVt`, 40 slots):

| Index | Why | Stub |
|-------|-----|------|
| 5 | `BIsSteamRunning` (typical) | `true` |
| 10 | Called @ vtable `+0x50` (RVA `0xBE773`) | no-op `StubVoid` |
| 34 | Called @ vtable `+0x110` (RVA `0xBE789`) | `true` |
| 3 | `GetAppID` fallback | `3602570` |
| 0 | generic | `StubZero` |

### 3.5 `SteamInternal_ContextInit`

Horsey does: `return value → [rax] → inner iface → vtable → call [rax+offset]`.

Return address of a **holder** whose first field points at `g_utils`:

```cpp
struct ContextHolder { SteamIface* iface; };
static ContextHolder g_utilsHolder = { &g_utils };
```

See RVAs `0xBE76D`, `0x376AF` in source comments.

### 3.6 `DllMain`

On `DLL_PROCESS_ATTACH`: `DisableThreadLibraryCalls`, `initVtables()` once.

---

## Phase 4 — Build and deploy

```bat
cd steam_bypass
build.bat
```

`build.bat`:

1. `g++ -shared` `src/steam_api64.cpp` + `exports.def`
2. Output: `build/steam_api64.dll`
3. Copy DLL + `steam_appid.txt` → `../Game/`

Run game from `Game/` (cwd matters for `data/`, `save/`).

---

## Phase 5 — Verify

### 5.1 Automated

```bat
python RE_Tools\tools\scripts\phase1_verify.py
```

Check `RE_Tools/analysis/phase1_verify.txt` — Steam import list + call-site RVAs.

### 5.2 Manual smoke test

1. Close Steam client (optional; stub should not need it).
2. Launch `Game\Horsey.exe`.
3. Expect: no instant exit from `RestartAppIfNecessary`; window stays up.
4. If crash: note **crash RVA** in x64dbg — usually a **vtable index** missing a stub.

### 5.3 Export sanity

Stub DLL should expose **~10** exports only (not 1000+ like real Steamworks redist).

Use `dumpbin /exports Game\steam_api64.dll` or RE_Tools PE scripts.

---

## Phase 6 — Troubleshooting (Horsey-specific)

| Symptom | Likely cause | Fix |
|---------|----------------|-----|
| “Failed to load steam_api64.dll” / missing export | `exports.def` ≠ game imports | Re-run Phase 1.1, sync `exports.def` |
| Instant exit on start | `RestartAppIfNecessary` returns `true` | Return `false` |
| Exit after init | `SteamInternal_SteamAPI_Init` returns `false` | Return `true` |
| Crash @ `0xBE773` / `0xBE789` | Utils vtable slot wrong | Patch indices 10 / 34 (see 3.4) |
| Crash on achievement | UserStats slot missing | Patch indices 0, 7, 8, 11 |
| “Not subscribed” / license check | Apps vtable | Patch indices 0, 5 → `true` |
| Wrong app id in logs | `GetAppID` stub | Return `3602570` |

After game updates: **re-run Phase 1** — imports and interface strings can change.

---

## Phase 7 — How this fits HorseSDK

| Consumer | Why stub exists |
|----------|-----------------|
| Phase 1 RE (`phase1_verify.py`, Frida, Ghidra) | Run exe without Steam for hours-long sessions |
| Mod loader / `horse_inject.exe` | Same `Game/` folder as `Horsey.exe` |
| Docs | [ReverseEngineeringProgress.md](../RE_Tools/docs/ReverseEngineeringProgress.md) · [GameMain_InitAndLoop.md](../RE_Tools/docs/GameMain_InitAndLoop.md) |

**Do not** commit Valve’s real `steam_api64.dll` or Steamworks SDK into git.

---

## Checklist for another AI maintaining the stub

- [ ] Confirm `Game/Horsey.exe` import table still has exactly the 10 symbols above
- [ ] Re-scan for new `SteamInternal_FindOrCreateUserInterface` version strings
- [ ] Disasm any new `call [rax+NN]` on utils/userStats/apps after game patch
- [ ] Update vtable indices in `src/steam_api64.cpp` only with evidence (RVA or official SDK header)
- [ ] Rebuild with `build.bat`, redeploy to `Game/`
- [ ] Run `phase1_verify.py` + short launch test
- [ ] Update [README.md](README.md) if imports or app id changed

---

## Related files (read in order)

1. [README.md](README.md) — operator quick start  
2. [`src/steam_api64.cpp`](src/steam_api64.cpp) — source of truth for behavior  
3. [`exports.def`](exports.def) — export names  
4. [../RE_Tools/docs/GameMain_InitAndLoop.md](../RE_Tools/docs/GameMain_InitAndLoop.md) — where Steam is called in the exe  
5. [../RE_Tools/analysis/phase1_verify.txt](../RE_Tools/analysis/phase1_verify.txt) — last automated verification output  
