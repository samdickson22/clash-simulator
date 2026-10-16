# macOS arm64 live16402b-r3 parity build

Status: COMPLETE — **strict parity FAIL; unqualified candidate**. Smoke passes 3/3. Built only in `/Users/sam/clasher-live/fullpool/` on `macmini-fleet`.
No deploy or live-loop selection was performed.

Native: `clasher_core.abi3.so`, SHA256
`8072e5779f6940ead50955fb8335224ce5162823918e2e743523491a48e97988`, **2,441,064 bytes**.
Mach-O arm64. Source: `git archive 878d5f459d58112527e9c3e76c804f27e5d7c0a3 engine-cards`;
all **504/504** archived source hashes matched on the Mac. Toolchain: `rustc 1.97.1
(8bab26f4f 2026-07-14)`, `aarch64-apple-darwin`; arm64 CPython 3.12.13.
Built with `cargo +1.97.1 build --locked --release --features extension-module,gil-release -j2`,
`CARGO_INCREMENTAL=0`, and an isolated `CARGO_HOME`/`CARGO_TARGET_DIR`. Copied
`target/release/libclasher_core.dylib` to `live16402b-r3/native/clasher_core.abi3.so` before
`cargo clean` removed **128.8 MiB** of intermediates. The previous recipe is documented in
`reports/live/bot/RESULTS.md` §5 and `reports/live/PROGRESS.md` (Mac native `617bfef4`, total-tree parity).

The trimmed live root was copied from the immutable **127x04** release
`/mpac/sdicks02/repos/clasher-bot-runtime/live16402b-r3`, whose RECEIPT.json SHA256 is
`2f60094df4007faecc4b3e2502b2c338255d8fd4650ea614ba74c1f02d387193`.
Python engine fixes from r3 are preserved. Gamedata SHA256 remains
`a7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb`.
The bot code snapshot was `206bde8f552b4fd132ecb782d501cf02f100d3c5`, plus the Mac PIN_SETS entry
in this change. All **4,843/4,843** runtime/input file hashes and **282/282** initial bot-code hashes
matched after transfer; the subsequent `runtime.py` change is the documented pin addition. An additional 21 released support files (19 imitation helpers, roles training JSON and W-screen planner) were restored after the initial trim; their hashes are included in postflight verification (**1,861 released files preserved**, plus all 504 source hashes).

## C56 parity

Reference: **Batch A gate run 4 on 127x04**, `/mpac/sdicks02/jobs/clasher/cards/batchA/gate/`,
`fixtures-total.jsonl`, `roots-total-{0,1,2,3}.jsonl`, and `compare.json`.
Every Linux root header identifies native
`de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1`.
Inputs and unchanged gate tools came from that batch's `roots/` and `gate-tools/`, and the
577 original train/validation episodes named by the Linux fixture output (four required files per episode).
Only the fixture data location was adapted through `sitecustomize.py` setting `rs_parity.D`.
Gate Python/glue and baseline gamedata use the exact 878d5f459 tree with the original r1 support files;
the live overlay and full-pool pin are used separately for smoke.

| Gate | Byte-identical records | Verdict |
|---|---:|---|
| Fixtures | 577/577 | PASS |
| 300 roots × full/cut | 598/600 | FAIL (18 one-ULP rollout values) |

Record bytes are compared directly, keyed by episode or `(k, variant)`, retaining the original JSON
float/hex/hash representations. Only the roots' native-path/native-SHA provenance header fields are
expected to differ. Sample size, input population and rollout arguments must agree. No tolerances,
rounding, normalized floats, or substituted Linux records are used. The Linux baseline contains 429/577 Python↔Rust lockstep successes; its 148 existing mismatch records are included in the exact cross-platform comparison. **Strict parity FAIL.** Only root **980** (game index **11**, tick **2780**, seat **1**) differs, in both `full` and `cut`. Exactly **18/9,336** rollout values differ; **9,318/9,336** match. Each difference is **+1 ULP = 2^-56 = 1.3877787807814457e-17** (Mac minus Linux).

| Actions; all balanced/pressure/defense styles, both variants | Linux `float.hex()` | Mac `float.hex()` | Values |
|---|---|---|---:|
| WAIT (2304) | `-0x1.0d90bf5d0433bp-4` | `-0x1.0d90bf5d0433ap-4` | 6 |
| 685 and 803 | `-0x1.6c17b8eb784c2p-4` | `-0x1.6c17b8eb784c1p-4` | 12 |

These are `rollout_e1` positions **0–2 and 9–14** in each affected record. All other fields in all 600 records match byte for byte: evaluate, evaluation parts at the original roots, public views/masks, selected actions, digests, apply-discrete checks, step checks and snapshot hashes. Header sample/population/arguments agree. [Full exact comparison](comparison.json). No tolerance was applied and no native/source math was changed. The isolated endpoint diagnosis uses exactly the same serialized metadata and root payload on Linux and Mac. For all three actions, delayed-command endpoint snapshots, digests and action traces are byte-identical, and their scalar values equal `rollout_e1` on each platform. Only endpoint leaf part 6 (danger) differs. The pinned source computes `proximity = (-eta.min(30.0) / 4.0).exp()` in `engine-cards/src/leaf.rs`.

The Hog Rider term (entity 35 for WAIT; entity 38 for 685/803) reproduces the platform libm difference at identical binary input:

```text
argument       -0x1.6e54fe9d10988p-1
Linux exp()     0x1.f4afac24b2b36p-2
macOS exp()     0x1.f4afac24b2b35p-2
```

Recomputing the leaf with only those `exp()` outputs substituted reproduces each Mac native danger value exactly. WAIT danger is Linux `0x1.24698b96c3c42p-3`, Mac `0x1.24698b96c3c40p-3`; 685/803 danger is Linux `0x1.522f073ccf7aap-3`, Mac `0x1.522f073ccf7a9p-3`. [Endpoint and libm evidence](diagnostic-summary.json). The build remains the exact requested source and features; the strict gate remains **FAIL**.

Raw Mac outputs, copied Linux outputs, source/input hashes, scripts and comparison are retained on
**127x05**, `/mpac/sdicks02/jobs/clasher/cards/mac/`.

## Full-pool smoke

**PASS: 3/3 terminal games, 0 crashes, 0 panics, 0 fast/search/native errors, 0 root-state breaks.** `Runtime(verify=True)` passes with the Mac pin, the expected gamedata SHA and the pinned checkpoints. All full-pool extension file hashes and receipts were checked before play. The runtime has 238 config entries. The final run built **190 native search roots** and accepted plays covering all four requested cards.

| Game / seed | Terminal tick | Native roots | Verdict |
|---|---:|---:|---|
| 0 / 202610160700 | 892 | 22 | PASS |
| 1 / 202610160701 | 3019 | 55 | PASS |
| 2 / 202610160702 | 3601 | 113 | PASS |

Final run: `outputs/smoke-r4.log`, `smoke-games.jsonl`, `smoke-summary.json`; [summary](smoke-summary.json). Earlier setup attempts are retained separately: missing `own_cycle` support, roles training JSON, and an error-counter bug in the custom harness. The training-JSON import failure produced three aborted game initializations, each before tick 0. Those attempts are excluded from the final 3-game result; no engine/native source was changed to obtain the pass. The prior runtime-open manifest was checked and the frozen W-screen planner restored before the final games.

Recipe: **`LIVE-K4L-R-gs-rw-fc-mpoolfp-w200-t1-p1`**, the LIVE K4L gs/rw/fc recipe with one native
thread and one persistent learned-rollout worker to respect the revised two-core cap. macOS uses
`CLASHER_LOPP_POOL_START=spawn`. Three complete games against **R3a** use alternating seats and
seeds **202610160700–202610160702**. Both decks contain **Bomber, GoblinCage, Tombstone,
SpearGoblins**; the remaining cards are either Knight/Fireball/HogRider/Musketeer or
Graveyard/Freeze/Mortar/Fisherman. Full games run to terminal, with the normal 6001-tick limit,
27-tick command delay and 200 ms search wall. Searches, fallbacks, native/pool errors and panics are
counted; native roots and accepted plays are recorded. The candidate Mac platform pin is the
verifier-safe equivalent of `live16402b-r3`; `Runtime(verify=True)` stays enabled.

Full-pool model extensions were copied into `models/` with their receipts:

- R3a-fp.pt: `ce7b0ea49e67671dc82f3584c3eb68c9891a47899a8d8f83a0519a960df8cbc2`.
- main02-fp.pt: `69313468f7439f9e7d0356ff92f4f2d9463e4bb5c10c32e360a0c1a1695cf0b9`.
- rl5-v10-fp.pt: `a6565cabe728e8842405cb7a9e040970893566596b11980ad7ddf867df3dddcc`.
- poolfp.npz: `faf6efbed4e46a419172a4b3887674c740f30d87f181de97cc8e7120dc3f878f`.

## Isolation, footprint and handoff

All build/gate/smoke jobs run at **nice 19 or lower priority**. Cargo uses `-j2`, fixture workers are
limited to two, root parity runs serially, and smoke uses `t1-p1`; numerical libraries have one thread
and Rayon has at most two. A guard samples the latest live run every two seconds, reading
`m*/frames.jsonl` and `decisions.jsonl`. It SIGSTOPs only its own process group if whole-battle FPS
falls below **9**, or whole-battle/recent-60-decision p95 exceeds **40 ms**, and latches the pause until
the battle ends. Initial pauses were caused by early decision spikes; recovered mid-battle latency did
not cause early resumption. STOP/CONT/EXIT receipts are retained with each phase's logs. The revised watchdog threshold is 8 GiB free. Completed fixture input directories are deleted only after the complete episode record is flushed; originals remain archived on 127x05.

Final total footprint: **819,978,240 bytes (781.99 MiB; about 0.764 GiB)**, including the independent venv, sources, runtime, models, tools and evidence. The runtime root itself is **120,602,624 bytes (115.02 MiB)**. Free disk after all jobs exited: **9.51 GiB**, above the revised 8 GiB watchdog threshold. [Measurement](footprint.json).

All 577 copied episode inputs were deleted after their results flushed (**290,897,439 bytes reclaimed**). Gate-only inputs and support roots, Cargo intermediates and the 30 MiB isolated Cargo download cache were removed. Source/archive originals and complete inputs remain on 127x05. All owned build/gate/smoke/diagnostic/postflight process groups exited.

`MAC-RECEIPT.json` records `qualification_passed: false`, the exact native/data/source/model pins, parity verdict and smoke summary. `MAC-CONTENT-SHA256.json` inventories 1,864 runtime files; its SHA256 is `11a46b2948b99b82020fc757a20faa67db8422c110f2e955f39480f0066d732e`. The preserved Linux receipts establish upstream provenance; the Mac receipt records this platform overlay. [Mac receipt](MAC-RECEIPT.json).

```text
~/clasher-live/fullpool/
  live16402b-r3/
    native/clasher_core.abi3.so
    src/clasher/                    # released r3 Python engine
    engine-rs/                      # released native Python glue
    imitation/
    student-source/
    reports/                        # runtime import paths and human-deck catalog
    main02.pt  R3a.pt
    gamedata.json  geometry.json  hitboxes.json  topology.json
    decks.json  load-config.json
    *RECEIPT.json
    MAC-CONTENT-SHA256.json          # exact per-file inventory (postflight)
  code/bot/                         # bot code with platform PIN_SETS entry
  code/reports/explore/x4s/          # runtime's repo-relative sdefault imports
  models/ext/                       # full-pool policy extensions and receipts
  models/lopp-fp/                    # poolfp.npz and receipt
  src/engine-cards/                  # exact 878d5f459 source archive
  venv/                             # independent Python environment
  tools/  outputs/                  # build/gate/smoke tools and audit receipts
```

The opt-in candidate **`live16402b-r3-mac`** pin is added to `bot/players/runtime.py`:

```python
PIN_SETS['live16402b-r3-mac'] = dict(
    PIN_SETS['live16402b-r3'],
    native_sha256='8072e5779f6940ead50955fb8335224ce5162823918e2e743523491a48e97988',
)
```

It inherits the full card scope, fc side cut, Fireball/Poison crown settings, gamedata and checkpoint
pins, changing only the native hash. Exact candidate environment (the LIVE LEAD performs selection; strict parity failed):

```sh
export CLASHER_BOT_RUNTIME="$HOME/clasher-live/fullpool/live16402b-r3"
export CLASHER_DELAY_NATIVE_DIR="$CLASHER_BOT_RUNTIME/native"
export CLASHER_BOT_RUNTIME_PINS=live16402b-r3-mac
export PYTHONHASHSEED=0
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$HOME/clasher-live/fullpool/code"
export CLASHER_ROOT="$CLASHER_BOT_RUNTIME"
export CLASHER_EVAL_RUNTIME_ROOT="$CLASHER_BOT_RUNTIME"
export CLASHER_LIVE_FAST="student:$HOME/clasher-live/fullpool/models/ext/rl5-v10-fp.pt@0.5375"
export CLASHER_LOPP_MODELS="$HOME/clasher-live/fullpool/models/lopp-fp"
export CLASHER_LOPP_POOL_START=spawn
export BOT_FULLPOOL_POLICIES="v1=$HOME/clasher-live/fullpool/models/ext/main02-fp.pt,R3a=$HOME/clasher-live/fullpool/models/ext/R3a-fp.pt"
export RAYON_NUM_THREADS=2 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1 NUMBA_NUM_THREADS=1
# Interpreter: $HOME/clasher-live/fullpool/venv/bin/python -B
# Smoke recipe: LIVE-K4L-R-gs-rw-fc-mpoolfp-w200-t1-p1
```

Dependencies are pinned to Linux gate versions: numpy 2.3.5, torch 2.10.0, numba 0.63.1,
gymnasium 1.2.3, msgspec 0.20.0. The live venv, macbench, loop files, running live processes,
adb, emulators and other apps were not modified by this work. The runtime tree is an **unqualified candidate**: the required byte-identical parity gate failed. The Mac pin verifies file identity and does not waive that gate. Live selection remains with the LIVE LEAD.
