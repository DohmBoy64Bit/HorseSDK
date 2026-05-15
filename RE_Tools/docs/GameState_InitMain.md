# `GameState_InitMain` @ `0x97110`

**Capstone** on `Game/Horsey.exe` · span `0x97110`–`0x99121` (8209 B)

**Role:** tail of bootstrap — entered via **`jmp`** from `0x874FF`, not `call`. Likely loads save / enters playable state (see `Save_Load`, `0x103B84` in callees).

## Callers (E8)


## Callees (top)

| Target | Count |
|--------|-------|
| `0xc4ec0` | 24 |
| `0x21e414` | 14 |
| `0xc44c0` | 12 |
| `0x251850` | 10 |
| `0x7f8a0` | 6 |
| `0x28600` | 6 |
| `0x7f3e0` | 4 |
| `0x21e450` | 4 |
| `0x99d70` | 4 |
| `0x96f00` | 3 |
| `0x55bd0` | 3 |
| `0x994a0` | 3 |
| `0x40ce0` | 2 |
| `0xbee70` | 2 |
| `qword ptr [rax + 0x48]` | 2 |

## Strings (sample)

- `n64_0` @ `0x2644a0`
- `n64.fnt` @ `0x2644a8`
- `picory` @ `0x2644b0`
- `ry` @ `0x2644b4`
- `picory.txt` @ `0x2644b8`
- `classified` @ `0x2644c8`
- `ed` @ `0x2644d0`
- `classified.txt` @ `0x2644d8`
- `softsquare` @ `0x2644e8`
- `re` @ `0x2644f0`
- `softsquare.txt` @ `0x2644f8`
- `bubbletime` @ `0x264508`
- `me` @ `0x264510`
- `bubbletime.txt` @ `0x264518`
- `habit_mono` @ `0x264528`
- `no` @ `0x264530`
- `habit_mono.crf` @ `0x264538`
- `no.crf` @ `0x264540`
- `rf` @ `0x264544`
- `capy_bold` @ `0x264548`
- `capy_bold.crf` @ `0x264558`
- `d.crf` @ `0x264560`
- `habit_narrow_bold` @ `0x264568`
- `habit_narrow_bold.crf` @ `0x264580`
- `d.crf` @ `0x264590`