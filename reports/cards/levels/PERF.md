# Exact-level planning: export warm-up

2026-10-17, exploration. Branch `cards/levels-perf`, based on `origin/main` **e5edb707d** (contains the levels merge
3ea58c365). Player **K4L-R-gs-mk1a1**, opponent **R3a**, runtime **live16402c**, full-pool environment and
**LIVE-AB1 cases 0–2**. Raw jobs: **127x04 `/mpac/sdicks02/jobs/clasher/cards/levels-perf`**.

The large first-game cost is **one-time Python-engine exports**, not a 9× cost on every search decision.
`LevelConfigs.load(L)` exports the entire 121-card pool if `L<L>.json` is missing. Exact max-level planning needs
**L16**, **L11** for export validation, and **L17** for Mirror: **363 card/level exports**. The second game in the
same process reuses them; a fresh process reads the published JSON files. The disk cache already existed before
this change. This patch makes warm-up explicit and keeps it out of the first decision.

## Measurement

All game/export work used 127x04, nice 15, single-thread BLAS/torch/native settings and `cpu_job.sh` leases of
one or two slots (never more than four slots across this task). `PYTHONHASHSEED=0`, `NUMPY_MADVISE_HUGEPAGE=0`,
`PYTHONDONTWRITEBYTECODE=1`, writable `NUMBA_CACHE_DIR` from `bot/fullpool/run/env.sh`. The only computation on
05 was the light unit suite and CLI help. No runtime-root files were changed.

Times below include `play_match` setup and the game, and exclude construction of `Runtime()` (separately
76–102 s in the initial probes). Every full-game row uses `max_ticks=6001` and reaches a terminal state.
The result's internal `cpu_seconds` starts after player setup, so it is not used to compare cold totals after
preparation moves into setup. A cold run starts with an absent private cache directory. Its immediate replay
uses the same Runtime/process.
Each disk-loaded case starts another Python process against that case's populated cache. No cProfile overhead
is included in the cold/warm game comparisons.

| Code / case | Empty disk, first game | Immediate replay | Fresh process, populated disk |
|---|---:|---:|---:|
| Original, case 0 | 658.9 s | 68.4 s | — |
| Fixed, case 0 | 631.9 s | 69.7 s | 69.5 s |
| Fixed, case 1 | 607.4 s | 56.3 s | 64.4 s |
| Fixed, case 2 | 591.9 s | 47.8 s | 53.4 s |

Case 0: original cold → same-process warm **9.6×** (658.9 → 68.4 s); original cold → fixed disk-loaded
**9.5×** (658.9 → 69.5 s). The fixed empty-cache game still takes 631.9 s; it does the same exports at setup.
Warm-game times before/after are 68.4/69.7 s; this is not a steady-search speedup claim.

| One-time export build | Cards | Original case 0 | Fixed case 0 |
|---|---:|---:|---:|
| L11 | 121 | 177.1 s | 182.3 s |
| L16 | 121 | 220.5 s | 192.0 s |
| L17 | 121 | 190.3 s | 183.9 s |
| Total | 363 | 587.9 s | 558.2 s |

Independent runs on a shared host; variation in export duration is not attributed to the patch.
Every memory-warm and disk-loaded row performs **0 exports / 0 level builds**. The first original decision
takes **590.3 s**; after startup preparation it takes **0.38 s** on the same case.

Moving exports to match startup does **not** make an empty cache cheaper to build. The one-shot warmer pays that
cost before the session; subsequent processes use the persistent files. Cold and prewarmed total costs are
reported separately, rather than claiming a reduction in rollout work.

An initial attempt using the shared cache waited in `locks_lock_inode_wait`: the old reader acquires the build
lock even for an already-published level while other jobs export different levels. That probe was stopped and
all controlled measurements use private caches. The patch lets published level/support files be read without
that unrelated writer lock; missing levels still build under the lock and publish by atomic rename.

## Decision breakdown (initial disk-populated cProfile probe)

These are inclusive wall times for case 0, tick 90, under cProfile; nested rows must not be added.
The native constructor has no separate cProfile entry; the root self-time bounds parsing plus its own assembly.

| Phase | L11 (`levels=None`) | Exact L16, before patch |
|---|---:|---:|
| Entire decision | 593 ms | 4,837 ms |
| Root, including first config setup | 142 ms | 4,440 ms |
| Mixed/Mirror config and fc preparation | — | 4,429 ms, once per match |
| `CutConfig` construction | — | 1,892 ms, two constructions |
| JSON encoding, all calls | 109 ms | 656 ms |
| Python JSON decoding, all calls | 11 ms | 91 ms |
| Native root parse, upper bound from root self-time | 26 ms | 3.1 ms |
| Native rollouts | 230 ms | 225 ms |
| Learned rollouts | 114 ms | 100 ms |
| Pool shipping / worker parsing | 0 | 0 |

`K4L-R-gs-mk1a1` is serial: it has no learned-worker pool. The pool content-hash cache is therefore not the
explanation for this measurement. `ExactLevelRoot._cfg[seat]` already memoizes the mixed config and `CutConfig`;
`CutConfig` already retains serialized cards/full config and caches cuts by reachable cards/side entries.
`LevelConfigs.entry` already memoizes qualified `(card, level)` payloads. No new per-decision memo or pool-key
change is needed. The BOT LEAD's separate steady-decision measurement (1.4–1.5×) is consistent with focusing
this work on cold startup.

## Changes

- `install_planner` materializes the exact config at match startup, before `player.start` and the first decision.
  This prepares every required export level and the final Mirror-aware cut. The full-pool belief can sample any
  card, so warming only the two actual decks would leave lazy export work. Each card export includes its
  recursive spawn/death payloads; no separate child export queue is needed.
- `python -m bot.levels.warm --levels 16` prepares **L11/L16/L17**, validates support, reports disk hits/errors,
  and can run once before starting a session or its worker processes. It works with other level sets too.
- The persistent cache namespace now includes the SHA256 of `configs.py`, `match.py`, and `root.py`, in addition
  to runtime/native/gamedata pins and the full reference-config hash. Changing the export/level-patch code cannot
  silently reuse an older export. Old cache namespaces are left in place; a new code version needs one warm-up.
- Published-cache reads bypass the global build lock. Export generation remains serialized and atomic.
- The final `CutConfig` is constructed once, after Mirror remapping, instead of constructing and discarding an
  intermediate cut. Config semantics and rollout/search code are unchanged.

## Gate

**PASS: 17 terminal games; zero native/decision failures.**

| Case | L16 cold = memory-warm = disk-loaded | `levels=None` before = after |
|---|---|---|
| 0 | `3f376aaf4c1d7b0b` | `2bf6063112a8c99f` |
| 1 | `3bf3b7b2f06cd7ca` | `a33bc8c0dc12dd82` |
| 2 | `d04525344e6c5e91` | `608c85b9bb284b4e` |

The original cold/warm L16 case-0 pair also matches the fixed branch. The checker compares full hashes,
terminal ticks, winner, tower HP, plays and accepted commands, and asserts 363 cold exports versus zero
memory-warm/disk-loaded exports. Full hashes/timings are in
[`receipts/perf-gate.json`](receipts/perf-gate.json).

Unit checks: `pytest bot/levels/test_match.py -q`: **16 passed**, including the new published-cache reader
regression. The warmer CLI passed with three disk hits, 121 cards at each level, and no errors
([receipt](receipts/perf-warmer.json)). The validated namespace **`16412b000df67f41-match3`** is populated on 04
under the match runner's default writable cache (`/mpac/sdicks02/jobs/clasher/cards/levels/level-configs`).
Staged changes are scanned with
`/mpac/sdicks02/cc/tools/bin/clasher-secret-scan` before commit.

## Reproduce

On 04/08, source the full-pool environment from this checkout:

```bash
export ROOT=/mpac/sdicks02/repos/clasher-bot-runtime/live16402c PINS=live16402c
source bot/fullpool/run/env.sh
export CLASHER_LEVELS_CACHE=/mpac/sdicks02/jobs/clasher/cards/levels-perf/session-cache
```

Warm before the live session (each host needs its own writable cache):

```bash
/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 15 \
  "$PY" -B -m bot.levels.warm --levels 16
```

Cold then same-process warm, using an **absent** private directory; repeat for cases 1 and 2:

```bash
COLD_CACHE=/mpac/sdicks02/jobs/clasher/cards/levels-perf/new-cache-case0
test ! -e "$COLD_CACHE"
/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 15 \
  "$PY" -B reports/cards/levels/tools/perf.py --out cold-after-case0.jsonl \
  --levels max --ticks 6001 --cases 0,0 --config-cache "$COLD_CACHE"
```

Run the same command in a new process with `--cases 0 --out disk-after-case0.jsonl` for the disk-loaded case.
Use `--levels none --cases 0,1,2` for the unchanged default path. `--profile --ticks 301 --cases 0` records
cProfile data for the first/fourth eligible decisions. The gate checker is
[`tools/perf_compare.py`](tools/perf_compare.py); the benchmark is [`tools/perf.py`](tools/perf.py).
