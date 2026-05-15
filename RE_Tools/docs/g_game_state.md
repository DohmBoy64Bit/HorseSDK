# `g_game_state` @ `0x313720`

**Global:** `qword` pointer to `GameState` object (`operator_new(0x30)` + `GameState_Ctor` @ bootstrap).

**Artifact:** `RE_Tools\analysis\phase1_g_game_state.json`

## Write (bootstrap)

- `0x874F1` — `mov [g_game_state], rbx` after `GameState_Ctor`

## Reads / uses (Capstone RIP scan)

**18** `mov/lea reg, [rip→g_game_state]` · **1** stores · **21** unique sites

### Game_Update
- `0x874f1`
- `0x876e9`
- `0x87806`
- `0x87827`

### Save_IO
- `0x6eabc`

### other
- `0x43a6`
- `0x6611f`
- `0x663b0`
- `0x6657a`
- `0x666af`
- `0x8f89e`
- `0xd0aaa`
- `0x103dfa`
- `0x10a2d8`
- `0x10a827`
- `0x10aaa1`
- `0x10ab40`
- `0x10ab58`
- `0x10e218`
- `0x1107b1`
- `0x111939`
