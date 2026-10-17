# Full-scope belief wiring

Branch: `cards/fullscope-belief`. Base: `aa61daf8d` (origin/main snapshot).

## Diff summary

| Item | Finding / change |
| --- | --- |
| 1: live/search planner construction | Already fixed upstream. `_WallMulti.start()` calls `planner_belief(rt, Belief)` and installs the returned class (`844d5655ad`); `MultiSearchPlayer.start()` does the same (`f6fdbaa304`). These are the only `PublicPlanner` construction sites in `bot/live/player.py` and `bot/search/`. No changes to those sources. |
| 2: live belief completions | Already fixed upstream (`64c720ea11`). `LivePlayer.start()` installs `LiveBelief` and assigns `rt.PRIOR` only when `belief_spec(rt) == 'c56'`. A selected full-pool prior retains `FullPoolBelief`, whose rebuilds sample decks containing the revealed cards. No changes to that source. |
| 3: full-pool eval strong opponent | `fullpool_eval.players()` now creates the default strong runtime with the caller's selected belief spec and uses the bundle's `FAST` for full-pool belief. The existing `strong_rt` argument overrides the runtime; the new keyword-only `strong_fast` independently overrides the checkpoint. An explicitly supplied C56 runtime keeps `LiveBelief` and `OLD_FAST` by default. `Observed` validates the actual selected class and checkpoint. |

Existing downstream validation workers that explicitly pass `runtime('c56')` retain their legacy setup. To select full scope there, pass `runtime(BELIEF)` or omit `strong_rt`; `strong_fast=FAST` can override just the fast tier. No translator vocabulary changes and no merge.

## Gate protocol

All matches use the pinned `live16402c` runtime and its native library, `PYTHONHASHSEED=0`, `NUMPY_MADVISE_HUGEPAGE=0`, single-thread numerical libraries, writable per-host `NUMBA_CACHE_DIR`, and `nice -n 15`.

- 08: before/after HEADLINE with `cpu_job.sh 4`; three serial workers plus the controller. Candidate `K4L-R-gs-rw-fc` (the serial fc variant), R3a/v1, cases 0–5, standard HEADLINE base `1455777415631152`. Also one unbounded `K4CW-r16` vs R3a, case 0 on C56 decks.
- Before: source archive of `aa61daf8d`, belief selection unset. After: changed source snapshot, `BOT_BELIEF_PRIOR=c56`. No extended policy overrides in either gate arm. This compares the implicit and explicit C56 paths as well as before/after; the construction smoke separately checks `rt.belief_prior='c56'`.
- 04: positive game and real construction checks with `cpu_job.sh 1`; extended v1/R3a installed using `bot/fullpool/run/env.sh`. Default harness fast checkpoint is `fits/f1a2/step-001200.pt`. The placement adapter uses the existing exact-binary receipt `/mpac/sdicks02/jobs/clasher/bot-deckopt2/placement-proof.json`.

The positive match uses our engine with live16402c stats, not RoyaleSim. The actual harness-created `LIVE-K4CW-r16` faces opponent deck `[Pekka, Witch, SkeletonDragons, ElectroWizard, Arrows, Zap, Knight, Giant]`, seed `1866440789737856` from the existing true-ids smoke bank. The opponent fixture deploys each target card once, using only its own hand/elixir and the ordinary delayed command channel, then follows R3a. The observer requires all four target cards to be revealed and present in **every** remaining belief state after their events are processed. It does not modify the belief or its RNG.

`smoke.py` also starts both planner construction routes and checks that they install `FullPoolBelief`, checks `planner_belief`'s C56 prior/class identity, starts an explicit C56 harness opponent, and constructs an independent fast-tier override.

## Results

| Positive / construction gate | Result |
| --- | --- |
| LIVE-K4CW-r16 vs four-card full-pool fixture | PASS: terminal at tick 3592; 0 search errors, 0 fast errors, 0 panics; search stayed enabled |
| Full-pool belief | PASS: `FullPoolBelief`, 4 rebuilds; PEKKA, Witch, Skeleton Dragons, Electro Wizard revealed and present in every posterior state at the check |
| `no train deck` errors in passing smoke log | 0 |
| WallCandidatePlayer / MultiSearchPlayer construction | Both install `FullPoolBelief` |
| Explicit C56 runtime | Original prior/class identity; `LiveBelief`, it5s2 at 0.5375 |
| Independent fast selector | Explicit C56 runtime accepts `strong_fast=FAST` |

Positive command hash: `a6cf2cfa6f9bc02f303e14eb5a6e9865f7ab0ffc8fd0efeefff7d46c21f268af`.

K4L C56 command-hash gate: **12/12 identical**, with 0 error rows.

| HEADLINE case | R3a hash (before = after, prefix) | v1 hash (before = after, prefix) |
| --- | --- | --- |
| 0 | `38ca14d87c9ca677` | `872e6bfc2462229a` |
| 1 | `b50ea8753dfcde90` | `315442ea17f49ea0` |
| 2 | `09a0b737c743d913` | `bc3e623f2dc478a0` |
| 3 | `5e7aba8a333d582c` | `6feb21c56c511984` |
| 4 | `3057a250233a4498` | `136465ec2e2d5c28` |
| 5 | `5f8667c4c217c776` | `24cd763cce34f9cc` |

| Additional C56 gate | Before command hash | After command hash | Result |
| --- | --- | --- | --- |
| K4CW-r16 vs R3a, case 0 | `16bfd8fb961aeccec0f67b7581054b12f852892f465b298e71e3f382d33fd7f3` | `16bfd8fb961aeccec0f67b7581054b12f852892f465b298e71e3f382d33fd7f3` | Identical |

`verify.py`: **PASS, 13/13 identical C56 hashes; full-pool smoke passed**. All 26 before/after games were terminal with 0 error rows. Full hashes and the positive-game/construction evidence are retained in [gate-results.json](gate-results.json).

## Reproduction and artifacts

- `gate.sh SNAPSHOT OUTPUT unset|c56`: run on 04/08 under `/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 4`.
- `PYTHONPATH=. python reports/cards/fullscope-belief/smoke.py OUT.json`: run from the snapshot under `cpu_job.sh 1`, with the full-pool environment above and `CLASHER_LEVELS_PLACEMENT_PROOF` set.
- `verify.py BASELINE CANDIDATE SMOKE OUT.json`: rejects missing/duplicate/error/nonterminal gate rows, unequal command hashes, and failed positive-game assertions.
- Source snapshots and full logs/results: `127x08:/mpac/sdicks02/jobs/clasher/cards/fullscope-belief/{before,after,baseline,candidate}` and `127x04:/mpac/sdicks02/jobs/clasher/cards/fullscope-belief/{after,smoke.log,smoke.json}`.
- The first smoke invocation stopped before a game because the source snapshot omitted the frozen frequency table; the snapshot was repaired and rerun.
- The initial policy-only positive game finished with zero search/fast errors or panics and three belief rebuilds, but R3a never played PEKKA. Its receipt is retained as `smoke-policy-only.json`; it was not counted as the four-card positive gate. The fixture above ensures all four reveal paths are exercised.
