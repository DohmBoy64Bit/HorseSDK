# `Settings_Save` @ `0x71F60`

**Capstone:** `FUN_140071f60` · **Quit caller:** `GameMain` @ **`0xBED11`**

Persists **`settings.xml`** on shutdown — **not** `save%d.dat` (`Save_Write` @ `0x6DAB0`).

**Artifacts:** `RE_Tools\analysis\phase1_settings_save.json`, `RE_Tools\analysis\disasm_settings_save.txt`

## Call graph (unique callees)

| Callee | Count | Role |
|--------|-------|------|
| `Xml_SetAttribute` | 11 | XML attribute write |
| `Xml_DocLoad` | 1 | parse XML |
| `Xml_FindRoot` | 1 |  |
| `0x27920` | 1 |  |
| `Xml_CreateDoc` | 1 |  |
| `File_OpenRead` | 1 |  |
| `0x21e414` | 1 |  |
| `Settings_GetGlobalPtr` | 1 |  |
| `0x25140` | 1 |  |
| `File_ReadToBuffer` | 1 | read existing file |
| `operator_new` | 1 |  |
| `memcpy` | 1 |  |
| `0x262e0` | 1 |  |
| `0x21e450` | 1 |  |
| `0x224844` | 1 |  |

## XML keys referenced in this function (exe strings)

- `background_draw`
- `background_sim`
- `fullscreen`
- `settings`
- `sound`
- `volume`
- `vsync`
- `wb`
- `winh`
- `winw`
- `winx`
- `winy`

## Path / file strings

- `.xml`
- `settings.xml`

## Ghidra renames

| From | To |
|------|-----|
| `FUN_140071f60` | `Settings_Save` |
