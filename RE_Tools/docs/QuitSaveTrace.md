# Quit vs game save (Frida)

**Script:** `RE_Tools/tools/scripts/frida_quit_save_trace.py`  
**Artifact:** `RE_Tools/analysis/frida_quit_save_trace.json`

## Method

1. Spawn `Game/Horsey.exe`, hook `Save_Write` (`0x6DAB0`), `Settings_Save` (`0x71F60`), shutdown sites `0xBED0C` / `0x98680` / `0xBED11`.
2. After load, set **`g_sdl_quit@0x318A50 = 1`** (same flag SDL_QUIT sets).
3. Record hooks through process exit.

## Results (2026-05-15 run)

| Event | On quit? | Notes |
|-------|----------|-------|
| `Shutdown_Entry` @ `0xBED0C` | Yes | First shutdown site |
| `Shutdown_Prep` @ `0x98680` | Yes | Runs before final settings write |
| **`Save_Write` @ `0x6DAB0`** | **Yes** | Same timestamp as prep; `FileWrite` path `Game\save\` via `0x6DB9A`; `edx=1` |
| `Settings_Save` @ `0x71F60` | Yes | Called from `0xBED11` immediately after prep chain |
| `settings.xml` FileWrite | No | Only `save\` path seen in this run |

### During gameplay (before quit)

| Caller (backtrace) | Role |
|--------------------|------|
| `Horsey.exe+10A2C7` | Auto-save path (`0x10A2C2`) |
| `Horsey.exe+10A827` | Paired flush (`0x10A822`) |
| `Horsey.exe+103B84` / `+96F59` / `+BE7C6` | Load/bootstrap chain |

## Conclusion

**Quit writes both `save%d.dat` and `settings.xml`.**

Order on forced quit:

```text
0xBED0C  Shutdown_Entry
  → 0x98680  Shutdown_Prep  (includes Save_Write — no direct E8 to 0x6DAB0; likely indirect)
  → 0xBED11  Settings_Save
```

Earlier docs that said quit only calls `0x71F60` were **incomplete** — `Save_Write` still runs inside the shutdown prep path, not from `0xBED11`.

**Capstone (E9 scan):** `jmp Save_Write` @ **`0x9869A`** inside `Shutdown_Prep` (`edx=1` @ `0x98695`). Not an E8 — see [Shutdown_Save_Callchain.md](Shutdown_Save_Callchain.md).
