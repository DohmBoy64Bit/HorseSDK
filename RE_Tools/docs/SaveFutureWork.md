# Save RE — deferred work

Items intentionally **out of scope** for on-disk save format v12. Do not block round-trip or loader work on these unless gameplay/runtime integration is the goal.

## `FUN_1400AE470` — runtime genetics apply

| Item | Detail |
|------|--------|
| **RVA** | `0xAE470` |
| **Called from** | `0xADB30` after `ReadNestedItem` when `[item+0x234] >= 0` |
| **On disk** | **No** — not part of `save1.dat` bytes |
| **Relation to save** | After `0x6D3B0` unpacks the **0xF0** gene pack @ inventory `+0x51`, AE470 maps allele indices into live horse component bytes using RNG @ `0xC1900` |
| **Artifacts** | `save_genetics_runtime.json`, `disasm_genetics_ae470.txt`, `decode_genetics_ae470.py` |

**Pinned status:** documented only; no C loader / editor support until phenotype simulation is required.

## Footer `vtable+0xB0` / `+0xB8`

| Item | Detail |
|------|--------|
| **Write** | `0x6E112` — `call [rax+0xB0]` after `WriteNestedSave` |
| **Read** | `0x6EA08` — `call [rax+0xB8]` after `ReadNestedSave` |
| **On disk** | Any bytes from this vcall are **not** separated in the Frida writer trace (may overlap prefix gaps). The former “opaque 240 B” regions are **gene packs**, not B0. |
| **Pinned status:** identify B0/B8 function RVAs and wire layout only when needed. |

## Other

- Per-field labels for `SaveSlot6` / `SaveRow13` ctx rows (offsets known in `SaveContext.h`).
- Full `vtable+0x48` payloads for all 343 main-nested b8 slots beyond the sampled type-1/2/tail layout.
