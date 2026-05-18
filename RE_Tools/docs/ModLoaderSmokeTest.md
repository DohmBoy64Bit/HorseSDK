# Mod loader smoke test

Run after `deploy_modloader.py` and whenever hook signatures change.

## Static (no game)

```bat
cd E:\games\HorseSDK
python RE_Tools\tools\scripts\verify_modloader_static.py
python RE_Tools\tools\scripts\verify_catalog_rvas.py
```

## Manual in-game

1. Start `Game\Horsey.exe` (windowed).
2. Run `Game\horse_inject.exe`.
3. Alt-tab to **Horsey Mod Loader** console.
4. Confirm: base address, `Loaded mod: Example Mod`, `GainMoney hooked`, `SpendMoney hooked`.
5. **Shop:** buy any item — expect `SpendMoney -N (ctx=... ui=... var=...)` and **no freeze/crash**.
6. **Race:** start and finish a race — expect `GainMoney +N` if you win/prize.
7. Console: `hook on Save_Write`, perform autosave or quit — expect `[hook] Save_Write ctx=...`.
8. `hook off SpendMoney`, buy again — no SpendMoney lines; game should still work.

## Frida cross-check (optional)

```bat
python RE_Tools\tools\scripts\frida_gameplay_hooks.py --attach
```

Shop + race while attached; compare `gameplay_frida.json` with loader console lines.

## Pass criteria

- [ ] Static scripts exit 0
- [ ] Shop buy does not crash with example_mod loaded
- [ ] `help` shows ASCII `-` separators (no `ΓÇö`)
- [ ] `overlay=0` — no top-left overlay window
